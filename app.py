"""
CVRadar v3
AI-Powered Resume Screening Matrix
app.py

New in v3:
- Multi-LLM: Gemini / Claude / OpenAI selectable by user
- Provider health check before main loop
- Graceful degradation: LLM failure → Track 1 local score (no blank rows)
- JD Builder removed: compulsory DOCX JD upload for all tracks
- Track 1 fully LLM-free: local JD parsing via jd_parser.py,
  domain via domain_taxonomy.txt, experience via section-aware regex
- Semantic exclusion filter: numeric range + role-title matching
- Dark accessible UI (high contrast, bold white text)
- Simplified nav: Candidate Screening + Batch Analytics only
- Clean 12-column Excel output
- Per-request 45s timeout, adaptive pacing, capped backoff
- Session-scoped storage (multi-user safe)
"""

# =====================================================
# IMPORTS
# =====================================================

import gc
import os
import re
import uuid
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

# =====================================================
# PROJECT MODULES
# =====================================================

from config import (
    UPLOAD_DIR, EXPORT_DIR, CACHE_DIR, LOG_DIR,
    SCORING_WEIGHTS, FIT_CATEGORIES,
)

from src.parser import ResumeParser
from src.jd_parser import parse_jd
from src.llm_provider import (
    LLMProvider, GEMINI, CLAUDE, OPENAI, PROVIDER_MODELS, MODEL_DISPLAY,
)
from src.evaluator import CandidateEvaluator
from src.scorer import CandidateScorer
from src.reporting import ReportingEngine
from src.checkpoint_manager import CheckpointManager
from src.status_tracker import StatusTracker
from src.schemas import CandidateProfile, ScoreBreakdown, JDRequirements
from src.filters import FilterEngine, FilterFlags, INCLUSION_BONUS, EXCLUSION_PENALTY

# =====================================================
# LOAD ENVIRONMENT (server key is optional)
# =====================================================

load_dotenv(Path(__file__).resolve().parent / ".env")

def _get_secret(key: str) -> str:
    """
    Safe st.secrets read. On local machines with no secrets.toml,
    st.secrets.get() raises StreamlitSecretNotFoundError instead of
    returning the default. This wrapper absorbs that cleanly.
    """
    try:
        return st.secrets[key] or ""
    except Exception:
        return ""

_SERVER_KEYS = {
    GEMINI: os.getenv("GEMINI_API_KEY") or _get_secret("GEMINI_API_KEY"),
    CLAUDE: os.getenv("ANTHROPIC_API_KEY") or _get_secret("ANTHROPIC_API_KEY"),
    OPENAI: os.getenv("OPENAI_API_KEY") or _get_secret("OPENAI_API_KEY"),
}

# =====================================================
# STREAMLIT CONFIG
# =====================================================

st.set_page_config(
    page_title="CVRadar | AI Resume Screening",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================
# DARK ACCESSIBLE CSS
# High contrast: dark navy BG, bold white labels,
# coloured accents — readable with eye sensitivity
# =====================================================

st.markdown(
    """
    <style>
    /* Main background */
    .stApp, .main, [data-testid="stAppViewContainer"] {
        background-color: #0f0f1a !important;
        color: #f0f0f0 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1a1a2e !important;
    }
    [data-testid="stSidebar"] * {
        color: #f0f0f0 !important;
    }

    /* All text elements — bold white */
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-weight: 800 !important;
    }
    p, label, span, div {
        color: #e8e8e8 !important;
    }

    /* Input fields */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div,
    .stFileUploader {
        background-color: #1e1e3a !important;
        color: #ffffff !important;
        border: 1px solid #4a4a8a !important;
        border-radius: 6px !important;
    }

    /* Buttons */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 800;
        height: 3.2rem;
        font-size: 1rem;
        background-color: #4a4aff !important;
        color: #ffffff !important;
        border: none !important;
        letter-spacing: 0.03em;
    }
    .stButton > button:hover {
        background-color: #6a6aff !important;
    }

    /* Primary button (Execute) */
    .stButton > button[kind="primary"] {
        background-color: #00b4d8 !important;
        color: #0f0f1a !important;
        font-weight: 900 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #00d4f8 !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background-color: #1e1e3a;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #3a3a6a;
    }
    [data-testid="stMetricValue"] {
        color: #00d4f8 !important;
        font-weight: 900 !important;
        font-size: 1.6rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: #b0b0d0 !important;
        font-weight: 700 !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background-color: #1a1a2e !important;
        border: 1px solid #3a3a6a !important;
        border-radius: 8px !important;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Info / warning / error boxes */
    .stAlert {
        border-radius: 8px !important;
        font-weight: 700 !important;
    }

    /* Session badge */
    .session-badge {
        font-size: 0.8rem;
        color: #00b4d8;
        background: #1a1a2e;
        padding: 4px 12px;
        border-radius: 12px;
        border: 1px solid #00b4d8;
        display: inline-block;
        font-weight: 700;
    }

    /* Hero text */
    .hero-text {
        font-size: 1.1rem;
        color: #b0b0d0;
        line-height: 1.7;
        font-weight: 500;
    }

    /* Radio and checkbox labels */
    .stRadio label, .stCheckbox label {
        color: #e8e8e8 !important;
        font-weight: 700 !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #1a1a2e; }
    ::-webkit-scrollbar-thumb { background: #4a4a8a; border-radius: 3px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =====================================================
# DIRECTORIES
# =====================================================

for _d in (UPLOAD_DIR, EXPORT_DIR, CACHE_DIR, LOG_DIR):
    Path(_d).mkdir(parents=True, exist_ok=True)

# =====================================================
# SESSION IDENTITY (multi-user isolation)
# =====================================================

if "session_id" not in st.session_state:
    st.session_state["session_id"] = uuid.uuid4().hex[:12]

SESSION_ID = st.session_state["session_id"]

# Checkpoint ledger is scoped per session AND per engine track
# This prevents Track 1 hashes from skipping Track 2 runs on the same files
def _ledger_path(track_key: str) -> Path:
    safe = track_key.replace(" ", "_").replace(":", "").replace("→", "").replace("/", "")[:20]
    return Path(CACHE_DIR) / f"ledger_{SESSION_ID}_{safe}.csv"
GC_FLUSH_INTERVAL = 50

# =====================================================
# SESSION STATE DEFAULTS
# =====================================================

_DEFAULTS = {
    "candidate_profiles": [],
    "candidate_results": pd.DataFrame(),
    "jd_requirements": None,
    "processing_complete": False,
    "filter_flags": {},
    "run_stats": {},
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# =====================================================
# ENGINE INITIALIZATION
# =====================================================

status_tracker = StatusTracker()
# checkpoint_manager is instantiated per-run inside the pipeline
# because the ledger path depends on which engine track is selected
parser = ResumeParser()
report_engine = ReportingEngine()
scorer = CandidateScorer()


# =====================================================
# DOMAIN TAXONOMY LOADER (Track 1, zero LLM)
# =====================================================
# Loaded once at module import time — no Streamlit cache decorator.
# @st.cache_data caches based on function identity, NOT file contents,
# so updating domain_taxonomy.txt on disk would NOT invalidate the
# cache and the app would keep serving stale data until restart.
# The file is ~15 KB and parses in <50 ms — no cache needed.

def _load_taxonomy() -> list:
    """
    Returns flat list of (canonical, [synonyms], group) tuples.
    """
    taxonomy_path = Path(__file__).parent / "src" / "domain_taxonomy.txt"
    result = []
    if not taxonomy_path.exists():
        return result

    with open(taxonomy_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) < 3:
                continue
            group = parts[0].strip()
            canonical = parts[1].strip()
            synonyms = [s.strip().lower() for s in parts[2].split(",")]
            result.append((canonical, synonyms, group))

    return result


# Load at import time — available to all functions below
_ALL_ENTRIES = _load_taxonomy()


def detect_domain(text: str, education_summary: str = "") -> tuple:
    """
    Returns (canonical_domain, group) for the best taxonomy match.
    Pure regex, zero LLM.

    Pass 1: full resume text (broad context)
    Pass 2: education summary only (more reliable for degree-level detection)
    Fallback: "Other / Undetected" instead of blank string
    """
    text_lower = text.lower()
    edu_lower = education_summary.lower()

    best_canonical = ""
    best_group = "Other"
    best_count = 0

    for canonical, synonyms, group in _ALL_ENTRIES:
        # Count hits in full text
        count = 0
        for syn in synonyms:
            pattern = r"(?<![a-z0-9])" + re.escape(syn) + r"(?![a-z0-9])"
            if re.search(pattern, text_lower):
                count += 1
        # Double-weight hits in education summary (more reliable signal)
        if edu_lower:
            for syn in synonyms:
                pattern = r"(?<![a-z0-9])" + re.escape(syn) + r"(?![a-z0-9])"
                if re.search(pattern, edu_lower):
                    count += 2
        if count > best_count:
            best_count = count
            best_canonical = canonical
            best_group = group

    # Fallback: if nothing matched, return readable label not blank string
    if not best_canonical:
        best_canonical = "Other / Undetected"
        best_group = "Other"

    return best_canonical, best_group


def normalise_education_level(raw: str) -> str:
    """
    Maps any education string — whether a short Track 1 label like 'Masters'
    or a full Track 2 sentence like 'M.Sc. Geoinformatics from TERI School...'
    — to one of: PhD, Masters, MBA, Bachelors, Diploma, Intermediate,
    Secondary, Unspecified.

    Used only for the Education Level pie chart so both tracks produce
    a consistent, grouped visual.
    The full education string is still stored in the Excel for recruiter use.
    """
    if not raw or not str(raw).strip():
        return "Unspecified"

    s = str(raw).lower().strip()

    # Already a clean short label (Track 1 output)
    _CLEAN = {
        "phd": "PhD", "masters": "Masters", "master": "Masters",
        "bachelors": "Bachelors", "bachelor": "Bachelors",
        "mba": "MBA", "diploma": "Diploma",
        "intermediate": "Intermediate", "secondary": "Secondary",
        "unspecified": "Unspecified",
    }
    if s in _CLEAN:
        return _CLEAN[s]

    # Pattern matching on full sentences (Track 2 output)
    if re.search(r'\bph\.?\s*d\.?\b|\bdoctorate\b|\bdphil\b', s):
        return "PhD"
    if re.search(r'\bmba\b', s):
        return "MBA"
    if re.search(
        r'\bm\.?\s*tech\b|\bm\.?\s*e\.?\b|\bm\.?\s*sc\b|\bm\.?\s*a\b'
        r'|\bmaster\s+of\b|\bmaster\'?s\b|\bm\.?\s*arch\b'
        r'|\bpost\s*graduate\b|\bpg\s+diploma\b|\bpgd\b'
        r'|\bmaster.*geoinformatics\b|\bmaster.*remote\b'
        r'|\bmaster.*geography\b|\bmaster.*science\b'
        r'|\bmaster.*technology\b|\bmaster.*arts\b', s
    ):
        return "Masters"
    if re.search(
        r'\bb\.?\s*tech\b|\bb\.?\s*e\.?\b|\bb\.?\s*sc\b|\bb\.?\s*a\b'
        r'|\bbca\b|\bbba\b|\bbcom\b|\bb\.?\s*arch\b'
        r'|\bbachelor\s+of\b|\bbachelor\'?s\b'
        r'|\bundergraduate\b|\bbeng\b', s
    ):
        return "Bachelors"
    if re.search(r'\bdiploma\b|\bpolytechnic\b', s):
        return "Diploma"
    if re.search(r'\bintermediate\b|\bhsc\b|\b12th\b|\bclass\s*12\b|\bplus\s*two\b', s):
        return "Intermediate"
    if re.search(r'\bsslc\b|\bssc\b|\b10th\b|\bclass\s*10\b|\bmatriculation\b', s):
        return "Secondary"
    if re.search(r'not\s+provided|not\s+mentioned|not\s+available|n/a', s):
        return "Unspecified"

    return "Unspecified"


# =====================================================
# TRACK 1 — LOCAL KEYWORD ENGINE (zero tokens, zero keys)
# =====================================================

class LocalKeywordEngine:

    # Education section header detector
    _EDU_SECTION = re.compile(
        r"^\s*(education|academic|qualification|degree|schooling"
        r"|educational\s+background|academic\s+background)\s*[:\-]?\s*$",
        re.I,
    )

    # Non-education section headers — end of education section
    _OTHER_SECTION = re.compile(
        r"^\s*(experience|skills|projects|certifications|awards|"
        r"publications|summary|objective|profile|employment|work\s+history"
        r"|professional|internship|languages|declaration)\s*[:\-]?\s*$",
        re.I,
    )

    # Degree patterns in priority order (highest first)
    # NOTE: 'master' alone is EXCLUDED — too many false positives
    # ('master plan', 'master data', 'master bedroom').
    # Only specific degree abbreviations are matched.
    _DEGREE_PRIORITY = [
        ("PhD",       re.compile(r"\bph\.?\s*d\.?\b|\bdoctorate\b|\bd\.?\s*sc\.?\b|\bdphil\b", re.I)),
        ("Masters",   re.compile(
            r"\bm\.?\s*tech\b|\bm\.?\s*e\.?\b|\bm\.?\s*sc\.?\b|\bm\.?\s*a\.?\b"
            r"|\bmba\b|\bm\.?\s*arch\b|\bm\.?\s*des\b|\bm\.?\s*phil\b"
            r"|\bmaster\s+of\s+\w|\bmaster'?s\s+(?:degree|in\b|of\b)"
            r"|\bpost\s*graduate\b|\bpg\s+diploma\b|\bpgd\b",
            re.I,
        )),
        ("Bachelors", re.compile(
            r"\bb\.?\s*tech\b|\bb\.?\s*e\.?\b|\bb\.?\s*sc\.?\b|\bb\.?\s*a\.?\b"
            r"|\bbedu\b|\bb\.?\s*arch\b|\bb\.?\s*des\b|\bb\.?\s*com\b|\bbbm\b"
            r"|\bbca\b|\bbba\b|\bbpharm\b|\bllb\b"
            r"|\bbachelor\s+of\s+\w|\bbachelor'?s\s+(?:degree|in\b|of\b)"
            r"|\bundergraduate\b|\bunder\s*grad\b",
            re.I,
        )),
        ("Diploma",   re.compile(r"\bdiploma\b|\bpoly\s*technic\b|\bpoly\b", re.I)),
        ("Intermediate", re.compile(r"\bintermediate\b|\bhsc\b|\bclass\s*12\b|\b12th\b|\bplus\s*two\b|\b\+2\b", re.I)),
        ("Secondary", re.compile(r"\bsslc\b|\bssc\b|\bcbse\b|\bicse\b|\bmatriculation\b|\bclass\s*10\b|\b10th\b", re.I)),
    ]

    # Degree level ranking (higher = better)
    _DEGREE_RANK = {
        "PhD": 6, "Masters": 5, "Bachelors": 4,
        "Diploma": 3, "Intermediate": 2, "Secondary": 1,
    }

    @classmethod
    def _extract_education(cls, text: str) -> str:
        """
        Section-aware education extractor.
        Strategy:
          1. Try to find an EDUCATION section and scan only within it
          2. Collect ALL degree matches within the section
          3. Return the HIGHEST degree found (PhD > Masters > Bachelors > ...)
          4. False-positive guard: standalone 'master' without a degree suffix is ignored
          5. Fallback to full-text scan if no education section is found
        """
        lines = text.splitlines()
        found_degrees = []

        # --- Pass 1: Section-aware scan ---
        in_edu_section = False
        edu_lines = []

        for line in lines:
            stripped = line.strip()
            if cls._EDU_SECTION.match(stripped):
                in_edu_section = True
                continue
            if in_edu_section and cls._OTHER_SECTION.match(stripped):
                in_edu_section = False
                continue
            if in_edu_section:
                edu_lines.append(stripped)

        scan_lines = edu_lines if edu_lines else lines

        for line in scan_lines:
            ll = line.lower()
            for degree_label, pattern in cls._DEGREE_PRIORITY:
                if pattern.search(ll):
                    rank = cls._DEGREE_RANK.get(degree_label, 0)
                    found_degrees.append((rank, degree_label, line.strip()))
                    break  # only one degree label per line

        if found_degrees:
            # Return the highest-ranked degree
            found_degrees.sort(key=lambda x: -x[0])
            return found_degrees[0][1]

        # --- Pass 2: Full-text fallback (no section found) ---
        # Only match specific degree abbreviations, never bare 'master'
        for line in lines:
            ll = line.lower()
            for degree_label, pattern in cls._DEGREE_PRIORITY:
                if pattern.search(ll):
                    rank = cls._DEGREE_RANK.get(degree_label, 0)
                    found_degrees.append((rank, degree_label))
                    break

        if found_degrees:
            found_degrees.sort(key=lambda x: -x[0])
            return found_degrees[0][1]

        return "Unspecified"

    # Section headers that mark the start of work-experience content
    _EXP_SECTION = re.compile(
        r"(professional\s+experience|work\s+experience|employment|"
        r"career\s+history|work\s+history|positions?\s+held|"
        r"professional\s+background)",
        re.I,
    )
    # Lines inside experience section that mention project/study → skip
    _PROJECT_LINE = re.compile(
        r"\b(project|study|analysis|assessment|research|thesis|dissertation)\b",
        re.I,
    )
    # Explicit "X years of experience" statement
    _EXP_EXPLICIT = re.compile(
        r"(\d{1,2}(?:\.\d)?)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?"
        r"(?:work(?:ing)?\s+)?experience",
        re.I,
    )
    # Work history date ranges: "Jan 2018 – Present" or "2018-2023"
    _DATE_RANGE = re.compile(
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\.?\s*"
        r"(\d{4})\s*[-–—to]+\s*"
        r"(?:(present|current|now|till\s+date|till\s+now)|(\d{4}))",
        re.I,
    )

    @staticmethod
    def _present(term, text_lower):
        term = term.strip().lower()
        if not term:
            return False
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        return bool(re.search(pattern, text_lower))

    @classmethod
    def _match_terms(cls, terms, text_lower):
        matched, missing = [], []
        for t in terms:
            (matched if cls._present(t, text_lower) else missing).append(t.strip())
        return matched, missing

    @classmethod
    def _extract_experience(cls, text: str) -> float:
        """
        Hierarchy:
        1. Explicit "X years of experience" statement
        2. Sum of non-overlapping work-history date ranges,
           ignoring project lines
        """
        # 1. Explicit statement
        m = cls._EXP_EXPLICIT.search(text)
        if m:
            val = float(m.group(1))
            if val <= 45:
                return val

        # 2. Date arithmetic — only in experience section context
        lines = text.splitlines()
        in_exp_section = False
        periods = []  # list of (start_year, end_year)
        import datetime
        current_year = datetime.date.today().year

        for line in lines:
            if cls._EXP_SECTION.search(line):
                in_exp_section = True
                continue
            # Heuristic: new all-caps section header resets context
            if re.match(r"^[A-Z\s]{8,}$", line.strip()):
                in_exp_section = False

            if not in_exp_section:
                continue
            if cls._PROJECT_LINE.search(line):
                continue

            for m in cls._DATE_RANGE.finditer(line):
                start = int(m.group(1))
                if m.group(2):  # "present"
                    end = current_year
                else:
                    end = int(m.group(3))
                if 1970 <= start <= current_year and start < end <= current_year + 1:
                    periods.append((start, end))

        if periods:
            # Merge overlapping periods
            periods.sort()
            merged = [periods[0]]
            for s, e in periods[1:]:
                if s <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))
            total = sum(e - s for s, e in merged)
            if 0 < total <= 45:
                return float(total)

        return 0.0

    @staticmethod
    def _extract_name(text: str, file_name: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            words = line.split()
            if (
                1 < len(words) <= 5
                and all(re.fullmatch(r"[A-Za-z.'\-]+", w) for w in words)
                and not any(
                    kw in line.lower()
                    for kw in (
                        "resume", "curriculum", "vitae", "masked",
                        "email", "phone", "address", "objective",
                    )
                )
            ):
                return line.title()
        return Path(file_name).stem.replace("_", " ").replace("-", " ").title()

    @staticmethod
    def _extract_projects(text: str) -> list:
        projects = []
        for line in text.splitlines():
            clean = line.strip()
            if (
                "project" in clean.lower()
                and 15 < len(clean) < 180
                and not clean.lower().startswith("project management")
            ):
                projects.append(clean)
            if len(projects) >= 5:
                break
        return projects

    @classmethod
    def evaluate(
        cls,
        resume_text: str,
        jd_requirements: JDRequirements,
        file_name: str,
        file_hash: str,
    ) -> CandidateProfile:

        text_lower = resume_text.lower()

        matched_must, missing_must = cls._match_terms(
            jd_requirements.must_have_skills, text_lower
        )
        matched_nice, _ = cls._match_terms(
            jd_requirements.nice_to_have_skills, text_lower
        )
        matched_certs, _ = cls._match_terms(
            jd_requirements.certifications, text_lower
        )
        domain_hit = (
            [jd_requirements.domain]
            if jd_requirements.domain
            and cls._present(jd_requirements.domain, text_lower)
            else []
        )

        exp_years = cls._extract_experience(resume_text)
        education = cls._extract_education(resume_text)
        name = cls._extract_name(resume_text, file_name)
        projects = cls._extract_projects(resume_text)
        primary_domain, _ = detect_domain(resume_text, education)

        total_must = len(jd_requirements.must_have_skills)

        return CandidateProfile(
            candidate_name=name,
            education_summary=education,
            experience_years=exp_years,
            primary_domain=primary_domain,
            domain_expertise=domain_hit,
            technical_skills=matched_must + matched_nice,
            certifications=matched_certs,
            projects=projects,
            matched_requirements=matched_must,
            missing_requirements=missing_must,
            summary=(
                f"Local keyword screen: matched "
                f"{len(matched_must)}/{total_must} must-have skills, "
                f"{len(matched_nice)} nice-to-have, "
                f"{len(matched_certs)} certifications."
            ),
            score_breakdown=ScoreBreakdown(),
            fit_category="Pending",
            status="Processed",
            processing_track="Track 1 Local",
            file_name=file_name,
            file_hash=file_hash,
        )


local_engine = LocalKeywordEngine()

# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.markdown(
        "## 📡 CVRadar",
        unsafe_allow_html=False,
    )
    st.markdown("**AI Resume Screening Matrix**")
    st.markdown("---")

    # ---- API KEY (top of sidebar) ----
    st.markdown("### 🔑 API Key")

    provider_choice = st.selectbox(
        "LLM Provider",
        [GEMINI, CLAUDE, OPENAI],
        index=0,
        help="Select which AI provider to use for Track 2 / Hybrid.",
    )

    user_key = st.text_input(
        "Paste Your API Key (optional)",
        type="password",
        help=(
            "Only needed for Track 2 / Hybrid. "
            "Your key is held in this browser session only — "
            "never written to disk, logged, or shared. "
            "Leave blank to use the server's built-in key if configured."
        ),
    )

    ACTIVE_KEY = (
        user_key.strip()
        if user_key.strip()
        else (_SERVER_KEYS.get(provider_choice, "") or "")
    )

    if user_key.strip():
        st.caption("✅ Using your personal key.")
    elif ACTIVE_KEY:
        st.caption("Using server-configured key.")
    else:
        st.caption("No key — Track 1 (Local) available.")

    # ---- MODEL SELECTION ----
    st.markdown("---")
    st.markdown("### 🧠 Model")

    available_models = PROVIDER_MODELS.get(provider_choice, [])
    model_labels = [
        MODEL_DISPLAY.get(m, m) for m in available_models
    ]

    model_idx = st.selectbox(
        "Select Model",
        range(len(available_models)),
        format_func=lambda i: model_labels[i],
        index=0,
    )
    selected_model = available_models[model_idx]

    # ---- PROCESSING ENGINE ----
    st.markdown("---")
    st.markdown("### ⚙️ Processing Engine")

    engine_choice = st.radio(
        "Active Track",
        [
            "Track 1: Local Keyword (Free)",
            "Track 2: LLM Semantic",
            "Hybrid: Local Pre-Filter → LLM",
        ],
        index=0,
    )

    hybrid_cutoff = 40
    if engine_choice.startswith("Hybrid"):
        hybrid_cutoff = st.slider(
            "Hybrid cull threshold",
            min_value=10,
            max_value=80,
            value=40,
            step=5,
            help=(
                "CVs scoring below this on the free local screen "
                "are not sent to the LLM, saving tokens."
            ),
        )

    inter_delay = st.slider(
        "Inter-request delay (sec)",
        min_value=0.5,
        max_value=5.0,
        value=1.5,
        step=0.5,
        help=(
            "Pause between LLM calls. Increase if you encounter "
            "429/rate-limit errors. Has no effect on Track 1."
        ),
    )

    enable_dedupe = st.checkbox("Duplicate Detection", value=True)
    enable_checkpointing = st.checkbox("Checkpoint Recovery", value=True)

    st.markdown("---")
    page_selection = st.radio(
        "Navigate",
        ["Candidate Screening", "Batch Analytics"],
    )

    st.markdown("---")
    st.markdown("### 🛠️ Maintenance")

    if st.button("🚨 Reset This Session"):
        # Delete ALL track ledgers for this session
        for ledger_file in Path(CACHE_DIR).glob(f"ledger_{SESSION_ID}_*.csv"):
            ledger_file.unlink(missing_ok=True)
        # Clear in-memory status records
        status_tracker.reset()
        # Generate a brand new session ID
        new_sid = uuid.uuid4().hex[:12]
        st.session_state.clear()
        st.session_state["session_id"] = new_sid
        for _k, _v in _DEFAULTS.items():
            st.session_state[_k] = _v
        st.rerun()

# =====================================================
# PAGE HEADER
# =====================================================

st.title("📡 CVRadar — AI Resume Screening Matrix")

st.markdown(
    "<p class='hero-text'>"
    "Multi-provider AI screening (Gemini · Claude · OpenAI) with "
    "<b>local pre-filtering</b>, cryptographic deduplication, "
    "checkpoint recovery, and <b>session-isolated</b> storage."
    "</p>",
    unsafe_allow_html=True,
)

st.markdown(
    f"<span class='session-badge'>🔐 Session: {SESSION_ID}</span>",
    unsafe_allow_html=True,
)

# =====================================================
# ARCHITECTURE EXPANDER
# =====================================================

with st.expander("📖 System Architecture & Scoring Logic", expanded=False):

    st.markdown("### Engine Tracks")

    st.info(
        "**Track 1 — Local Keyword (Free, Zero API):** "
        "Fully offline. JD parsed locally from DOCX. Skills matched "
        "by word-boundary regex. Experience extracted via section-aware "
        "date arithmetic. Domain detected via global taxonomy (300+ streams). "
        "Semantic exclusion filters (numeric thresholds + role titles) applied locally."
    )
    st.success(
        "**Track 2 — LLM Semantic:** "
        "Deep contextual reading by your chosen LLM. Understands implied "
        "skills, career transitions, and complex eligibility rules. "
        "Filter detection is merged into a single call per CV."
    )
    st.warning(
        "**Hybrid — Local Pre-Filter → LLM:** "
        "Track 1 runs first. Only CVs clearing the threshold score are "
        "escalated to the LLM — typically 40–70% fewer API calls. "
        "On LLM failure, the local score is preserved (graceful degradation)."
    )

    st.markdown("### Scoring Weights (Hard Python — No AI Hallucination)")
    st.markdown(
        f"Skills **{SCORING_WEIGHTS['skills']}** · "
        f"Experience **{SCORING_WEIGHTS['experience']}** · "
        f"Education **{SCORING_WEIGHTS['education']}** · "
        f"Projects **{SCORING_WEIGHTS['projects']}** · "
        f"Domain **{SCORING_WEIGHTS['domain']}** · "
        f"Certifications **{SCORING_WEIGHTS['certifications']}**"
    )

    st.markdown("### Filter Layer")
    st.markdown(
        f"Priority trait detected → **+{INCLUSION_BONUS} pts**  \n"
        f"Exclusion trait detected → **−{EXCLUSION_PENALTY} pts**  \n"
        "Score clamped 0–100. Fit category recomputed.  \n"
        "Exclusion supports: numeric ranges ('less than 3 years', "
        "'freshers not required'), role titles ('Business Analyst'), "
        "and career-stage keywords."
    )

    st.markdown("### Reliability")
    st.info(
        "All LLM calls have a 45-second timeout and 5 retry attempts "
        "with exponential backoff (max 30s). On permanent failure the CV "
        "receives a Track 1 local score instead of a blank row. "
        "Checkpoint Recovery skips already-processed CVs on re-run."
    )

# =====================================================
# SESSION LEDGER BANNER
# =====================================================

if any(Path(CACHE_DIR).glob(f"ledger_{SESSION_ID}_*.csv")):
    st.info(
        "📌 **Active session ledger detected.** "
        "Previously processed CVs on the same track will be skipped. "
        "Use Reset Session to start completely clean."
    )

st.markdown("---")

# =====================================================
# DEFAULTS
# =====================================================

run_pipeline = False
uploaded_jd = None
uploaded_resumes = []
priority_input = ""
exclusion_input = ""

# =====================================================
# SCREENING PAGE
# =====================================================

if page_selection == "Candidate Screening":

    st.header("Candidate Screening")

    is_track1 = engine_choice.startswith("Track 1")
    needs_llm = not is_track1

    # ---- JD UPLOAD ----
    st.subheader("1. Job Description")

    st.caption(
        "Upload your JD as a **DOCX file** for best extraction accuracy. "
        "On Track 1 the JD is parsed locally (zero API). "
        "On Track 2 / Hybrid the same JD text is sent to the LLM."
    )

    uploaded_jd = st.file_uploader(
        "Upload Job Description (.docx)",
        type=["docx"],
        key="jd_upload",
    )

    # ---- PRIORITY & NEGATIVE FILTERS ----
    st.subheader("2. Priority & Negative Filters (Optional)")

    st.caption(
        "Leave blank to skip. Use only job-relevant criteria.  \n"
        "**Priority** examples: 'GEE experience, publications, ISRO background'  \n"
        "**Exclusion** examples: 'freshers not required, Business Analyst, "
        "less than 2 years, Data Analyst not required'"
    )

    col_inc, col_exc = st.columns(2)

    with col_inc:
        priority_input = st.text_area(
            f"🌟 Priority Traits (+{INCLUSION_BONUS} pts)",
            placeholder="GEE experience, peer-reviewed publications",
            height=110,
        )

    with col_exc:
        exclusion_input = st.text_area(
            f"🚫 Exclusion Traits (−{EXCLUSION_PENALTY} pts)",
            placeholder="freshers not required, Business Analyst, less than 2 years",
            height=110,
        )

    # ---- RESUME UPLOAD ----
    st.subheader("3. Candidate Resumes")

    uploaded_resumes = st.file_uploader(
        "Upload Resumes (PDF or DOCX, multiple allowed)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
    )

    if uploaded_resumes:
        st.success(f"**{len(uploaded_resumes)}** resumes uploaded")

    # ---- DISCLAIMERS + EXECUTE ----
    st.markdown("---")

    tc1 = st.checkbox(
        "I acknowledge that CVRadar is an AI-assisted pipeline for "
        "**preliminary screening only**. Final hiring decisions require "
        "human review and judgement."
    )

    tc2 = st.checkbox(
        "I acknowledge that LLM tracks (Track 2 / Hybrid) consume API "
        "credits from the configured key. **The author bears no "
        "responsibility** for API costs incurred, charges from failed runs, "
        "503 / rate-limit errors, model unavailability, money deducted "
        "for incomplete runs, or unsatisfactory screening results. "
        "Use of LLM tracks is entirely at my own risk."
    )

    run_pipeline = st.button(
        "🚀 Execute CVRadar Pipeline",
        use_container_width=True,
        type="primary",
        disabled=not (tc1 and tc2),
    )

# =====================================================
# PROCESSING PIPELINE
# =====================================================

if run_pipeline:

    is_track1 = engine_choice.startswith("Track 1")
    needs_llm = not is_track1

    # ---- VALIDATION ----
    if uploaded_jd is None:
        st.error("Please upload a Job Description (DOCX).")
        st.stop()

    if not uploaded_resumes:
        st.error("Please upload at least one resume.")
        st.stop()

    if needs_llm and not ACTIVE_KEY:
        st.error(
            f"🔑 {provider_choice} API key required for "
            f"{engine_choice}. Paste your key in the sidebar, "
            "or switch to Track 1: Local Keyword (free)."
        )
        st.stop()

    # ---- JD PARSING ----
    # parse_jd() gives structured requirements (for local scoring)
    # We also extract raw JD text for the LLM evaluator prompt
    with st.spinner("Parsing Job Description..."):
        uploaded_jd.seek(0)
        final_jd = parse_jd(uploaded_jd)
        # Extract raw text for LLM prompt
        uploaded_jd.seek(0)
        try:
            from docx import Document as _Doc
            _doc = _Doc(uploaded_jd)
            jd_text = "\n".join(
                p.text.strip() for p in _doc.paragraphs if p.text.strip()
            )
        except Exception:
            jd_text = " | ".join(final_jd.must_have_skills)

    with st.expander("Parsed JD Requirements"):
        st.json({
            "Must Have Skills": final_jd.must_have_skills,
            "Nice To Have Skills": final_jd.nice_to_have_skills,
            "Education": final_jd.education,
            "Experience": final_jd.experience,
            "Domain": final_jd.domain,
            "Certifications": final_jd.certifications,
        })

    st.session_state["jd_requirements"] = final_jd

    # ---- PROVIDER SETUP ----
    provider = None
    evaluator = None

    if needs_llm:
        provider = LLMProvider(
            provider=provider_choice,
            model=selected_model,
            api_key=ACTIVE_KEY,
            inter_request_delay=inter_delay,
        )

        # Health check before burning through 300+ CVs
        with st.spinner(
            f"Checking {provider_choice} ({selected_model}) availability..."
        ):
            ok, msg = provider.health_check()

        if ok:
            st.success(f"✅ {msg}")
        else:
            st.warning(
                f"⚠️ {msg}  \n"
                "The pipeline will continue — failed LLM calls will "
                "fall back to Track 1 local scoring automatically."
            )

        evaluator = CandidateEvaluator(provider=provider)

    # ---- FILTER ENGINE ----
    filter_engine = FilterEngine(
        priority_traits=priority_input,
        exclusion_traits=exclusion_input,
    )

    # ---- CHECKPOINT (track-scoped ledger) ----
    # Each engine track gets its own ledger so Track 1 hashes
    # never block a Track 2 run on the same files
    track_key = engine_choice.split(":")[0].strip()
    SESSION_LEDGER = _ledger_path(track_key)
    checkpoint_manager = CheckpointManager(SESSION_LEDGER)

    processed_hashes = set()
    if enable_checkpointing:
        processed_hashes = checkpoint_manager.processed_hashes()

    seen_hashes = set()

    # ---- MAIN LOOP ----
    total = len(uploaded_resumes)
    progress_bar = st.progress(0)
    status_ph = st.empty()

    candidate_profiles = []
    failed_resumes = []
    filter_flag_map = {}
    llm_calls = 0
    degraded_count = 0
    culled_count = 0

    for idx, resume_file in enumerate(uploaded_resumes):

        file_name = resume_file.name
        file_hash = None

        try:
            status_ph.info(
                f"**{idx + 1}/{total}** → {file_name}"
            )

            parsed = parser.process_resume(resume_file, file_name)
            file_hash = parsed["file_hash"]
            resume_text = parsed["resume_text"]

            # Checkpoint skip
            if enable_checkpointing and file_hash in processed_hashes:
                status_tracker.update(file_hash, "Skipped", "Checkpoint")
                continue

            # Within-batch dedupe
            if enable_dedupe and file_hash in seen_hashes:
                status_tracker.update(file_hash, "Duplicate")
                continue

            seen_hashes.add(file_hash)
            status_tracker.update(file_hash, "Processing")

            flags = None

            # ---- ENGINE DISPATCH ----

            if is_track1:

                profile = local_engine.evaluate(
                    resume_text, final_jd, file_name, file_hash
                )
                if filter_engine.active:
                    flags = filter_engine.keyword_flags(
                        resume_text, profile.experience_years
                    )

            elif engine_choice.startswith("Track 2"):

                profile, flags = evaluator.evaluate(
                    resume_text=resume_text,
                    jd_text=jd_text,
                    jd_requirements=final_jd,
                    file_name=file_name,
                    file_hash=file_hash,
                    priority_traits=priority_input,
                    exclusion_traits=exclusion_input,
                )
                llm_calls += 1

                if profile is None:
                    # Graceful degradation to Track 1
                    profile = local_engine.evaluate(
                        resume_text, final_jd, file_name, file_hash
                    )
                    profile.processing_track = "Degraded to Local"
                    if filter_engine.active:
                        flags = filter_engine.keyword_flags(
                            resume_text, profile.experience_years
                        )
                    degraded_count += 1

            else:  # Hybrid

                local_profile = local_engine.evaluate(
                    resume_text, final_jd, file_name, file_hash
                )
                local_profile, _ = scorer.score_candidate(
                    local_profile, final_jd
                )
                local_score = local_profile.score_breakdown.final_score

                if local_score < hybrid_cutoff:
                    culled_count += 1
                    local_profile.status = "Culled"
                    local_profile.processing_track = "Hybrid-Culled"
                    local_profile.processing_notes = (
                        f"Hybrid pre-filter: local score {local_score} "
                        f"< threshold {hybrid_cutoff}."
                    )
                    if filter_engine.active:
                        flags = filter_engine.keyword_flags(
                            resume_text, local_profile.experience_years
                        )
                        local_profile = filter_engine.apply(
                            local_profile, flags
                        )
                        filter_flag_map[file_hash] = flags
                    candidate_profiles.append(local_profile)
                    status_tracker.update(file_hash, "Culled")
                    checkpoint_manager.save_record({
                        "file_hash": file_hash,
                        "candidate_name": local_profile.candidate_name,
                        "status": "Culled",
                    })
                    continue

                profile, flags = evaluator.evaluate(
                    resume_text=resume_text,
                    jd_text=jd_text,
                    jd_requirements=final_jd,
                    file_name=file_name,
                    file_hash=file_hash,
                    priority_traits=priority_input,
                    exclusion_traits=exclusion_input,
                )
                llm_calls += 1

                if profile is None:
                    profile = local_engine.evaluate(
                        resume_text, final_jd, file_name, file_hash
                    )
                    profile.processing_track = "Degraded to Local"
                    if filter_engine.active:
                        flags = filter_engine.keyword_flags(
                            resume_text, profile.experience_years
                        )
                    degraded_count += 1

            # ---- SCORING ----
            profile, explanation = scorer.score_candidate(
                profile, final_jd
            )
            profile.processing_notes = (
                explanation + "\n" + profile.processing_notes
            ).strip()

            # ---- FILTER APPLY ----
            if flags is not None:
                profile = filter_engine.apply(profile, flags)
                filter_flag_map[file_hash] = flags

            candidate_profiles.append(profile)

            status_tracker.update(file_hash, "Success")
            checkpoint_manager.save_record({
                "file_hash": file_hash,
                "candidate_name": profile.candidate_name,
                "status": "Success",
            })

        except Exception as e:
            failed_resumes.append({
                "file_name": file_name,
                "error": str(e),
            })
            status_tracker.update(
                file_hash if file_hash else file_name,
                "Failed",
                str(e),
            )

        finally:
            progress_bar.progress((idx + 1) / total)
            if (idx + 1) % GC_FLUSH_INTERVAL == 0:
                gc.collect()

    status_ph.empty()

    # ---- STORE ----
    st.session_state["candidate_profiles"] = candidate_profiles
    st.session_state["processing_complete"] = True
    st.session_state["filter_flags"] = filter_flag_map
    st.session_state["run_stats"] = {
        "total": total,
        "processed": len(candidate_profiles),
        "llm_calls": llm_calls,
        "degraded": degraded_count,
        "culled": culled_count,
        "failed": len(failed_resumes),
    }

    # ---- SUMMARY ----
    st.success(f"**{len(candidate_profiles)}** candidates processed.")

    stats = st.session_state["run_stats"]
    if needs_llm:
        st.info(
            f"💸 **API usage:** {stats['llm_calls']} LLM calls | "
            f"{stats['degraded']} degraded to local | "
            f"{stats['culled']} culled pre-LLM"
        )

    if failed_resumes:
        st.warning(f"{len(failed_resumes)} resumes failed entirely.")
        with st.expander("Failed Resumes"):
            st.dataframe(pd.DataFrame(failed_resumes))

    with st.expander("Processing Status Log"):
        st.dataframe(
            status_tracker.to_dataframe(),
            use_container_width=True,
        )

# =====================================================
# RESULTS & ANALYTICS (Screening page)
# =====================================================

if (
    page_selection == "Candidate Screening"
    and st.session_state.get("processing_complete", False)
):

    profiles = st.session_state["candidate_profiles"]

    if not profiles:
        st.info("No candidates were processed in this session.")

    else:

        result_df = report_engine.build_dataframe(profiles)
        result_df = report_engine.rank_candidates(result_df)
        st.session_state["candidate_results"] = result_df

        # ---- SUMMARY METRICS ----
        summary = report_engine.executive_summary(result_df)

        st.markdown("---")
        st.header("Screening Results")

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total", summary.get("total_candidates", 0))
        m2.metric("Avg Score", summary.get("average_score", 0))
        m3.metric("Highest", summary.get("highest_score", 0))
        m4.metric("Shortlisted ≥80", summary.get("shortlisted", 0))
        m5.metric("Review 65–79", summary.get("review", 0))
        m6.metric("Rejected <65", summary.get("rejected", 0))

        # ---- FIT BREAKDOWN ----
        st.markdown("---")

        fc = result_df["Fit Category"].value_counts().reset_index()
        fc.columns = ["Fit Category", "Count"]

        cat_colours = {
            "Exceptional Fit": "#27AE60",
            "Strong Fit": "#2ECC71",
            "Moderate Fit": "#F39C12",
            "Potential Fit": "#E67E22",
            "Low Fit": "#E74C3C",
        }

        c1, c2 = st.columns(2)

        with c1:
            fig_fit = px.pie(
                fc,
                values="Count",
                names="Fit Category",
                title="Candidate Pipeline Distribution",
                hole=0.4,
                color="Fit Category",
                color_discrete_map=cat_colours,
            )
            fig_fit.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f0f0f0",
            )
            st.plotly_chart(fig_fit, use_container_width=True)

        with c2:
            fig_score = px.histogram(
                result_df,
                x="Final Score",
                nbins=20,
                title="Score Distribution",
                color_discrete_sequence=["#00b4d8"],
            )
            fig_score.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f0f0f0",
            )
            st.plotly_chart(fig_score, use_container_width=True)

        # ---- DOMAIN / STREAM ANALYTICS ----
        st.markdown("---")
        st.subheader("Stream & Education Analytics")

        if "Primary Domain" in result_df.columns:

            # Replace blank / empty domain labels for display
            display_df = result_df.copy()
            display_df["Primary Domain"] = display_df[
                "Primary Domain"
            ].replace({"": "Other / Undetected", None: "Other / Undetected"})
            display_df["Primary Domain"] = display_df[
                "Primary Domain"
            ].fillna("Other / Undetected")

            dom_all = (
                display_df["Primary Domain"]
                .value_counts()
                .head(15)
                .reset_index()
            )
            dom_all.columns = ["Stream", "Total Applicants"]

            d1, d2 = st.columns(2)

            with d1:
                fig_dom = px.bar(
                    dom_all,
                    x="Total Applicants",
                    y="Stream",
                    orientation="h",
                    title="Streams: Who Applied",
                    color="Total Applicants",
                    color_continuous_scale="Blues",
                    text="Total Applicants",
                )
                fig_dom.update_traces(textposition="outside")
                fig_dom.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#f0f0f0",
                    font_size=12,
                    yaxis={"categoryorder": "total ascending"},
                    margin={"l": 10, "r": 60, "t": 40, "b": 10},
                    showlegend=False,
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_dom, use_container_width=True)

            with d2:
                # Education Level pie chart
                # normalise_education_level() handles both Track 1 short
                # labels ("Masters") and Track 2 full sentences
                # ("M.Sc. Geoinformatics from TERI School...")
                edu_colours = {
                    "PhD":           "#8B5CF6",
                    "Masters":       "#06B6D4",
                    "Bachelors":     "#10B981",
                    "MBA":           "#F59E0B",
                    "Diploma":       "#F97316",
                    "Intermediate":  "#6B7280",
                    "Secondary":     "#9CA3AF",
                    "Unspecified":   "#374151",
                }
                edu_normalised = (
                    display_df["Education"]
                    .apply(normalise_education_level)
                    .value_counts()
                    .reset_index()
                )
                edu_normalised.columns = ["Education Level", "Count"]

                fig_edu = px.pie(
                    edu_normalised,
                    values="Count",
                    names="Education Level",
                    title="Education Level Breakdown",
                    hole=0.4,
                    color="Education Level",
                    color_discrete_map=edu_colours,
                )
                fig_edu.update_traces(
                    textposition="inside",
                    textinfo="percent+label",
                    textfont_size=12,
                )
                fig_edu.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#f0f0f0",
                    font_size=12,
                    showlegend=True,
                    legend=dict(
                        font=dict(color="#f0f0f0", size=11),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    margin={"l": 10, "r": 10, "t": 40, "b": 10},
                )
                st.plotly_chart(fig_edu, use_container_width=True)

        # ---- SKILLS ANALYTICS ----
        st.markdown("---")
        st.subheader("Skills Analysis")

        sk1, sk2 = st.columns(2)

        with sk1:
            # Top skills matched across all CVs
            from collections import Counter
            all_matched = []
            for p in profiles:
                all_matched.extend(p.matched_requirements)
            if all_matched:
                skill_counts = (
                    pd.DataFrame(
                        Counter(all_matched).most_common(12),
                        columns=["Skill", "CVs Matched"],
                    )
                )
                fig_sk = px.bar(
                    skill_counts,
                    x="CVs Matched",
                    y="Skill",
                    orientation="h",
                    title="Top Skills Found Across CVs",
                    color="CVs Matched",
                    color_continuous_scale="Teal",
                    text="CVs Matched",
                )
                fig_sk.update_traces(textposition="outside")
                fig_sk.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#f0f0f0",
                    font_size=12,
                    yaxis={"categoryorder": "total ascending"},
                    margin={"l": 10, "r": 60, "t": 40, "b": 10},
                    showlegend=False,
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_sk, use_container_width=True)
            else:
                st.info("No skills were matched on this run.")

        with sk2:
            # Most commonly missing skills (talent gap)
            all_missing = []
            for p in profiles:
                all_missing.extend(p.missing_requirements)
            if all_missing:
                missing_counts = (
                    pd.DataFrame(
                        Counter(all_missing).most_common(12),
                        columns=["Skill", "CVs Missing"],
                    )
                )
                fig_miss = px.bar(
                    missing_counts,
                    x="CVs Missing",
                    y="Skill",
                    orientation="h",
                    title="Skills Most Commonly Missing (Talent Gap)",
                    color="CVs Missing",
                    color_continuous_scale="Reds",
                    text="CVs Missing",
                )
                fig_miss.update_traces(textposition="outside")
                fig_miss.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#f0f0f0",
                    font_size=12,
                    yaxis={"categoryorder": "total ascending"},
                    margin={"l": 10, "r": 60, "t": 40, "b": 10},
                    showlegend=False,
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_miss, use_container_width=True)
            else:
                st.info("No missing skills recorded.")

        # ---- TRACK BREAKDOWN (only meaningful on Hybrid/Track 2) ----
        track_counts = (
            result_df["Processing Track"]
            .value_counts()
            .reset_index()
        )
        track_counts.columns = ["Track", "Count"]

        if len(track_counts) > 1:
            # Only show when multiple tracks are present (Hybrid / degradation)
            st.markdown("---")
            fig_track = px.bar(
                track_counts,
                x="Track",
                y="Count",
                title="Processing Track Breakdown",
                color="Track",
                color_discrete_sequence=[
                    "#00b4d8", "#27AE60", "#E67E22", "#E74C3C"
                ],
                text="Count",
            )
            fig_track.update_traces(textposition="outside")
            fig_track.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#f0f0f0",
                font_size=12,
                showlegend=False,
                margin={"l": 10, "r": 40, "t": 40, "b": 10},
            )
            st.plotly_chart(fig_track, use_container_width=True)

        # ---- EXPORT ----
        st.markdown("---")
        st.subheader("Download Results")

        excel_bytes = report_engine.export_excel(result_df)

        st.download_button(
            label="⬇️ Download Excel Report",
            data=excel_bytes,
            file_name=f"cvradar_report_{SESSION_ID}.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
            use_container_width=True,
        )

        with st.expander("Preview Full Results Table"):
            st.dataframe(result_df, use_container_width=True)

# =====================================================
# BATCH ANALYTICS PAGE
# =====================================================

elif page_selection == "Batch Analytics":

    st.header("Batch Analytics")

    st.markdown(
        "Upload multiple CVRadar Excel reports (from previous runs) "
        "to generate cross-batch talent analytics."
    )

    uploaded_reports = st.file_uploader(
        "Upload CVRadar Excel Reports (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        key="batch_reports",
    )

    if uploaded_reports:

        with st.spinner("Merging reports..."):
            merged_df = report_engine.merge_batch_reports(uploaded_reports)

        if merged_df.empty:
            st.warning("No valid CVRadar reports found in the uploaded files.")

        else:

            st.success(
                f"**{len(merged_df)}** candidates across "
                f"**{len(uploaded_reports)}** reports."
            )

            # ---- BATCH KPIs ----
            avg_score = round(merged_df["Final Score"].mean(), 1)
            shortlisted = len(merged_df[merged_df["Final Score"] >= 80])
            highest = int(merged_df["Final Score"].max())
            lowest = int(merged_df["Final Score"].min())

            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Total Candidates", len(merged_df))
            b2.metric("Average Score", avg_score)
            b3.metric("Highest Score", highest)
            b4.metric("Shortlisted ≥80", shortlisted)

            st.markdown("---")

            # ---- PIPELINE DISTRIBUTION ----
            c1, c2 = st.columns(2)

            with c1:
                cat_colours = {
                    "Exceptional Fit": "#27AE60",
                    "Strong Fit": "#2ECC71",
                    "Moderate Fit": "#F39C12",
                    "Potential Fit": "#E67E22",
                    "Low Fit": "#E74C3C",
                }
                fc = merged_df["Fit Category"].value_counts().reset_index()
                fc.columns = ["Fit Category", "Count"]
                fig1 = px.pie(
                    fc,
                    values="Count",
                    names="Fit Category",
                    hole=0.4,
                    title="Pipeline Distribution (All Batches)",
                    color="Fit Category",
                    color_discrete_map=cat_colours,
                )
                fig1.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#f0f0f0",
                )
                st.plotly_chart(fig1, use_container_width=True)

            with c2:
                fig2 = px.histogram(
                    merged_df,
                    x="Final Score",
                    nbins=20,
                    title="Score Distribution (All Batches)",
                    color_discrete_sequence=["#00b4d8"],
                )
                fig2.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#f0f0f0",
                )
                st.plotly_chart(fig2, use_container_width=True)

            # ---- DOMAIN: WHO APPLIED + EDUCATION BREAKDOWN ----
            st.markdown("---")

            if "Primary Domain" in merged_df.columns:

                # Clean blank labels
                mdf = merged_df.copy()
                mdf["Primary Domain"] = mdf["Primary Domain"].replace(
                    {"": "Other / Undetected", None: "Other / Undetected"}
                ).fillna("Other / Undetected")

                d1, d2 = st.columns(2)

                dom_all = (
                    mdf["Primary Domain"]
                    .value_counts()
                    .head(15)
                    .reset_index()
                )
                dom_all.columns = ["Stream", "Total"]

                with d1:
                    fig3 = px.bar(
                        dom_all,
                        x="Total",
                        y="Stream",
                        orientation="h",
                        title="All Streams: Who Applied",
                        color="Total",
                        color_continuous_scale="Blues",
                        text="Total",
                    )
                    fig3.update_traces(textposition="outside")
                    fig3.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#f0f0f0",
                        font_size=12,
                        yaxis={"categoryorder": "total ascending"},
                        margin={"l": 10, "r": 60, "t": 40, "b": 10},
                        showlegend=False,
                        coloraxis_showscale=False,
                    )
                    st.plotly_chart(fig3, use_container_width=True)

                with d2:
                    edu_colours = {
                        "PhD":           "#8B5CF6",
                        "Masters":       "#06B6D4",
                        "Bachelors":     "#10B981",
                        "MBA":           "#F59E0B",
                        "Diploma":       "#F97316",
                        "Intermediate":  "#6B7280",
                        "Secondary":     "#9CA3AF",
                        "Unspecified":   "#374151",
                    }
                    if "Education" in mdf.columns:
                        edu_normalised = (
                            mdf["Education"]
                            .apply(normalise_education_level)
                            .value_counts()
                            .reset_index()
                        )
                        edu_normalised.columns = ["Education Level", "Count"]
                        fig_edu = px.pie(
                            edu_normalised,
                            values="Count",
                            names="Education Level",
                            title="Education Level Breakdown",
                            hole=0.4,
                            color="Education Level",
                            color_discrete_map=edu_colours,
                        )
                        fig_edu.update_traces(
                            textposition="inside",
                            textinfo="percent+label",
                            textfont_size=12,
                        )
                        fig_edu.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            font_color="#f0f0f0",
                            font_size=12,
                            showlegend=True,
                            legend=dict(
                                font=dict(color="#f0f0f0", size=11),
                                bgcolor="rgba(0,0,0,0)",
                            ),
                            margin={"l": 10, "r": 10, "t": 40, "b": 10},
                        )
                        st.plotly_chart(fig_edu, use_container_width=True)

            # ---- HIGHEST / LOWEST ----
            st.markdown("---")

            hl1, hl2 = st.columns(2)

            top5 = merged_df.nlargest(5, "Final Score")[
                ["File Name", "Candidate Name", "Primary Domain",
                 "Final Score", "Fit Category"]
            ]
            bot5 = merged_df.nsmallest(5, "Final Score")[
                ["File Name", "Candidate Name", "Primary Domain",
                 "Final Score", "Fit Category"]
            ]

            with hl1:
                st.subheader("🏆 Top 5 Scorers")
                st.dataframe(top5, use_container_width=True, hide_index=True)

            with hl2:
                st.subheader("⚠️ Bottom 5 Scorers")
                st.dataframe(bot5, use_container_width=True, hide_index=True)

            # ---- DOWNLOAD MERGED ----
            st.markdown("---")

            merged_excel = report_engine.export_excel(merged_df)

            st.download_button(
                label="⬇️ Download Merged Report",
                data=merged_excel,
                file_name=f"cvradar_merged_{SESSION_ID}.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

            with st.expander("Preview Merged Data"):
                st.dataframe(merged_df, use_container_width=True)

# =====================================================
# FOOTER
# =====================================================

st.markdown("---")
st.caption(
    f"📡 CVRadar v3 | AI Resume Screening Matrix | Session {SESSION_ID}"
)
