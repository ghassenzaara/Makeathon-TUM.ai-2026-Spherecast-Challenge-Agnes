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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
OPENCORPORATES_API_KEY = os.getenv("OPENCORPORATES_API_KEY", "")

# --- Database ---
DB_PATH = _PROJECT_ROOT.parent / "database" / "db.sqlite"  # database/db.sqlite

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
ONTOLOGY_DIR = _PROJECT_ROOT / "backend" / "ontology"

# --- Rate Limiting ---
SCRAPE_DELAY_SECONDS = 1.0  # Delay between web scraping requests

# --- Attribute extraction ---
ATTRIBUTE_EXTRACTION_BATCH_SIZE = int(os.getenv("ATTRIBUTE_EXTRACTION_BATCH_SIZE", "25"))
MAX_LLM_CALLS_PER_RUN = int(os.getenv("MAX_LLM_CALLS_PER_RUN", "60"))

# --- Clustering ---
LINK_SIMILARITY_THRESHOLD = float(os.getenv("LINK_SIMILARITY_THRESHOLD", "0.70"))
