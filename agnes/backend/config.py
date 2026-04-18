"""
Agnes Configuration Module.

Loads environment variables and defines project-wide constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent  # agnes/
load_dotenv(_PROJECT_ROOT / ".env")

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

# --- Database ---
DB_PATH = _PROJECT_ROOT.parent / "db.sqlite"  # Root-level db.sqlite

# --- Semantic Matching ---
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))

# --- Confidence Scoring ---
CONFIDENCE_HIGH = 75    # >= 75 → high confidence recommendation
CONFIDENCE_MEDIUM = 50  # >= 50 → recommend with warnings
# < 50 → flag for human review

# --- Paths ---
DATA_DIR = _PROJECT_ROOT / "data"
ENRICHMENT_CACHE_DIR = DATA_DIR / "enrichment_cache"
ENRICHMENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# --- Rate Limiting ---
SCRAPE_DELAY_SECONDS = 1.0  # Delay between web scraping requests
