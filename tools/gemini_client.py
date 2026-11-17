"""Gemini free-tier client."""
from __future__ import annotations
import json
import time
import os
from typing import Any
import httpx
from tools.ollama_client import OllamaError

NL = chr(10)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "60"))
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))


class GeminiClient:
    def __init__(self, api_key=GEMINI_API_KEY, model=GEMINI_MODEL, timeout=GEMINI_TIMEOUT):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.host = "https://generativelanguage.googleapis.com"

    def list_models(self):
        return [self.model]

    def ensure_ready(self):
        if not self.api_key:
            raise OllamaError(
                "GEMINI_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/app/apikey"
            )
        self._request("Reply with the word ok", system=None, temperature=0, json_mode=False)

    def _request(self, prompt, *, system, temperature, json_mode, num_predict=None):
        url = self.host + "/v1beta/models/" + self.model + ":generateContent?key=" + self.api_key
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        if num_predict:
            payload["generationConfig"]["maxOutputTokens"] = num_predict
        last_err = None
        for _ in range(GEMINI_MAX_RETRIES + 1):
            try:
                r = httpx.post(url, json=payload, timeout=self.timeout)
                if r.status_code == 503:
                    if _ < GEMINI_MAX_RETRIES:
                        time.sleep(2 ** _)
                        continue
                    raise OllamaError(
                        "Gemini 503 UNAVAILABLE (model overloaded). "
                        "Try gemini-3.6-flash or gemini-3.5-flash-lite, "
                        "or wait 30-60s and retry."
                    )
                if r.status_code == 429:
                    raise OllamaError("Gemini rate limit hit. Wait 60s.")
                if r.status_code == 400:
                    raise OllamaError("Gemini 400: " + r.text[:300])
                if r.status_code == 403:
                    raise OllamaError("Gemini 403 key rejected: " + r.text[:200])
                r.raise_for_status()
                data = r.json()
                cands = data.get("candidates") or []
                if not cands:
                    reason = data.get("promptFeedback", {}).get("blockReason", "no candidates")
                    raise OllamaError("Gemini no output: " + str(reason))
                parts = cands[0].get("content", {}).get("parts") or []
                if not parts:
                    raise OllamaError("Gemini empty parts")
                return parts[0].get("text", "")
            except OllamaError:
                raise
            except Exception as e:
                last_err = e
        raise OllamaError("Gemini failed: " + str(last_err))

    def chat(self, messages, *, system=None, temperature=GEMINI_TEMPERATURE, json_mode=False, num_predict=None):
        if not messages:
            raise OllamaError("No messages")
        joined = (NL + NL).join(m.get("content", "") for m in messages)
        return self._request(joined, system=system, temperature=temperature, json_mode=json_mode, num_predict=num_predict)

    def chat_json(self, messages, *, system, schema_hint=None, temperature=0.2):
        sys = system.strip()
        if schema_hint:
            sys = sys + " Return ONLY JSON matching: " + schema_hint
        else:
            sys = sys + " Return ONLY valid JSON."
        raw = ""
        for _ in range(GEMINI_MAX_RETRIES + 1):
            raw = self.chat(messages, system=sys, temperature=temperature, json_mode=True)
            parsed = _extract_json(raw)
            if parsed is not None:
                return parsed
        raise OllamaError("Gemini invalid JSON: " + raw[:300])


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            obj = json.loads(text[start:end+1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None
