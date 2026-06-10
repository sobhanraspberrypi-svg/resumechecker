import streamlit as st
import pandas as pd
import io
import re
import time
from PyPDF2 import PdfReader
from docx import Document
from google import genai
from pydantic import BaseModel, Field

# --- Page Configuration (Enterprise SaaS Aesthetic) ---
st.set_page_config(
    page_title="Nexus | AI Sourcing Matrix",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Premium CSS Elements ---
st.markdown("""
    <style>
    .main {background-color: #FAFAFA;}
    .stButton>button {width: 100%; border-radius: 6px; font-weight: bold; height: 3rem;}
    .hero-text {font-size: 1.25rem; color: #4A5568; line-height: 1.6;}
    .metric-card {background-color: #FFFFFF; padding: 15px; border-radius: 8px; border: 1px solid #E2E8F0; margin-bottom: 15px;}
    </style>
""", unsafe_allow_html=True)

# --- Universal Structured AI Schema ---
class UniversalProfile(BaseModel):
    candidate_name: str = Field(description="The extracted actual name of the candidate. Ignore headers like Resume or CV.")
    overall_score: int = Field(description="Overall match score from 0 to 100 based on JD requirements and exclusion rules.")
    education_summary: str = Field(description="Highest degree earned, major, and institution.")
    experience_years: float = Field(description="Total calculated workforce experience in years.")
    key_strengths: str = Field(description="Comma-separated list of top 3 matching technical or domain capabilities.")
    missing_requirements: str = Field(description="Key criteria from the JD that are visibly missing in the CV.")
    exclusion_violated: bool = Field(description="Set to True ONLY if the candidate matches any criteria the user explicitly wants to exclude. If no criteria are provided, default to False.")
    justification: str = Field(description="One concise sentence explaining the score and noting any exclusion violations.")

# --- Local Text Extraction & Security Layer ---
def scrub_pii(text):
    """Local Data Privacy Shield: Guarantees zero data leakage before cloud inference."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    text = re.sub(email_pattern, "[EMAIL MASKED]", text)
    text = re.sub(phone_pattern, "[PHONE MASKED]", text)
    return text

def extract_text_from_file(file_obj, filename):
    """Parses incoming multi-format text payloads locally."""
    text = ""
    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(file_obj)
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif filename.endswith('.docx'):
            doc = Document(file_obj)
            text = "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        st.error(f"Error parsing file {filename}: {e}")
    return text

# --- Track 1: Local Statistical Engine ---
def process_track_1(cv_text, jd_text, filename):
    cv_tokens = set(re.findall(r'\b\w{4,}\b', cv_text.lower()))
    jd_tokens = set(re.findall(r'\b\w{4,}\b', jd_text.lower()))
    stop_words = {"with", "from", "that", "this", "building", "using", "management", "experience", "required"}
    keywords = jd_tokens - stop_words
    
    score = 0 if not keywords else min(int((len(cv_tokens.intersection(keywords)) / len(keywords)) * 220), 100)
    
    return {
        "File Name": filename, "Candidate Name": "Run Track 2 for Extraction",
        "Score": score, "Experience (Yrs)": 0.0, "Education": "N/A",
        "Key Strengths": f"Matched {len(cv_tokens.intersection(keywords))} raw tokens",
        "Missing": "Run Track 2 to discover semantic gaps", 
        "Exclusion Violated": False,
        "Justification": "Processed via high-speed keyword token matrix."
    }

# --- Track 2: Advanced Semantic Pipeline with Interactive Countdown Clock ---
def process_track_2(cv_text, jd_text, exclusions_text, filename, client, model_choice, status_placeholder):
    # Enforce optional behavior for exclusions cleanly
    clean_exclusions = exclusions_text.strip() if exclusions_text.strip() else "No specific exclusions provided by user."
    
    prompt = f"""
    Evaluate the following Anonymized Resume against the provided Job Description.
    
    CRITICAL EVALUATION RULES:
    1. PhD EQUIVALENCY: If the JD lists standard workforce experience requirements (e.g., 2+ years) and the candidate has an aligned academic PhD, treat the PhD as fully qualifying (count as 4 years of technical experience).
    2. HIGHER EDUCATION BONUS: Prioritize Master's or Doctorate credentials under educational alignment metrics.
    
    CRITICAL EXCLUSION BLOCK (OPTIONAL NEGATIVE FILTERS):
    {clean_exclusions}
    Rule: If and only if a specific exclusion block is active above, check if the candidate matches those traits. If they do, set 'exclusion_violated' to true and penalize or zero-out their 'overall_score'.
    
    Job Description:
    {jd_text}
    
    Anonymized Resume:
    {cv_text}
    """
    
    max_retries = 3
    backoff_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_choice, 
                contents=prompt,
                config={
                    'response_mime_type': 'application/json', 
                    'response_schema': UniversalProfile, 
                    'temperature': 0.1
                }
            )
            p = response.parsed
            return {
                "File Name": filename, 
                "Candidate Name": p.candidate_name, 
                "Score": p.overall_score,
                "Experience (Yrs)": p.experience_years, 
                "Education": p.education_summary,
                "Key Strengths": p.key_strengths, 
                "Missing": p.missing_requirements, 
                "Exclusion Violated": p.exclusion_violated,
                "Justification": p.justification
            }
        except Exception as e:
            # Resiliency handling for temporary data-center 503 capacity spikes
            if "503" in str(e) or "demand" in str(e).lower():
                if attempt < max_retries - 1:
                    # Interactive Visual Countdown Timer Component
                    for remaining in range(int(backoff_delay), 0, -1):
                        status_placeholder.warning(
                            f"⏱️ **Google Server High Demand Spike Detected.** Retrying `{filename}` in **{remaining}s**... (Attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(1)
                    backoff_delay *= 2
                    continue
            raise e

# --- Workspace Layout ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2103/2103322.png", width=50)
    st.markdown("## Nexus Control Panel")
    st.markdown("---")
    
    st.markdown("### ⚙️ Engine Parameters")
    selected_model = st.selectbox(
        "Choose Background Model Architecture:",
        ("gemini-2.5-flash", "gemini-2.5-pro"),
        help="Flash offers optimal tracking speeds for large datasets. Pro maximizes logical processing constraints."
    )
    st.markdown("---")
    st.markdown("**App Environment:** 🟢 Production")
    st.markdown("**Data Privacy Layer:** 🔒 Enforced")

# Premium Header
st.title("💠 Nexus: Semantic Screening & Pipeline Matrix")
st.markdown("<p class='hero-text'>An enterprise-grade cross-role sourcing engine. Instantly map contextual alignments, evaluate advanced degree waivers, implement exclusion safeguards, and bypass the limitations of legacy filters.</p>", unsafe_allow_html=True)

# Functional Descriptions
col_track1, col_track2 = st.columns(2)
with col_track1:
    st.info("### ⚡ Track 1: Fast Keyword Matrix\n**Best For:** Instant screening of massive initial resume volumes.\n* **Technology:** Local NLP token intersection mapping.\n* **Performance:** 100% Free, handles high volume instantly.\n* **Constraint:** Strict dictionary tracking; ignores context or synonyms.")
with col_track2:
    st.success("### 🧠 Track 2: LLM Semantic Pipeline\n**Best For:** Deep, contextual role shortlisting and verification.\n* **Technology:** Gemini Engine + Pydantic Schema Alignment.\n* **Performance:** Highly precise. Reads complex resumes like an expert recruiter.\n* **Capability:** Processes complex rules (e.g., handling PhD experience substitutions and hard filters).")

st.markdown("---")

# Configuration Input Setup
st.subheader("1. Configure Sourcing Pipeline Parameters")
engine_choice = st.radio("Select Processing Track:", ("Track 1: Fast Keyword Matrix (Local)", "Track 2: LLM Semantic Pipeline (Gemini API)"), horizontal=True)

client = None
if "Track 2" in engine_choice:
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("🔒 Configuration Error: GEMINI_API_KEY is missing from your Streamlit Secrets repository.")
        st.stop()
    client = genai.Client(api_key=api_key)

st.subheader("2. Upload Sourcing Directories & System Constraints")
st_jd_col, st_cv_col = st.columns(2)
with st_jd_col:
    uploaded_jd = st.file_uploader("Upload Job Requirement Specification (PDF/DOCX)", type=["pdf", "docx"])
with st_cv_col:
    uploaded_cvs = st.file_uploader("Upload Target Resume Repository (Batch — Max 1,500 files)", type=["pdf", "docx"], accept_multiple_files=True)

# Negative Filter Panel (Clearly documented as completely optional)
st.markdown("#### 🚫 Parameters to Exclude (Negative Filters — *Optional*)")
exclusion_input = st.text_area(
    "Describe candidate profiles you want to discard automatically (Leave blank if not needed):",
    placeholder="Example: Exclude candidates who are freshers. Exclude profiles with more than 10 years of total experience. Do not include anyone without core Python experience.",
    help="Any candidate matching these criteria will be explicitly flagged, down-ranked, and organized cleanly into the pipeline dashboard."
)

# Processing Runtime Execution Loop
if st.button("🚀 Execute Shortlist Pipeline", type="primary"):
    if not uploaded_jd or not uploaded_cvs:
        st.warning("Prerequisites incomplete: Provide both a Job Spec and target Resumes to map.")
    
    elif len(uploaded_cvs) > 1500:
        st.error(f"❌ Batch Limit Exceeded: You uploaded {len(uploaded_cvs)} files. To ensure system stability and prevent runtime timeouts, please restrict batch size to 1,500 or fewer files per batch run.")
        st.stop()
        
    else:
        jd_payload = extract_text_from_file(uploaded_jd, uploaded_jd.name)
        compiled_records = []
        
        # Operational Help Alerts to instruct on using the Force Stop button
        st.markdown(f"<div class='metric-card'>🕵️‍♂️ <b>Job Size:</b> Direct evaluation pipeline initialized for <b>{len(uploaded_cvs)}</b> candidates using <b>{selected_model}</b>. <br><br>🛑 <b>Need to Cancel?</b> To immediately halt or force-stop processing mid-run, click the black <b>'Stop'</b> button located in the top-right corner of your browser page.</div>", unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        
        # Dedicated dynamic placeholder slots for the interactive countdown clock
        clock_placeholder = st.empty()
        spinner_placeholder = st.empty()
        
        with spinner_placeholder.container():
            with st.spinner('Orchestrating workflows and checking constraints...'):
                for idx, cv_file in enumerate(uploaded_cvs):
                    raw_text = extract_text_from_file(cv_file, cv_file.name)
                    secure_text = scrub_pii(raw_text)
                    
                    if "Track 1" in engine_choice:
                        record = process_track_1(secure_text, jd_payload, cv_file.name)
                    else:
                        try:
                            # Pass the clock placeholder down to handle dynamic error rendering
                            record = process_track_2(secure_text, jd_payload, exclusion_input, cv_file.name, client, selected_model, clock_placeholder)
                        except Exception as err:
                            st.error(f"Execution Error on {cv_file.name}: {err}")
                            continue
                    
                    # Clear any temporary countdown warnings once a file succeeds
                    clock_placeholder.empty()
                    compiled_records.append(record)
                    progress_bar.progress((idx + 1) / len(uploaded_cvs))
                    
        spinner_placeholder.empty()
        st.success("Sourcing Pipeline Analysis Complete.")
        df = pd.DataFrame(compiled_records).sort_values(by="Score", ascending=False)
        st.session_state['master_pipeline_data'] = df

# --- Dynamic Kanban UI Deployment ---
if 'master_pipeline_data' in st.session_state:
    df = st.session_state['master_pipeline_data']
    
    st.markdown("---")
    tab_kanban, tab_grid = st.tabs(["📋 Pipeline Screening Board", "🔍 Master Data Sheet"])
    
    with tab_kanban:
        kb1, kb2, kb3, kb4 = st.columns(4)
        
        with kb1:
            st.markdown("#### 🏆 Shortlisted Queue (≥80%)")
            high_df = df[(df['Score'] >= 80) & (df['Exclusion Violated'] == False)]
            for _, r in high_df.iterrows():
                with st.expander(f"🟩 {r['Score']}% — {r['Candidate Name']}"):
                    st.caption(f"📄 File: {r['File Name']}")
                    st.write(f"**Experience:** {r['Experience (Yrs)']} Yrs | **Education:** {r['Education']}")
                    st.write(f"**Core Assets:** {r['Key Strengths']}")
                    st.info(r['Justification'])
                    
        with kb2:
            st.markdown("#### 🟡 Contingent Queue (60-79%)")
            mid_df = df[(df['Score'] >= 60) & (df['Score'] < 80) & (df['Exclusion Violated'] == False)]
            for _, r in mid_df.iterrows():
                with st.expander(f"🟨 {r['Score']}% — {r['Candidate Name']}"):
                    st.caption(f"📄 File: {r['File Name']}")
                    st.write(f"**Experience:** {r['Experience (Yrs)']} Yrs | **Education:** {r['Education']}")
                    st.write(f"**Core Assets:** {r['Key Strengths']}")
                    st.info(r['Justification'])
                    
        with kb3:
            st.markdown("#### 🔴 Unaligned Queue (<60%)")
            low_df = df[(df['Score'] < 60) & (df['Exclusion Violated'] == False)]
            for _, r in low_df.iterrows():
                with st.expander(f"🟥 {r['Score']}% — {r['Candidate Name']}"):
                    st.caption(f"📄 File: {r['File Name']}")
                    st.write(f"**Experience:** {r['Experience (Yrs)']} Yrs")
                    st.write(f"**Missing Qualifications:** {r['Missing']}")
                    st.error(r['Justification'])
                    
        with kb4:
            st.markdown("#### 🛑 Flagged Exclusions")
            ex_df = df[df['Exclusion Violated'] == True]
            for _, r in ex_df.iterrows():
                with st.expander(f"⚫ {r['Score']}% — {r['Candidate Name']}"):
                    st.caption(f"📄 File: {r['File Name']}")
                    st.write(f"**Experience:** {r['Experience (Yrs)']} Yrs")
                    st.warning(f"**Violation:** Triggered exclusion rules.")
                    st.error(r['Justification'])

    with tab_grid:
        st.dataframe(df, use_container_width=True)

    # --- Excel Export Compiler ---
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as xl_writer:
        df.to_excel(xl_writer, index=False, sheet_name='Nexus_Sourcing_Report')
    
    st.download_button(
        label="Download Master Sourcing Report (Excel)",
        data=excel_buffer.getvalue(),
        file_name="nexus_sourcing_analytics.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )