"""Gemini client — mirrors the interface used by tools/ollama_client and orchestrator."""
from __future__ import annotations
import json as _json

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TEMPERATURE

try:
    from google import genai
    from google.genai import types
    _GENAI_IMPORT_ERR = None
except ImportError as e:  # pragma: no cover
    genai = None
    types = None
    _GENAI_IMPORT_ERR = e


class GeminiError(Exception):
    pass


class GeminiClient:
    host = "https://generativelanguage.googleapis.com"

    def __init__(self) -> None:
        if genai is None:
            raise GeminiError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from _GENAI_IMPORT_ERR
        if not GEMINI_API_KEY:
            raise GeminiError("GEMINI_API_KEY is not set in .env")
        self.model = GEMINI_MODEL
        self._client = genai.Client(api_key=GEMINI_API_KEY)

    # -- readiness ---------------------------------------------------------
    def ensure_ready(self) -> bool:
        try:
            self._client.models.generate_content(
                model=self.model,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=1),
            )
            return True
        except Exception as e:
            raise GeminiError(f"Gemini not ready ({self.model}): {e}") from e

    # -- simple generation -------------------------------------------------
    def generate(self, prompt: str, system: str | None = None) -> str:
        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=GEMINI_TEMPERATURE,
                ),
            )
            return resp.text or ""
        except Exception as e:
            raise GeminiError(str(e)) from e

    # -- chat (message list) ----------------------------------------------
    def chat(self, messages: list[dict]) -> str:
        system_parts, contents = [], []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                contents.append({
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": content}],
                })
        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction="\n\n".join(system_parts) or None,
                    temperature=GEMINI_TEMPERATURE,
                ),
            )
            return resp.text or ""
        except Exception as e:
            raise GeminiError(str(e)) from e

    # -- JSON-mode chat — matches ResearchAgent.client.chat_json() usage --
    def chat_json(self, messages: list[dict], system: str | None = None,
                  schema_hint: str | None = None) -> dict:
        system_parts = []
        if system:
            system_parts.append(system)
        if schema_hint:
            system_parts.append(
                "Return ONLY valid JSON matching this shape:\n" + schema_hint
            )
        contents = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                contents.append({
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": content}],
                })
        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction="\n\n".join(system_parts) or None,
                    temperature=GEMINI_TEMPERATURE,
                    response_mime_type="application/json",
                ),
            )
            text = (resp.text or "").strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.lstrip().startswith("json"):
                    text = text.lstrip()[4:]
                text = text.rsplit("```", 1)[0].strip()
            return _json.loads(text)
        except Exception as e:
            raise GeminiError(f"chat_json failed: {e}") from e