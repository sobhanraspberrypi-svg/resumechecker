import streamlit as st
import pandas as pd
import io
import os
import re
import time
from PyPDF2 import PdfReader
from docx import Document
from google import genai
from pydantic import BaseModel, Field

# --- Page Configuration ---
st.set_page_config(
    page_title="Nexus | AI Sourcing Matrix",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
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
    candidate_name: str = Field(description="The extracted actual name of the candidate.")
    base_score: int = Field(description="Raw alignment score from 0 to 100 based strictly on the core Job Description.")
    education_summary: str = Field(description="Highest degree earned, major, and institution.")
    experience_years: float = Field(description="Total calculated workforce experience in years.")
    key_strengths: str = Field(description="Comma-separated list of top 3 matching capabilities.")
    missing_requirements: str = Field(description="Key criteria from the JD that are visibly missing.")
    inclusion_matched: bool = Field(description="True ONLY if the candidate matches the specific Priority/Inclusion traits.")
    exclusion_violated: bool = Field(description="True ONLY if the candidate possesses traits listed in the Negative Filters.")
    justification: str = Field(description="One concise sentence explaining the raw score and any flagged rules.")

# --- Local Text Extraction & Security ---
def scrub_pii(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    text = re.sub(email_pattern, "[EMAIL MASKED]", text)
    text = re.sub(phone_pattern, "[PHONE MASKED]", text)
    return text

def extract_text_from_file(file_obj, filename):
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

# --- Track 1: Fast Engine ---
def process_track_1(cv_text, jd_text, filename):
    return {"File Name": filename, "Candidate Name": "Switch to Track 2", "Base Score": 0, "Final Score": 0, "Justification": "Track 1 is for basic text overlap, not logical scoring.", "Priority Matched": False, "Exclusion Violated": False, "Experience (Yrs)": 0, "Education": "N/A", "Key Strengths": "N/A", "Missing": "N/A"}

# --- Track 2: Advanced Semantic Engine with Bulletproof 503 Handling ---
def process_track_2(cv_text, jd_text, inclusion_text, exclusion_text, filename, client, model_choice, status_placeholder):
    clean_inc = inclusion_text.strip() if inclusion_text.strip() else "None provided."
    clean_exc = exclusion_text.strip() if exclusion_text.strip() else "None provided."
    
    prompt = f"""
    Evaluate the following Anonymized Resume against the Job Description.
    
    1. PRIORITIES (INCLUSION): {clean_inc}
    If candidate has these, set 'inclusion_matched' to true.
    
    2. NEGATIVE FILTERS (EXCLUSION): {clean_exc}
    If candidate has these, set 'exclusion_violated' to true.
    
    Job Description: {jd_text}
    Anonymized Resume: {cv_text}
    """
    
    max_retries = 5 # Highly robust retry count
    backoff_delay = 5 # Starts at 5s, doubles up to a minute on fail
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_choice, contents=prompt,
                config={'response_mime_type': 'application/json', 'response_schema': UniversalProfile, 'temperature': 0.1}
            )
            p = response.parsed
            
            # --- STRICT MATHEMATICAL SCORING ---
            final_score = p.base_score
            if p.inclusion_matched:
                final_score += 15
            if p.exclusion_violated:
                final_score -= 30
                
            final_score = max(0, min(100, final_score))
            
            return {
                "File Name": filename, 
                "Candidate Name": p.candidate_name, 
                "Base Score": p.base_score,
                "Final Score": final_score,
                "Experience (Yrs)": p.experience_years, 
                "Education": p.education_summary,
                "Key Strengths": p.key_strengths, 
                "Missing": p.missing_requirements, 
                "Priority Matched": p.inclusion_matched,
                "Exclusion Violated": p.exclusion_violated,
                "Justification": p.justification
            }
        except Exception as e:
            if "503" in str(e) or "demand" in str(e).lower():
                if attempt < max_retries - 1:
                    for remaining in range(int(backoff_delay), 0, -1):
                        status_placeholder.warning(f"⏱️ **Google Server Spike (503).** Pausing pipeline to avoid drop. Retrying `{filename}` in **{remaining}s**... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(1)
                    backoff_delay *= 2 # Exponential backoff prevents spamming the crashed server
                    continue
            raise e

# --- Sidebar Configuration (Restored Model Info) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2103/2103322.png", width=50)
    st.markdown("## Nexus Control Panel")
    st.markdown("---")
    
    st.markdown("### 🧠 AI Model Architecture")
    selected_model = st.selectbox(
        "Select Background LLM Engine:",
        ("gemini-2.5-flash", "gemini-2.5-pro"),
        index=0
    )
    st.info("""
    **Model Guide:**
    * **Flash (Default):** Extremely fast and highly cost-effective. Best for massive batch processing (100+ CVs).
    * **Pro:** Slower and slightly more expensive, but features elite logical reasoning. Best for nuanced roles (<50 CVs) where complex exclusion math is failing.
    """)
    st.markdown("---")
    st.markdown("**App Environment:** 🟢 Production")
    st.markdown("**Data Privacy Layer:** 🔒 Enforced")

# --- Main UI Header ---
st.title("💠 Nexus: Semantic Pipeline")
st.markdown("<p class='hero-text'>Enterprise-grade resume processing with Priority Weighting, Negative Filters, and Checkpoint Data Backup.</p>", unsafe_allow_html=True)

# --- Restored Interactive Architecture Guide ---
with st.expander("📖 Interactive Guide: Engine Tracks & Scoring Logic", expanded=False):
    st.markdown("### 1. Select Your Sourcing Engine")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.info("⚡ **Track 1: Fast Keyword Matrix (Free/Local)**\n\nUses Python token-intersection to instantly find keyword overlap. Best for rapid volume culling. Ignores context.")
    with col_t2:
        st.success("🧠 **Track 2: LLM Semantic Pipeline (API)**\n\nUses Gemini to read complex context, evaluate PhD equivalencies, and apply strict inclusion/exclusion rules.")
    
    st.markdown("---")
    st.markdown("### 2. How the Math is Calculated (Track 2)")
    st.markdown("""
    To prevent AI hallucination, Nexus decouples the scoring logic:
    * **Base Score (0-100):** AI determines raw alignment with the Job Description.
    * **Inclusion Bonus (+15 Pts):** Automatically added if priority traits are found.
    * **Exclusion Penalty (-30 Pts):** Automatically subtracted if unwanted traits are detected.
    * *(Final scores are capped mathematically between 0 and 100)*
    """)

st.markdown("---")

# Pipeline Setup
st.subheader("1. Configure Sourcing Parameters")
engine_choice = st.radio("Select Active Processing Track:", ("Track 2: LLM Semantic Pipeline", "Track 1: Local Keyword (Basic)"), horizontal=True)

col_inc, col_exc = st.columns(2)
with col_inc:
    inclusion_input = st.text_area("🌟 Priority Traits (Inclusion Bonus +15)", placeholder="Example: Remote sensing, satellite imaging, 1 to 5 years experience.")
with col_exc:
    exclusion_input = st.text_area("🚫 Traits to Discard (Exclusion Penalty -30)", placeholder="Example: More than 10 years experience, zero Python knowledge.")

st.subheader("2. File Uploads & Checkpoint Configuration")
st_jd, st_cv = st.columns(2)
with st_jd:
    uploaded_jd = st.file_uploader("Upload Job Description (PDF/DOCX)", type=["pdf", "docx"])
with st_cv:
    uploaded_cvs = st.file_uploader("Upload Target Resumes (Batch)", type=["pdf", "docx"], accept_multiple_files=True)

backup_dir = st.text_input("📁 Local Backup Directory (For massive batches)", placeholder="e.g., E:\\STARTUP_PROPOSALS\\Backups", help="Ensures no data is lost if the Streamlit browser times out.")

if st.button("🚀 Execute Pipeline", type="primary"):
    if not uploaded_jd or not uploaded_cvs:
        st.warning("Upload both a Job Description and Resumes.")
        st.stop()
        
    if backup_dir and not os.path.isdir(backup_dir):
        st.error(f"❌ Backup Directory Error: The path '{backup_dir}' does not exist. Please create the folder or leave the box blank.")
        st.stop()

    client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY"))
    jd_payload = extract_text_from_file(uploaded_jd, uploaded_jd.name)
    
    compiled_records = []
    progress_bar = st.progress(0)
    clock_placeholder = st.empty()
    
    backup_file_path = os.path.join(backup_dir, "nexus_live_backup.csv") if backup_dir else None

    with st.spinner(f'Processing {len(uploaded_cvs)} resumes using {selected_model}...'):
        for idx, cv_file in enumerate(uploaded_cvs):
            secure_text = scrub_pii(extract_text_from_file(cv_file, cv_file.name))
            
            if "Track 1" in engine_choice:
                record = process_track_1(secure_text, jd_payload, cv_file.name)
            else:
                try:
                    record = process_track_2(secure_text, jd_payload, inclusion_input, exclusion_input, cv_file.name, client, selected_model, clock_placeholder)
                except Exception as err:
                    st.error(f"Failed on {cv_file.name}: {err}")
                    continue
            
            clock_placeholder.empty()
            compiled_records.append(record)
            
            # --- LIVE CHECKPOINTING ---
            if backup_file_path:
                try:
                    df_incremental = pd.DataFrame([record])
                    write_mode = 'w' if idx == 0 else 'a'
                    write_header = True if idx == 0 else False
                    df_incremental.to_csv(backup_file_path, mode=write_mode, header=write_header, index=False)
                except Exception as e:
                    pass # Silently fail backup if permission denied so pipeline continues

            progress_bar.progress((idx + 1) / len(uploaded_cvs))
            
    st.success(f"Processing Complete! Backup saved to {backup_file_path}" if backup_file_path else "Processing Complete!")
    df = pd.DataFrame(compiled_records).sort_values(by="Final Score", ascending=False)
    st.session_state['master_data'] = df

# --- Results Dashboard ---
if 'master_data' in st.session_state:
    df = st.session_state['master_data']
    st.markdown("---")
    
    if st.button("🧹 Clear Memory for New Batch"):
        st.session_state.clear()
        st.rerun()

    st.subheader("📋 Pipeline Screening Board")
    kb1, kb2, kb3 = st.columns(3)
    
    with kb1:
        st.markdown("#### 🏆 Shortlisted (≥80)")
        for _, r in df[df['Final Score'] >= 80].iterrows():
            with st.expander(f"🟩 {r['Final Score']} — {r['Candidate Name']}"):
                st.caption(f"Base: {r['Base Score']} | Priority: {r['Priority Matched']} | Excluded: {r['Exclusion Violated']}")
                st.info(r['Justification'])
                
    with kb2:
        st.markdown("#### 🟡 Review (50-79)")
        for _, r in df[(df['Final Score'] >= 50) & (df['Final Score'] < 80)].iterrows():
            with st.expander(f"🟨 {r['Final Score']} — {r['Candidate Name']}"):
                st.caption(f"Base: {r['Base Score']} | Priority: {r['Priority Matched']} | Excluded: {r['Exclusion Violated']}")
                st.info(r['Justification'])
                
    with kb3:
        st.markdown("#### 🔴 Unaligned (<50)")
        for _, r in df[df['Final Score'] < 50].iterrows():
            with st.expander(f"🟥 {r['Final Score']} — {r['Candidate Name']}"):
                st.caption(f"Base: {r['Base Score']} | Priority: {r['Priority Matched']} | Excluded: {r['Exclusion Violated']}")
                if r['Exclusion Violated']: st.error("Penalty Applied: Triggered Exclusion Filter")
                st.error(r['Justification'])

    st.dataframe(df, use_container_width=True)