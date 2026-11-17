import os, sys
from pathlib import Path
os.environ.setdefault("MODEL_PROVIDER", "ollama")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
