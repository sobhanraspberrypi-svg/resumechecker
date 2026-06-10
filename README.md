# 💠 Nexus: Semantic Candidate Screening Engine

An enterprise-ready, LLM-orchestrated Candidate Sourcing and Application Tracking Matrix built with Python, Streamlit, and the official Google GenAI SDK. 

## 🚀 The Core Innovation
Standard ATS engines review applications by hunting for exact keyword matches. If your job specification requires "Geo-informatics" but a candidate lists "Doctorate in Spatial Data Systems & GIS", traditional parsers drop the applicant completely. 

Nexus utilizes semantic intent evaluation to read documents like a human recruitment engineer. It processes contextual parameters (like evaluating a PhD as 4 years of corporate experience based on custom instructions) and functions uniformly across diverse domains ranging from Geospatial Engineering to Corporate Accounting.

## ⚙️ Architecture & Strategy
* **Local PII Privacy Shield:** Uses localized regular expressions to intercept and scrub candidate phone numbers and email variables before data hits any cloud endpoints.
* **Dual-Track Processing Modality:**
  * **Track 1 (Fast Keyword Matrix):** Uses local token array intersection algorithms. Completely free and built for high-volume baseline filtering.
  * **Track 2 (LLM Semantic Pipeline):** Uses structured JSON schemas via Pydantic mapping on `gemini-2.5-flash` for high-fidelity evaluation.
* **Batch Safeguard Limits:** Built-in validation limits maximum parallel input batches to 1,500 documents per execution block to protect runtime container stability.
* **Dynamic Kanban Board View:** Sorts and aggregates parsed candidate payloads automatically into structured, visual tracking columns.

## 💻 Technical Setup
1. Clone this repository to your environment.
2. Run `pip install -r requirements.txt` to align application dependencies.
3. Add your enterprise `GEMINI_API_KEY` token to your `.streamlit/secrets.toml` file.
4. Execute via terminal: `streamlit run app.py`