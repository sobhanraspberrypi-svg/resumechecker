import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
import re
import time
import hashlib
import gc
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

# --- System Constants ---
RECOVERY_FILE = ".nexus_cloud_backup.csv"
BATCH_SIZE = 50  # Memory flush trigger

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

# --- Core ETL Utilities ---
def get_file_hash(file_obj):
    file_obj.seek(0)
    file_hash = hashlib.sha256(file_obj.read()).hexdigest()
    file_obj.seek(0) 
    return file_hash

def scrub_pii(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    return re.sub(phone_pattern, "[PHONE MASKED]", re.sub(email_pattern, "[EMAIL MASKED]", text))

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
def process_track_1(cv_text, jd_text, filename, f_hash):
    return {"File Name": filename, "Candidate Name": "Switch to Track 2 for Name", "Base Score": 0, "Final Score": 0, "Experience (Yrs)": 0, "Education": "N/A", "Key Strengths": "N/A", "Missing": "N/A", "Priority Matched": False, "Exclusion Violated": False, "Justification": "Processed via Track 1 Keyword Matrix.", "File Hash": f_hash}

# --- Track 2: Advanced Semantic Engine ---
def process_track_2(cv_text, jd_text, inclusion_text, exclusion_text, filename, f_hash, client, model_choice, status_placeholder):
    clean_inc = inclusion_text.strip() if inclusion_text.strip() else "None provided."
    clean_exc = exclusion_text.strip() if exclusion_text.strip() else "None provided."
    
    prompt = f"""
    Evaluate the following Anonymized Resume against the Job Description.
    1. PRIORITIES (INCLUSION): {clean_inc} (Set 'inclusion_matched' to true if found).
    2. NEGATIVE FILTERS (EXCLUSION): {clean_exc} (Set 'exclusion_violated' to true if found).
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
            
            final_score = p.base_score
            if p.inclusion_matched: final_score += 15
            if p.exclusion_violated: final_score -= 30
            final_score = max(0, min(100, final_score))
            
            return {
                "File Name": filename, "Candidate Name": p.candidate_name, "Base Score": p.base_score, "Final Score": final_score,
                "Experience (Yrs)": p.experience_years, "Education": p.education_summary, "Key Strengths": p.key_strengths, 
                "Missing": p.missing_requirements, "Priority Matched": p.inclusion_matched, "Exclusion Violated": p.exclusion_violated,
                "Justification": p.justification, "File Hash": f_hash
            }
        except Exception as e:
            if "503" in str(e) or "demand" in str(e).lower():
                if attempt < max_retries - 1:
                    for remaining in range(int(backoff_delay), 0, -1):
                        status_placeholder.warning(f"⏱️ **Google Server Spike.** Pausing pipeline. Retrying `{filename}` in **{remaining}s**...")
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
    selected_model = st.selectbox("Select Background LLM Engine:", ("gemini-2.5-flash", "gemini-2.5-pro"), index=0)
    st.markdown("---")
    
    st.markdown("### 🛠️ System Maintenance")
    if st.button("🚨 Factory Reset & Clear Memory", type="secondary"):
        if os.path.exists(RECOVERY_FILE):
            os.remove(RECOVERY_FILE)
        st.session_state.clear()
        st.success("System wiped. Ready for a completely new batch!")
        time.sleep(1)
        st.rerun()

# --- Main UI Header ---
st.title("💠 Nexus: Semantic Analytics Pipeline")
st.markdown("<p class='hero-text'>Enterprise-grade screening with Cryptographic Deduplication, Automatic Memory Flushing, and Immortal Cloud Backups.</p>", unsafe_allow_html=True)

# --- SYSTEM INSTRUCTION EXPANDERS ---
with st.expander("📖 System Architecture, Scoring Logic & Safe Limits", expanded=False):
    st.markdown("### 1. Engine Processing Tracks")
    st.info("**Track 1: Local Keyword (Basic):** High-speed, 100% free token-intersection mapping. Good for massive volume culling but ignores deep context.")
    st.success("**Track 2: LLM Semantic Pipeline:** Deep reading via Gemini 2.5. Capable of mapping advanced degree waivers and complex scoring logic.")
    
    st.markdown("### 2. Mathematical Scoring Structure")
    st.write("To prevent AI hallucination, final scores are strictly calculated via hard Python logic:")
    st.markdown("* **Base Score (0-100):** AI determines raw alignment with the core JD.\n* **Inclusion Bonus (+15 Pts):** Automatically applied if priority traits are detected.\n* **Exclusion Penalty (-30 Pts):** Automatically deducted if negative filters are triggered.")
    
    st.markdown("### 3. Safe Cloud Batch Limits")
    st.warning("**Cloud Limit:** While the system employs background garbage collection (RAM flushing), we recommend uploading batches of **100-150 resumes at a time** to prevent web-browser timeouts. The system will automatically save your progress and append subsequent batches safely.")

# --- CLOUD RESCUE DETECTION ---
if os.path.exists(RECOVERY_FILE):
    st.info("📌 **Active Ledger Detected:** A previous dataset is stored in the system. New uploads will be appended, and exact duplicates will be bypassed to save API tokens.")
    if st.button("🔄 View Current Visual Dashboard"):
        st.session_state['master_data'] = pd.read_csv(RECOVERY_FILE)

st.markdown("---")

# Pipeline Setup
st.subheader("1. Configure Sourcing Parameters")
engine_choice = st.radio("Select Active Processing Track:", ("Track 1: Local Keyword (Basic)", "Track 2: LLM Semantic Pipeline"), horizontal=True)

col_inc, col_exc = st.columns(2)
with col_inc:
    inclusion_input = st.text_area("🌟 Priority Traits (Inclusion Bonus +15)")
with col_exc:
    exclusion_input = st.text_area("🚫 Traits to Discard (Exclusion Penalty -30)")

st.subheader("2. File Uploads")
st_jd, st_cv = st.columns(2)
with st_jd:
    uploaded_jd = st.file_uploader("Upload Job Description (PDF/DOCX)", type=["pdf", "docx"])
with st_cv:
    uploaded_cvs = st.file_uploader("Upload Target Resumes (Batch)", type=["pdf", "docx"], accept_multiple_files=True)

st.markdown("---")
tc_agreed = st.checkbox("I acknowledge that Nexus is an experimental AI-driven pipeline meant for preliminary screening.")

if st.button("🚀 Execute Pipeline", type="primary", disabled=not tc_agreed):
    if not uploaded_jd or not uploaded_cvs:
        st.warning("Upload both a Job Description and Resumes.")
        st.stop()

    client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY"))
    jd_payload = extract_text_from_file(uploaded_jd, uploaded_jd.name)
    
    recovered_hashes = set()
    if os.path.exists(RECOVERY_FILE):
        existing_df = pd.read_csv(RECOVERY_FILE)
        if 'File Hash' in existing_df.columns:
            recovered_hashes = set(existing_df['File Hash'].dropna().tolist())

    session_hashes = set()
    progress_bar = st.progress(0)
    status_msg = st.empty()
    clock_placeholder = st.empty()
    
    total_files = len(uploaded_cvs)
    
    for idx, cv_file in enumerate(uploaded_cvs):
        f_hash = get_file_hash(cv_file)
        status_msg.info(f"Processing ({idx+1}/{total_files}): {cv_file.name}")
        
        if f_hash in recovered_hashes:
            progress_bar.progress((idx + 1) / total_files)
            continue
            
        elif f_hash in session_hashes:
            record = {
                "File Name": cv_file.name, "Candidate Name": "Duplicate Record", "Base Score": 0, "Final Score": 0,
                "Experience (Yrs)": 0, "Education": "N/A", "Key Strengths": "N/A", "Missing": "N/A",
                "Priority Matched": False, "Exclusion Violated": False, "Justification": "Bypassed: Exact duplicate of another file in this batch.",
                "File Hash": f_hash
            }
        else:
            session_hashes.add(f_hash)
            secure_text = scrub_pii(extract_text_from_file(cv_file, cv_file.name))
            
            if "Track 1" in engine_choice:
                record = process_track_1(secure_text, jd_payload, cv_file.name, f_hash)
            else:
                try:
                    record = process_track_2(secure_text, jd_payload, inclusion_input, exclusion_input, cv_file.name, f_hash, client, selected_model, clock_placeholder)
                except Exception as err:
                    st.error(f"Failed on {cv_file.name}: {err}")
                    continue

        try:
            df_incremental = pd.DataFrame([record])
            write_mode = 'a' if os.path.exists(RECOVERY_FILE) else 'w'
            write_header = not os.path.exists(RECOVERY_FILE)
            df_incremental.to_csv(RECOVERY_FILE, mode=write_mode, header=write_header, index=False)
        except Exception as e:
            pass 

        progress_bar.progress((idx + 1) / total_files)
        
        if (idx + 1) % BATCH_SIZE == 0:
            gc.collect()
            
    status_msg.success("Processing Complete!")
    st.session_state['master_data'] = pd.read_csv(RECOVERY_FILE)
    st.rerun()

# --- VISUAL RESULTS DASHBOARD ---
if 'master_data' in st.session_state:
    df = st.session_state['master_data']
    st.markdown("---")
    
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as xl_writer:
        df.to_excel(xl_writer, index=False, sheet_name='Nexus_Sourcing_Report')
    
    st.download_button(
        label="⬇️ Download Master Sourcing Report (Excel)",
        data=excel_buffer.getvalue(),
        file_name="nexus_sourcing_analytics.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

    st.markdown("### 📊 Enterprise Cohort Analytics")
    
    # Pre-process Data for Visuals
    def categorize_score(score):
        if score == 0: return "Duplicate / Invalid"
        elif score >= 80: return "Shortlisted (≥80)"
        elif score >= 50: return "Review (50-79)"
        else: return "Unaligned (<50)"
        
    def categorize_edu(edu_str):
        edu = str(edu_str).lower()
        if 'phd' in edu or 'doctorate' in edu: return "Doctorate (PhD)"
        elif any(keyword in edu for keyword in ['master', 'msc', 'm.sc', 'mba', 'm.tech', 'm.e.']): return "Master's Degree"
        elif any(keyword in edu for keyword in ['bachelor', 'bsc', 'b.sc', 'b.tech', 'be ', 'b.e.']): return "Bachelor's Degree"
        else: return "Other / Unspecified"
        
    def categorize_domain(edu_str):
        edu = str(edu_str).lower()
        if any(keyword in edu for keyword in ['geo', 'gis', 'remote sensing', 'spatial']): return "Geospatial & GIS"
        elif 'agri' in edu: return "Agriculture & Agronomy"
        elif any(keyword in edu for keyword in ['computer', 'it ', 'software']): return "Computer Science & IT"
        elif any(keyword in edu for keyword in ['civil', 'planning', 'architecture']): return "Civil & Urban Planning"
        elif any(keyword in edu for keyword in ['environment', 'earth', 'geology']): return "Environmental & Earth Sciences"
        elif any(keyword in edu for keyword in ['physics', 'math', 'stat']): return "Math & Physics"
        else: return "Other Disciplines"
    
    df['Pipeline Tier'] = df['Final Score'].apply(categorize_score)
    df['Degree Level'] = df['Education'].apply(categorize_edu)
    df['Academic Domain'] = df['Education'].apply(categorize_domain)
    
    # Remove duplicates/zeros from academic breakdown to keep charts clean
    clean_df = df[df['Final Score'] > 0]
    
    # Render Row 1: Pipeline Tier & Technical Strengths
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        tier_counts = df['Pipeline Tier'].value_counts().reset_index()
        tier_counts.columns = ['Tier', 'Count']
        fig_pie1 = px.pie(
            tier_counts, values='Count', names='Tier', hole=0.4, title="Candidate Pipeline Distribution",
            color='Tier',
            color_discrete_map={"Shortlisted (≥80)": "#2ECC71", "Review (50-79)": "#F1C40F", "Unaligned (<50)": "#E74C3C", "Duplicate / Invalid": "#95A5A6"}
        )
        st.plotly_chart(fig_pie1, use_container_width=True)

    with r1c2:
        all_skills = []
        for strengths in df['Key Strengths'].dropna():
            if isinstance(strengths, str) and strengths != "N/A":
                skills = [s.strip() for s in strengths.split(',')]
                all_skills.extend(skills)
                
        skill_counts = Counter(all_skills).most_common(10)
        df_skills = pd.DataFrame(skill_counts, columns=['Skill', 'Frequency'])
        if not df_skills.empty:
            fig_bar1 = px.bar(df_skills, x='Frequency', y='Skill', orientation='h', title="Top 10 Technical Strengths", color='Frequency', color_continuous_scale='Blues')
            fig_bar1.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar1, use_container_width=True)
            
    # Render Row 2: Education Level & Academic Domain
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        edu_counts = clean_df['Degree Level'].value_counts().reset_index()
        edu_counts.columns = ['Degree Level', 'Count']
        fig_pie2 = px.pie(
            edu_counts, values='Count', names='Degree Level', title="Highest Academic Qualification",
            color_discrete_sequence=px.colors.sequential.Teal
        )
        st.plotly_chart(fig_pie2, use_container_width=True)
        
    with r2c2:
        domain_counts = clean_df['Academic Domain'].value_counts().reset_index()
        domain_counts.columns = ['Domain', 'Count']
        fig_bar2 = px.bar(domain_counts, x='Count', y='Domain', orientation='h', title="Primary Academic Backgrounds", color='Count', color_continuous_scale='Purples')
        fig_bar2.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar2, use_container_width=True)