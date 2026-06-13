# Nexus v2 – AI-Powered Talent Intelligence Platform

## Overview

Nexus v2 is an AI-powered Talent Intelligence and Resume Screening platform designed to help recruiters, HR teams, hiring managers, and talent acquisition professionals evaluate large volumes of resumes against a Job Description (JD) in a scalable and explainable manner.

The platform combines Large Language Models (LLMs), structured candidate evaluation, explainable scoring, and talent analytics to transform traditional resume screening into a data-driven recruitment workflow.

Unlike conventional Applicant Tracking Systems (ATS), Nexus v2 provides:

* AI-assisted candidate evaluation
* Explainable scoring
* Talent intelligence dashboards
* Skill gap analysis
* Batch analytics across hundreds of resumes
* Recruiter-friendly exports

---

# Key Features

## Candidate Screening

* Upload Job Description (PDF/DOCX)
* Upload candidate resumes (PDF/DOCX)
* Process 100+ resumes in a batch
* Strict and Flexible matching modes
* Duplicate detection
* Resume parsing and text extraction

---

## Explainable AI Scoring

Candidates are scored across:

| Component        | Weight |
| ---------------- | ------ |
| Skills Match     | 35     |
| Experience       | 20     |
| Education        | 15     |
| Projects         | 15     |
| Domain Expertise | 10     |
| Certifications   | 5      |

Total Score = 100

Fit Categories:

* Exceptional Fit
* Strong Fit
* Moderate Fit
* Potential Fit
* Low Fit

---

## Talent Intelligence Dashboard

Analyze talent pools using:

* Skill inventory
* Missing skills analysis
* Domain expertise distribution
* Certification analysis
* Education distribution
* Talent gap reports

---

## Recruitment Dashboard

Visualize:

* Candidate funnel
* Score distribution
* Fit category distribution
* Top candidate leaderboard
* Shortlist recommendations

---

## Batch Analytics

Merge multiple screening reports.

Example:

100 resumes
+
100 resumes
+
100 resumes
+
100 resumes
+
100 resumes

=

500 candidate talent intelligence report

Features:

* Merge reports
* Remove duplicates
* Re-rank candidates
* Cross-batch analytics
* Consolidated reporting

---

# System Architecture

Resume Upload
↓
Resume Parser
↓
JD Builder
↓
Gemini Evaluation Engine
↓
Structured Candidate Profile
↓
Scoring Engine
↓
Reporting Engine
↓
Recruitment Dashboard
↓
Talent Intelligence Dashboard

---

# Repository Structure

nexus-v2/

├── app.py

├── config.py

├── requirements.txt

├── README.md

├── .env.example

│

├── src/

│ ├── parser.py

│ ├── schemas.py

│ ├── utils.py

│

│ ├── jd_builder.py

│ ├── evaluator.py

│ ├── scorer.py

│

│ ├── reporting.py

│ ├── analytics.py

│ ├── dashboard.py

│

│ ├── retry_engine.py

│ ├── checkpoint_manager.py

│ └── status_tracker.py

│

├── data/

│ ├── uploads/

│ ├── exports/

│ └── cache/

│

└── logs/

---

# Installation

Clone the repository:

git clone https://github.com/yourusername/nexus-v2.git

cd nexus-v2

Install dependencies:

pip install -r requirements.txt

---

# Configuration

Create a .env file:

GEMINI_API_KEY=YOUR_API_KEY

---

# Run Application

streamlit run app.py

---

# Output

The platform generates:

* Ranked candidate list
* Executive recruitment summary
* Recruiter shortlist
* Skill inventory
* Talent gap report
* Excel report export
* Batch analytics report

---

# Example Use Cases

## Internal HR Teams

* Resume screening
* Hiring support
* Talent intelligence

## GIS & Remote Sensing

* Geospatial hiring
* EO analytics hiring
* Climate intelligence hiring

## Sustainability

* ESG hiring
* Carbon markets
* Climate risk teams

## Data Science

* ML engineers
* Data scientists
* Analytics teams

## AI / ML

* LLM engineers
* GenAI specialists
* AI researchers

## General Recruitment

* Domain-independent recruitment workflows

---

# Reliability Features

* Retry engine
* Checkpoint recovery
* Duplicate detection
* Batch processing
* Resume failure tracking
* Processing status monitoring

---

# Future Roadmap

* Multi-language resume support
* ATS integrations
* Recruiter collaboration
* Interview recommendation engine
* Talent market benchmarking
* Agentic recruiting workflows
* AI hiring assistant

---

# Technology Stack

Frontend:

* Streamlit

AI:

* Google Gemini

Data Processing:

* Pandas
* NumPy

Visualization:

* Plotly

File Processing:

* PyPDF2
* python-docx

Data Validation:

* Pydantic

Exports:

* OpenPyXL

---

# Author

Sobhan Mishra

Geo-Spatial Manager | Sustainability & Climate Analytics | AI for Earth Observation | Talent Intelligence Systems

---

# License

MIT License
