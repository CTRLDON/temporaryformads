from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"
FRONTEND_DIR = BASE_DIR / "frontend"
for p in (DATA_DIR, OUTPUTS_DIR):
    p.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "ventureos.db"

# --- Provider selection ---------------------------------------------------
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "ollama").strip().lower()

# --- Ollama ---------------------------------------------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
OLLAMA_MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "2"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "2"))

# --- Gemini ---------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", str(OLLAMA_TIMEOUT)))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", str(OLLAMA_MAX_RETRIES)))
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", str(OLLAMA_TEMPERATURE)))

STAGES = ["discover", "validate", "build", "commercial", "launch", "operate"]
STAGE_LABELS = {
    "discover": "Discover", "validate": "Validate", "build": "Build",
    "commercial": "Commercial Setup", "launch": "Launch",
    "operate": "Operate & Learn",
}
THEME_BY_CATEGORY = {
    "education": "blue", "technology": "cyan", "sustainability": "teal",
    "creative": "coral", "productivity": "amber", "general": "indigo",
}