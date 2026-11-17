"""Entry point — `python main.py` then open http://127.0.0.1:8000."""
from __future__ import annotations
import uvicorn
from tools.ollama_client import get_client, OllamaError


def main():
    try:
        c = get_client()
        c.ensure_ready()
        print(f"[VentureOS] {type(c).__name__} ready — model: {c.model}")
    except OllamaError as e:
        print("\n[WARN]  MODEL PROVIDER NOT READY\n" + "-" * 60 + f"\n{e}\n" + "-" * 60)
        print("The API will still start, but agents will error until fixed.\n")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
