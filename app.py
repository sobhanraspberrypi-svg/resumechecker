import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
import re
import time
from collections import Counter
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

# --- Cloud Rescue File Path ---
# This file is hidden and saves directly to the Streamlit server's background storage
RECOVERY_FILE = ".nexus_cloud_backup.csv"

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
    
    max_retries = 5 
    backoff_delay = 5 
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_choice, contents=prompt,
                config={'response_mime_type': 'application/json', 'response_schema': UniversalProfile, 'temperature': 0.1}
            )
            p = response.parsed
            
            # Mathematical Scoring
            final_score = p.base_score
            if p.inclusion_matched: final_score += 15
            if p.exclusion_violated: final_score -= 30
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
                        status_placeholder.warning(f"⏱️ **Google Server Spike (503).** Pausing pipeline. Retrying `{filename}` in **{remaining}s**... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(1)
                    backoff_delay *= 2 
                    continue
            raise e

# --- Sidebar Configuration ---
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
    st.info("**Flash (Default):** Extremely fast, best for massive batch processing (100+ CVs).\n\n**Pro:** Slower but features elite reasoning. Best for complex exclusion math on small batches.")
    st.markdown("---")
    st.markdown("**App Environment:** 🟢 Production (Visual Analytics)")

# --- Main UI Header ---
st.title("💠 Nexus: Semantic Analytics Pipeline")
st.markdown("<p class='hero-text'>Enterprise-grade resume processing mapped to live visual architecture. Built with crash-proof dual checkpointing.</p>", unsafe_allow_html=True)

# --- CLOUD RESCUE DETECTION ---
if os.path.exists(RECOVERY_FILE):
    st.warning("⚠️ **Rescue Data Detected:** It looks like a previous batch was interrupted by a browser timeout.")
    if st.button("🔄 Load Recovered Dashboard"):
        df_recovered = pd.read_csv(RECOVERY_FILE)
        st.session_state['master_data'] = df_recovered
        st.success(f"Successfully recovered {len(df_recovered)} profiles from the cloud server!")

st.markdown("---")

# Pipeline Setup
st.subheader("1. Configure Sourcing Parameters")
engine_choice = st.radio("Select Active Processing Track:", ("Track 2: LLM Semantic Pipeline", "Track 1: Local Keyword (Basic)"), horizontal=True)

col_inc, col_exc = st.columns(2)
with col_inc:
    inclusion_input = st.text_area("🌟 Priority Traits (Inclusion Bonus +15)")
with col_exc:
    exclusion_input = st.text_area("🚫 Traits to Discard (Exclusion Penalty -30)")

st.subheader("2. File Uploads & Security Backups")
st_jd, st_cv = st.columns(2)
with st_jd:
    uploaded_jd = st.file_uploader("Upload Job Description (PDF/DOCX)", type=["pdf", "docx"])
with st_cv:
    uploaded_cvs = st.file_uploader("Upload Target Resumes (Batch)", type=["pdf", "docx"], accept_multiple_files=True)

# UPDATED LOCAL BACKUP FIELD WITH WARNING
backup_dir = st.text_input(
    "📁 Local Backup Directory (⚠️ USE ONLY WHEN RUNNING LOCALLY ON YOUR PC)", 
    placeholder="e.g., E:\\STARTUP_PROPOSALS\\Backups", 
    help="If running this app on your own computer, enter a folder path to save backups. LEAVE THIS BLANK if you are using the live Streamlit Cloud web link!"
)

st.markdown("---")
st.markdown("#### ⚠️ Experimental Framework Agreement")
tc_agreed = st.checkbox("I acknowledge that Nexus is an experimental AI-driven pipeline. Results are generated via semantic probability models. I agree to use these insights for preliminary screening assistance only.")

if st.button("🚀 Execute Pipeline", type="primary", disabled=not tc_agreed):
    if not uploaded_jd or not uploaded_cvs:
        st.warning("Upload both a Job Description and Resumes.")
        st.stop()
        
    if backup_dir and not os.path.isdir(backup_dir):
        st.error(f"❌ Backup Directory Error: The path '{backup_dir}' does not exist on this machine. Please create the folder or leave the box blank.")
        st.stop()

    client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY"))
    jd_payload = extract_text_from_file(uploaded_jd, uploaded_jd.name)
    
    # Determine local backup file path if user provided a valid directory
    local_backup_file = os.path.join(backup_dir, "nexus_local_backup.csv") if backup_dir else None

    # Clean slate for previous cloud rescues and local backups
    if os.path.exists(RECOVERY_FILE):
        os.remove(RECOVERY_FILE)
    if local_backup_file and os.path.exists(local_backup_file):
        os.remove(local_backup_file)
    
    progress_bar = st.progress(0)
    clock_placeholder = st.empty()
    
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
            
            # --- DUAL CHECKPOINTING ---
            try:
                df_incremental = pd.DataFrame([record])
                write_mode = 'w' if idx == 0 else 'a'
                write_header = True if idx == 0 else False
                
                # 1. Always save to Cloud Rescue
                df_incremental.to_csv(RECOVERY_FILE, mode=write_mode, header=write_header, index=False)
                
                # 2. Save to Local Backup if requested
                if local_backup_file:
                    df_incremental.to_csv(local_backup_file, mode=write_mode, header=write_header, index=False)
                    
            except Exception as e:
                pass # Fail silently so the main loop continues

            progress_bar.progress((idx + 1) / len(uploaded_cvs))
            
    st.success("Processing Complete!")
    st.session_state['master_data'] = pd.read_csv(RECOVERY_FILE)

# --- VISUAL RESULTS DASHBOARD ---
if 'master_data' in st.session_state:
    df = st.session_state['master_data']
    st.markdown("---")
    
    # Provide the Excel Download immediately
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as xl_writer:
        df.to_excel(xl_writer, index=False, sheet_name='Nexus_Sourcing_Report')
    
    col_dl, col_clear = st.columns([3, 1])
    with col_dl:
        st.download_button(
            label="⬇️ Download Master Sourcing Report (Excel)",
            data=excel_buffer.getvalue(),
            file_name="nexus_sourcing_analytics.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    with col_clear:
        if st.button("🧹 Clear Memory"):
            st.session_state.clear()
            st.rerun()

    st.markdown("### 📊 Cohort Analytics")
    
    # Pre-process Data for Categories
    def categorize_score(score):
        if score >= 80: return "Shortlisted (≥80)"
        elif score >= 50: return "Review (50-79)"
        else: return "Unaligned (<50)"
    
    df['Pipeline Tier'] = df['Final Score'].apply(categorize_score)
    
    # Render Graphs side-by-side
    graph_col1, graph_col2 = st.columns(2)
    
    with graph_col1:
        # Donut Chart for Score Distribution
        tier_counts = df['Pipeline Tier'].value_counts().reset_index()
        tier_counts.columns = ['Tier', 'Count']
        fig_pie = px.pie(
            tier_counts, 
            values='Count', 
            names='Tier', 
            hole=0.4, 
            title="Candidate Pipeline Distribution",
            color='Tier',
            color_discrete_map={
                "Shortlisted (≥80)": "#2ECC71", 
                "Review (50-79)": "#F1C40F", 
                "Unaligned (<50)": "#E74C3C"
            }
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    with graph_col2:
        # Bar Chart for Most Common Skills
        all_skills = []
        for strengths in df['Key Strengths'].dropna():
            if isinstance(strengths, str) and strengths != "N/A":
                skills = [s.strip() for s in strengths.split(',')]
                all_skills.extend(skills)
        
        # Count and get top 10
        skill_counts = Counter(all_skills).most_common(10)
        df_skills = pd.DataFrame(skill_counts, columns=['Skill', 'Frequency'])
        
        if not df_skills.empty:
            fig_bar = px.bar(
                df_skills, 
                x='Frequency', 
                y='Skill', 
                orientation='h',
                title="Top 10 Technical Strengths Found in Cohort",
                color='Frequency',
                color_continuous_scale='Blues'
            )
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Not enough skill data extracted to render technical chart.")
            
    # Render a lightweight preview of the data instead of 300 heavy expanders
    st.markdown("### 🔍 Top 20 Candidates Preview")
    preview_df = df[['Candidate Name', 'Final Score', 'Experience (Yrs)', 'Key Strengths', 'Pipeline Tier']].head(20)
    st.dataframe(preview_df, use_container_width=True)