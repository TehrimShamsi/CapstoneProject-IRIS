"""
Shared configuration for IRIS backend.
Centralizes paths and settings.
"""
from pathlib import Path
import os

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"

# Data subdirectories
PDFS_DIR = DATA_DIR / "pdfs"
SESSIONS_DIR = DATA_DIR / "sessions"
MEMORY_BANK_DIR = DATA_DIR / "memory_bank"
PAPERS_METADATA_DIR = DATA_DIR / "papers"

# Create all necessary directories
for directory in [PDFS_DIR, SESSIONS_DIR, MEMORY_BANK_DIR, PAPERS_METADATA_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# API Keys and Model Settings
GOOGLE_API_KEY = os.getenv("AIzaSyBEBnqat3u_UjT5Wh7tKCYeMiNOtCXPt5M")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
MAX_TOKENS_DEFAULT = int(os.getenv("MAX_TOKENS_DEFAULT", "1024"))

# Feature flags
USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "").lower() in ("1", "true", "yes")