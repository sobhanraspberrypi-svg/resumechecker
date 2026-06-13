"""
CVRadar
Inclusion / Exclusion Filter Engine
src/filters.py

v3 enhancements:
- Semantic exclusion interpreter: parses numeric thresholds from
  natural language ("freshers not required", "less than 3 years",
  "senior candidates only", "Business Analyst not required")
- Keyword-to-numeric mapping for common career-stage phrases
- Role-title exclusion: checks designation lines in CV
- Track 1 uses keyword_flags() (free, no LLM)
- Track 2 / Hybrid: flags are merged into the evaluator call; this
  module only applies the deterministic score math
- No LLM calls in this module at all

Scoring philosophy (unchanged):
  Priority trait found   -> +15 (once, flat)
  Exclusion trait found  -> -30 (once, flat, clamped to 0-100)
"""

import re
from pydantic import BaseModel, Field
from config import FIT_CATEGORIES


INCLUSION_BONUS = 15
EXCLUSION_PENALTY = 30

# =====================================================
# KEYWORD-TO-NUMERIC MAPPINGS
# Career stage phrases that imply an experience range
# =====================================================

_KEYWORD_NUMERIC = {
    # Experience too LOW (exclude below threshold)
    "fresher": ("lt", 1),
    "freshers": ("lt", 1),
    "fresh graduate": ("lt", 1),
    "fresh graduates": ("lt", 1),
    "entry level": ("lt", 2),
    "entry-level": ("lt", 2),
    "trainee": ("lt", 2),
    "intern": ("lt", 1),
    "no experience": ("lt", 1),
    "zero experience": ("lt", 1),
    "0 years": ("lt", 1),

    # Experience too HIGH (exclude above threshold)
    "very senior": ("gt", 15),
    "highly senior": ("gt", 15),
    "director level": ("gt", 12),
    "vp level": ("gt", 12),
    "c-level": ("gt", 15),
    "chief level": ("gt", 15),
    "retired": ("gt", 30),
    "retirement": ("gt", 30),
}

# Numeric range patterns in exclusion text
# "less than 3 years", "under 2 years", "below 5 years"
_LT_PATTERN = re.compile(
    r"(?:less\s+than|under|below|fewer\s+than|<)\s*(\d{1,2})\s*(?:\+)?\s*years?",
    re.I,
)
# "more than 10 years", "over 8 years", "above 15 years"
_GT_PATTERN = re.compile(
    r"(?:more\s+than|over|above|greater\s+than|>)\s*(\d{1,2})\s*(?:\+)?\s*years?",
    re.I,
)
# "1 to 3 years", "1-3 years" (range to exclude)
_RANGE_PATTERN = re.compile(
    r"(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})\s*years?",
    re.I,
)
# "minimum X years" — implies exclude below X
_MIN_PATTERN = re.compile(
    r"minimum\s+(\d{1,2})\s*(?:\+)?\s*years?",
    re.I,
)
# "X+ years"
_PLUS_PATTERN = re.compile(
    r"(\d{1,2})\s*\+\s*years?",
    re.I,
)


# =====================================================
# DATA MODEL
# =====================================================

class FilterFlags(BaseModel):
    inclusion_matched: bool = Field(default=False)
    exclusion_violated: bool = Field(default=False)
    reason: str = Field(default="")


# =====================================================
# FILTER ENGINE
# =====================================================

class FilterEngine:

    def __init__(self, priority_traits: str = "", exclusion_traits: str = ""):
        self.priority = (priority_traits or "").strip()
        self.exclusion = (exclusion_traits or "").strip()

        # Pre-parse exclusion rules once
        self._exc_rules = self._parse_exclusion_rules(self.exclusion)

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    @property
    def active(self):
        return bool(self.priority or self.exclusion)

    # --------------------------------------------------
    # TERM UTILITIES
    # --------------------------------------------------

    @staticmethod
    def _present(term: str, text_lower: str) -> bool:
        term = term.strip().lower()
        if not term:
            return False
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        return bool(re.search(pattern, text_lower))

    @staticmethod
    def _terms(raw: str) -> list:
        return [t.strip() for t in re.split(r"[,;]", raw) if t.strip()]

    # --------------------------------------------------
    # EXCLUSION RULE PARSER
    # Converts natural language into executable rules
    # --------------------------------------------------

    def _parse_exclusion_rules(self, exclusion_text: str) -> list:
        """
        Returns a list of rule dicts:
          {"type": "exp_lt", "value": 3}       # exclude if exp < 3
          {"type": "exp_gt", "value": 10}      # exclude if exp > 10
          {"type": "exp_range", "lo": 1, "hi": 6}  # exclude if 1 <= exp <= 6
          {"type": "keyword", "term": "business analyst"}  # title/role exclusion
        """
        if not exclusion_text:
            return []

        rules = []
        text_lower = exclusion_text.lower()

        # 1. Keyword-to-numeric mappings
        for phrase, (op, val) in _KEYWORD_NUMERIC.items():
            if phrase in text_lower:
                rtype = "exp_lt" if op == "lt" else "exp_gt"
                rules.append({"type": rtype, "value": val, "label": phrase})

        # 2. "less than X years"
        for m in _LT_PATTERN.finditer(exclusion_text):
            rules.append({
                "type": "exp_lt",
                "value": int(m.group(1)),
                "label": m.group(0),
            })

        # 3. "more than X years"
        for m in _GT_PATTERN.finditer(exclusion_text):
            rules.append({
                "type": "exp_gt",
                "value": int(m.group(1)),
                "label": m.group(0),
            })

        # 4. "X to Y years" range exclusion
        for m in _RANGE_PATTERN.finditer(exclusion_text):
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo < hi:
                rules.append({
                    "type": "exp_range",
                    "lo": lo,
                    "hi": hi,
                    "label": m.group(0),
                })

        # 5. "minimum X years" — exclude below X
        for m in _MIN_PATTERN.finditer(exclusion_text):
            rules.append({
                "type": "exp_lt",
                "value": int(m.group(1)),
                "label": m.group(0),
            })

        # 6. "X+ years" standing alone (minimum) — exclude below X
        for m in _PLUS_PATTERN.finditer(exclusion_text):
            val = int(m.group(1))
            if val > 1:  # avoid catching "1+ year" in role names
                rules.append({
                    "type": "exp_lt",
                    "value": val,
                    "label": m.group(0),
                })

        # 7. Remaining comma-separated terms that are not numeric phrases
        # → treated as role/title keyword exclusions
        for term in self._terms(exclusion_text):
            term_lower = term.lower()
            # Skip if this term is already captured by numeric rules
            already_numeric = any(
                r.get("label", "").lower() == term_lower
                or term_lower in r.get("label", "").lower()
                for r in rules
            )
            is_numeric_phrase = bool(
                _LT_PATTERN.search(term)
                or _GT_PATTERN.search(term)
                or _RANGE_PATTERN.search(term)
                or _MIN_PATTERN.search(term)
            )
            if not already_numeric and not is_numeric_phrase:
                clean = re.sub(
                    r"\b(not\s+required|not\s+needed|exclude|no\s+)\b",
                    "",
                    term_lower,
                ).strip()
                if clean and len(clean) > 2:
                    rules.append({"type": "keyword", "term": clean})

        return rules

    # --------------------------------------------------
    # EXPERIENCE RULE EVALUATION
    # --------------------------------------------------

    def _check_experience_rules(self, experience_years: float) -> list:
        """Returns list of triggered rule labels."""
        triggered = []
        for rule in self._exc_rules:
            rtype = rule["type"]
            if rtype == "exp_lt" and experience_years < rule["value"]:
                triggered.append(
                    f"exp {experience_years}y < required {rule['value']}y"
                )
            elif rtype == "exp_gt" and experience_years > rule["value"]:
                triggered.append(
                    f"exp {experience_years}y > max {rule['value']}y"
                )
            elif rtype == "exp_range":
                lo, hi = rule["lo"], rule["hi"]
                if lo <= experience_years <= hi:
                    triggered.append(
                        f"exp {experience_years}y in excluded range {lo}-{hi}y"
                    )
        return triggered

    # --------------------------------------------------
    # KEYWORD / TITLE RULE EVALUATION
    # --------------------------------------------------

    def _check_keyword_rules(self, resume_text: str, experience_years: float) -> list:
        """Returns list of triggered keyword rule labels."""
        triggered = []
        text_lower = resume_text.lower()
        for rule in self._exc_rules:
            if rule["type"] == "keyword":
                term = rule["term"]
                if self._present(term, text_lower):
                    triggered.append(f"role/trait match: '{term}'")
        return triggered

    # --------------------------------------------------
    # PRIORITY KEYWORD CHECK
    # --------------------------------------------------

    def _check_priority(self, resume_text: str) -> list:
        text_lower = resume_text.lower()
        hits = []
        for term in self._terms(self.priority):
            if self._present(term.lower(), text_lower):
                hits.append(term)
        return hits

    # --------------------------------------------------
    # MAIN KEYWORD FLAGS (Track 1 entry point)
    # --------------------------------------------------

    def keyword_flags(self, resume_text: str, experience_years: float = 0.0) -> FilterFlags:
        """
        Pure local detection — no LLM.
        experience_years should be passed in from the local extractor.
        """
        inc_hits = self._check_priority(resume_text)

        exc_exp = self._check_experience_rules(experience_years)
        exc_kw = self._check_keyword_rules(resume_text, experience_years)
        exc_hits = exc_exp + exc_kw

        parts = []
        if inc_hits:
            parts.append(f"Priority: {', '.join(inc_hits)}")
        if exc_hits:
            parts.append(f"Exclusion: {'; '.join(exc_hits)}")
        if not parts:
            parts.append("No filter traits detected.")

        return FilterFlags(
            inclusion_matched=bool(inc_hits),
            exclusion_violated=bool(exc_hits),
            reason=" | ".join(parts),
        )

    # --------------------------------------------------
    # DETERMINISTIC SCORE ADJUSTMENT
    # --------------------------------------------------

    @staticmethod
    def _fit_category(score: int) -> str:
        for category, (low, high) in FIT_CATEGORIES.items():
            if low <= score <= high:
                return category
        return "Low Fit"

    def apply(self, profile, flags: FilterFlags) -> object:
        """
        Applies ±adjustment to profile.score_breakdown.final_score.
        Recomputes fit_category. Appends to processing_notes.
        Returns the mutated profile.
        """
        if flags is None:
            return profile

        base = profile.score_breakdown.final_score
        adjustment = 0
        notes = []

        if flags.inclusion_matched:
            adjustment += INCLUSION_BONUS
            notes.append(f"+{INCLUSION_BONUS} priority bonus")

        if flags.exclusion_violated:
            adjustment -= EXCLUSION_PENALTY
            notes.append(f"-{EXCLUSION_PENALTY} exclusion penalty")

        if adjustment != 0:
            adjusted = max(0, min(100, base + adjustment))
            profile.score_breakdown.final_score = adjusted
            profile.fit_category = self._fit_category(adjusted)

            profile.processing_notes = (
                f"{profile.processing_notes}\n"
                f"FILTER: base {base} {' '.join(notes)} → final {adjusted}. "
                f"{flags.reason}"
            ).strip()

        elif flags.reason and "No filter" not in flags.reason:
            profile.processing_notes = (
                f"{profile.processing_notes}\n"
                f"FILTER: no score change. {flags.reason}"
            ).strip()

        return profile
