from pathlib import Path

# ======================================================
# PROJECT PATHS
# ======================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache"

LOG_DIR = BASE_DIR / "logs"

MASTER_LEDGER = CACHE_DIR / "nexus_master.csv"
FAILED_LEDGER = CACHE_DIR / "failed_resumes.csv"

# ======================================================
# GEMINI CONFIGURATION
# ======================================================

DEFAULT_MODEL = "gemini-2.5-flash"

AVAILABLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro"
]

TEMPERATURE = 0.1

MAX_RETRIES = 5

INITIAL_RETRY_DELAY = 5

# ======================================================
# BATCH PROCESSING
# ======================================================

SAFE_BATCH_SIZE = 100

CHECKPOINT_INTERVAL = 1

# ======================================================
# SCORING WEIGHTS
# ======================================================

SCORING_WEIGHTS = {
    "skills": 35,
    "experience": 20,
    "education": 15,
    "projects": 15,
    "domain": 10,
    "certifications": 5
}

# ======================================================
# FIT CATEGORIES
# ======================================================

FIT_CATEGORIES = {
    "Exceptional Fit": (90, 100),
    "Strong Fit": (80, 89),
    "Moderate Fit": (65, 79),
    "Potential Fit": (50, 64),
    "Low Fit": (0, 49)
}

# ======================================================
# STATUS VALUES
# ======================================================

STATUS_QUEUED = "Queued"
STATUS_PROCESSING = "Processing"
STATUS_SUCCESS = "Success"
STATUS_FAILED = "Failed"
STATUS_RETRIED = "Retried"

# ======================================================
# FILE FORMATS
# ======================================================

SUPPORTED_RESUME_TYPES = [
    ".pdf",
    ".docx"
]

SUPPORTED_JD_TYPES = [
    ".pdf",
    ".docx"
]

# ======================================================
# EXPORT
# ======================================================

EXPORT_FILE_NAME = "nexus_candidate_report.xlsx"
EXPORT_SHEET_NAME = "Candidate_Evaluation"

# ======================================================
# APP INFO
# ======================================================

APP_TITLE = "Nexus v2"

APP_SUBTITLE = (
    "AI-Powered Talent Intelligence Platform"
)