# 📡 CVRadar  — AI-Powered Resume Screening Matrix

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.45%2B-FF4B4B?logo=streamlit)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Providers](https://img.shields.io/badge/LLM-Gemini%20%7C%20Claude%20%7C%20OpenAI-purple)](https://anthropic.com)

> **Multi-provider AI resume screening with local pre-filtering, cryptographic deduplication, checkpoint recovery, and session-isolated multi-user storage.**

---

## ⚠️ Disclaimer

CVRadar is an **experimental, open-source** AI-assisted pipeline intended **solely for preliminary CV screening**. All results must be validated by a qualified human recruiter before any hiring decision is made.

The author and contributors accept **no responsibility or liability** for:
- API costs incurred, including charges from failed runs, 503 errors, or model unavailability
- Unsatisfactory, incorrect, or biased screening results
- Any direct, indirect, or consequential loss arising from use of this software

**By using CVRadar you agree that use is entirely at your own risk.**  
This tool does not constitute legal, HR, or professional recruitment advice.

Users who paste their own API key acknowledge that charges from incomplete runs, rate-limit errors, or unsatisfactory results are solely their responsibility. The author bears no liability for any API spend.

---

## ✨ Features

- **Three processing tracks** — fully offline local keyword engine, deep LLM semantic evaluation, and a hybrid mode that saves 40–70% of API calls
- **Multi-provider LLM support** — Google Gemini, Anthropic Claude, and OpenAI GPT, selectable from the sidebar
- **Bring-your-own-key** — users paste their own API key; it lives only in their browser session and is never saved to disk
- **Deterministic scoring** — the AI never generates scores; all arithmetic is hard Python (skills 35 + experience 20 + education 15 + projects 15 + domain 10 + certifications 5)
- **Priority & Exclusion filters** — optional ±15/−30 point adjustments for desirable and disqualifying traits, including numeric experience thresholds (`less than 2 years`, `freshers not required`)
- **Checkpoint recovery** — per-session, per-track ledger skips already-processed CVs on re-run; Track 1 hashes never block Track 2 runs
- **Session-isolated storage** — every browser tab gets a UUID; concurrent users cannot see or interfere with each other's data
- **PII masking** — emails and phone numbers replaced before any text reaches the LLM
- **Graceful degradation** — LLM failure falls back to local Track 1 score; no blank rows
- **Clean 12-column Excel output** — full filenames, colour-coded fit categories, recruiter-ready
- **Analytics dashboard** — stream breakdown, education level pie, skills matched/missing, score distribution

---

## 🖥️ Demo Screenshot

```
📡 CVRadar — AI Resume Screening Matrix
├── Stream & Education Analytics
│   ├── Streams: Who Applied (horizontal bar)
│   └── Education Level Breakdown (donut pie)
├── Skills Analysis
│   ├── Top Skills Found Across CVs
│   └── Skills Most Commonly Missing (Talent Gap)
└── Processing Track Breakdown
```

---

## 🚀 Quick Start

### 1. Clone

```bash
git clone https://github.com/sobhanraspberrypi-svg/resumechecker.git
cd resumechecker
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys (optional)

Create a `.env` file in the project root:

```env
# Add only the providers you intend to use
GEMINI_API_KEY=your_gemini_key_here
ANTHROPIC_API_KEY=your_claude_key_here
OPENAI_API_KEY=your_openai_key_here
```

> **Note:** If you have no server key, users can paste their own key in the sidebar at runtime. Track 1 (Local Keyword) requires no key at all.

### 4. Run

```bash
streamlit run app.py
```

---

## 📁 Project Structure

```
resumechecker/
├── app.py                    ← Main Streamlit application (CVRadar v3)
├── config.py                 ← Scoring weights, fit categories, directory paths
├── requirements.txt
├── .env                      ← API keys — DO NOT commit this file
├── .gitignore
├── LICENSE
├── README.md
└── src/
    ├── parser.py             ← PDF / DOCX text extraction + PII masking
    ├── jd_parser.py          ← Local DOCX JD keyword extraction (Track 1, zero LLM)
    ├── llm_provider.py       ← Unified Gemini / Claude / OpenAI adapter with retry logic
    ├── evaluator.py          ← LLM evaluation schema and structured call logic
    ├── scorer.py             ← Deterministic Python scorer (no AI numbers)
    ├── filters.py            ← Priority / exclusion filter engine
    ├── reporting.py          ← Excel export and analytics dataframe builder
    ├── schemas.py            ← Pydantic data models (CandidateProfile, JDRequirements)
    ├── checkpoint_manager.py ← Per-session, per-track checkpoint ledger
    ├── status_tracker.py     ← Per-CV processing status log
    └── domain_taxonomy.txt   ← Global academic domain synonym list (97 entries, 14 groups)
```

---

## ⚙️ Processing Tracks

| Track | Cost | API Required | Best For |
|---|---|---|---|
| **Track 1: Local Keyword** | Free | ❌ None | Fast bulk pre-screening, zero token spend |
| **Track 2: LLM Semantic** | API credits | ✅ Yes | Deep contextual evaluation, implied skills |
| **Hybrid: Pre-Filter → LLM** | Reduced | ✅ Yes | Balanced — local culls weak CVs, LLM handles survivors |

### How Hybrid saves tokens

Track 1 scores every CV locally first. Only CVs clearing a configurable threshold (default 40/100) are sent to the LLM. On a typical 341-CV batch with a noisy applicant pool, this reduces API calls by 40–70%.

---

## 📊 Scoring System

All scores are computed by a deterministic Python scorer — the LLM extracts structured information only, never generates numbers.

| Component | Weight | How Calculated |
|---|---|---|
| Skills Match | 35 pts | Matched must-have JD skills ÷ total must-have skills |
| Experience | 20 pts | Extracted years vs JD experience range |
| Education | 15 pts | Degree level vs JD minimum requirement |
| Projects | 15 pts | Number of relevant projects found in CV |
| Domain Expertise | 10 pts | Domain keyword match against JD domain field |
| Certifications | 5 pts | Matched certification keywords |

### Fit Categories

| Category | Score Range |
|---|---|
| Exceptional Fit | 85–100 |
| Strong Fit | 70–84 |
| Moderate Fit | 55–69 |
| Potential Fit | 40–54 |
| Low Fit | 0–39 |

### Optional Filter Layer

After scoring, an optional filter layer applies flat adjustments:

- **Priority trait detected → +15 points**
- **Exclusion trait detected → −30 points**

Score is clamped to 0–100. Fit category is recomputed. The AI only detects whether a trait is present; the arithmetic is pure Python.

---

## 📄 Job Description (JD) Format Guide

The JD is the single most important input. A well-structured JD produces accurate skill matching.

### File Format

- ✅ Upload as `.docx` (Microsoft Word) only
- ❌ PDF not accepted — PDF text extraction is fragile
- ❌ Plain `.txt` not accepted

### Recommended Structure

```
Mandatory Technical Skills (Must-Haves)
• QGIS
• ArcGIS
• Remote Sensing
• Python (pandas, geopandas)
• Image classification

Preferred Skills (Nice-to-Have)
• Google Earth Engine (GEE)
• GDAL
• Deep learning for remote sensing

Education
Master's degree in Remote Sensing, Geoinformatics, or related field

Experience
2 to 3 years of professional working experience in Geospatial projects
```

### Section Headers CVRadar Recognises

| Section | Recognised Headers |
|---|---|
| Must-Have | Must-Have, Mandatory, Required Skills, Core Skills, Essential, Technical Skills |
| Nice-to-Have | Nice-to-Have, Preferred, Good to Have, Desirable, Additional Skills, Added Advantage |
| Education | Education, Qualification, Degree, Academic |
| Experience | Experience, Work Experience, Professional Experience, Years of |
| Domain | Domain, Sector, Industry, Field of |
| Certifications | Certifications, License, Accreditation |

### Good vs Poor JD Examples

**✅ Good — bullet points with specific tools:**
```
• QGIS
• ArcGIS
• Remote Sensing
• Python (pandas, geopandas, GDAL)
```

**❌ Poor — vague sentences (no extractable keywords):**
```
Must have a great understanding of geospatial concepts and tools
for data analysis and mapping solutions in various environments.
```

> **Tip:** On Track 1 (local), always use bullet-point format. On Track 2 (LLM), natural prose JDs also work well since the LLM reads the full context.

---

## 🎯 Priority & Exclusion Filters

Filters are optional. Leave both boxes blank to skip the filter layer entirely.

### Priority Traits (+15 points)

Reward candidates with specific desirable strengths beyond the core JD:

```
GEE experience, ISRO background, peer-reviewed publications, crop classification
```

| Example | What it does |
|---|---|
| `ISRO background, NRSC experience` | Rewards government RS institute background |
| `peer-reviewed publications` | Rewards academic research output |
| `Google Earth Engine, GEE` | Rewards specific tool beyond must-haves |
| `open-source contributions` | Rewards open source activity |
| `hyperspectral, LiDAR` | Rewards advanced sensor experience |

### Exclusion Traits (−30 points)

Three types of exclusion rules are supported:

**Type A — Experience thresholds (numeric):**

| Example | Effect |
|---|---|
| `freshers not required` | Excludes experience < 1 year |
| `less than 2 years` | Excludes experience < 2 years |
| `experience more than 7 years` | Excludes experience > 7 years |
| `entry level` | Excludes experience < 2 years |
| `1 to 5 years` | Excludes candidates within that range |

**Type B — Role / title keywords:**

| Example | Effect |
|---|---|
| `Business Analyst` | Penalises Business Analyst role/title |
| `Data Analyst not required` | Same — 'not required' is stripped |
| `BPO, voice support` | Penalises non-technical backgrounds |

**Type C — Career stage keywords:**

| Example | Effect |
|---|---|
| `intern` | Penalises intern-only profiles |
| `trainee` | Maps to experience < 2 years |
| `director level` | Maps to experience > 12 years |

### Full Example

```
Priority Traits:
GEE experience, ISRO background, peer-reviewed publications, crop classification

Exclusion Traits:
freshers not required, Business Analyst, Data Analyst not required, experience more than 7 years
```

> ⚠️ **Only use job-relevant criteria.** Filters based on age, gender, religion, caste, nationality, marital status, disability, or any protected characteristic are discriminatory and must not be used.

---

## 📋 Excel Output Columns

| Column | Description |
|---|---|
| Rank | Candidate rank by Final Score (1 = highest) |
| File Name | Full original filename — no truncation |
| Candidate Name | Extracted from CV text |
| Primary Domain | Academic / professional stream detected from CV |
| Experience (Yrs) | Total professional experience in years |
| Education | Degree level (Track 1) or full degree sentence (Track 2) |
| Skills Matched | JD must-have skills found in the CV |
| Skills Missing | JD must-have skills NOT found in the CV |
| Projects | Top 3–5 project titles from the CV |
| Final Score | 0–100 deterministic score after filter adjustments |
| Fit Category | Exceptional / Strong / Moderate / Potential / Low Fit |
| Processing Track | Track 1 Local / Track 2 (Claude) / Degraded to Local |
| Filter Note | Explanation of any priority/exclusion adjustment |

---

## 💰 API Cost Estimates

| Provider + Model | Cost per CV | 341 CVs |
|---|---|---|
| Claude Haiku 4.5 | ~$0.004 | ~$1.30 |
| Gemini 2.5 Flash (no thinking) | ~$0.003 | ~$1.00 |
| GPT-4o Mini | ~$0.005 | ~$1.70 |
| Track 1 Local | $0.00 | $0.00 |

> Estimates assume ~2,000 input tokens + ~500 output tokens per CV. Actual cost varies by CV length and whether filters are active. Thinking tokens (Gemini 2.5 Pro) are billed at output rates and are capped in CVRadar to minimise spend.

---

## 🔒 Security & Privacy

- **API keys** entered in the sidebar are held only in the user's browser session (`st.session_state`) — never written to disk, never logged
- **Session isolation** — each browser tab gets a UUID; concurrent users cannot access each other's data or checkpoint ledgers
- **PII masking** — all email addresses and phone numbers are replaced with `[EMAIL MASKED]` and `[PHONE MASKED]` before any text is sent to the LLM
- **No telemetry** — CVRadar sends no usage data anywhere beyond the LLM API calls you explicitly trigger

---

## 🔧 Troubleshooting

| Problem | Solution |
|---|---|
| 0 candidates processed | Checkpoint Recovery has all hashes from a previous run on that track. Click **Reset This Session** and re-run. |
| Streams show Other / Undetected | `domain_taxonomy.txt` is missing from `src/`. Copy it from the repository. Verify it is > 10 KB. |
| 503 / rate-limit errors | Increase Inter-request delay slider to 3.0 sec. The retry engine retries up to 5× with exponential backoff. |
| Education pie shows full sentences | Upgrade to v3 — it includes `normalise_education_level()` that maps full sentences to clean labels. |
| JD skills not matching CVs | Expand **Parsed JD Requirements** after uploading. If must-have skills shows full sentences, restructure JD to use bullet points. |
| `st.secrets` error on local run | Harmless — the app falls back to `.env` automatically. Ensure `.env` exists with correct key names. |
| App shows Nexus v2 instead of CVRadar | Old `app.py` was not replaced. Open `app.py` and verify line 3 reads `CVRadar v3`. |
| Streamlit opens Vim for merge messages | Run `git config --global core.editor notepad` to switch to Notepad. |

---

## 📦 Batch Strategy for 300+ CVs

1. Split uploads into **100–150 CVs per run** (browser memory constraint on Streamlit Cloud)
2. Download the Excel report after each batch
3. On the next run, Checkpoint Recovery automatically skips already-processed CVs
4. Upload all Excel files to **Batch Analytics** to generate a merged cross-batch report

> On Track 2 with Claude Haiku at 1.5 sec inter-request delay, a 341-CV run takes approximately 20–25 minutes and costs approximately $1.30.

---

## 🌐 Deployment

### Streamlit Community Cloud (Free)

1. Push this repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select your repository and `app.py`
4. In **Settings → Secrets**, add your API keys:
   ```toml
   GEMINI_API_KEY = "your_key"
   ANTHROPIC_API_KEY = "your_key"
   OPENAI_API_KEY = "your_key"
   ```
5. Deploy

> Free tier has ~1 GB shared RAM and goes to sleep after inactivity. Suitable for demos and small teams.

### Local Network (LAN)

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Anyone on your network can access it at `http://YOUR_IP:8501`.

---

## 🤝 Contributing

Contributions are welcome. CVRadar is MIT-licensed and fully open source.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Follow the existing module structure
4. New LLM providers go in `src/llm_provider.py`
5. Domain taxonomy additions go in `src/domain_taxonomy.txt` using the format:
   ```
   GROUP | Canonical Name | synonym1, synonym2, synonym3
   ```
6. Do not commit `.env` files, API keys, or candidate CV data
7. Open a Pull Request with a clear description

### .gitignore (recommended)

```gitignore
.env
data/
__pycache__/
*.pyc
*.pyo
.streamlit/secrets.toml
```

---

## 📜 Licence

```
MIT License

Copyright (c) 2025 Sobhan Mohanty

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

---

## 👤 Author

**Sobhan Mohanty**  
Senior Geospatial Data Scientist & ML Engineer  
Geospatial and AI Lead — SatSure, Bengaluru

[![GitHub](https://img.shields.io/badge/GitHub-sobhanraspberrypi--svg-black?logo=github)](https://github.com/sobhanraspberrypi-svg)

---

*CVRadar v3 — Built with Streamlit · Powered by Claude / Gemini / OpenAI · MIT Licensed*
