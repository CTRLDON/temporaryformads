"""Founder agent — clarification-first, Python-tracked required fields."""
from __future__ import annotations
import json
import re
from agents.base import BaseAgent

REQUIRED_FIELDS = ["budget", "skills", "education", "target_market"]
MAX_QUESTIONS = 10

CLARIFICATION_QUESTIONS = [
    "What specific problem does this solve, and why does it matter? What's the pain point you're addressing?",
    "What makes this different from what already exists? What's your unique angle or unfair advantage?",
]

FIELD_HINTS = {
    "budget": [r"\b\d+\s*(?:egp|usd|eur|gbp|\$|€|£|k|m|thousand|million)\b",
               r"\b(?:budget|can spend|have about|have around|can invest)\b"],
    "skills": [r"\b(?:i have|i've|i can|i know|i built|i ran|i coded|i designed|i developed)\b",
               r"\b(?:skills?|experienced?|background in|worked on|built|hire)\b"],
    "education": [r"\b(?:university|college|degree|bachelor|master|phd|mba|studied|graduated|self-taught)\b"],
    "target_market": [r"\b(?:consumer|customer|business|user|people|student|professional|audience|market|client|smb|enterprise)\b"],
}

QUESTION_PATTERNS = {
    "budget": r"\b(?:budget|spend|invest|cost|money|funding|capital|cash|afford|runway)\b",
    "skills": r"\b(?:skills?|experience|expertise|background|build yourself|hire|implement)\b",
    "education": r"\b(?:educat|background|stud|degree|qualif|school|trained|graduated)\b",
    "target_market": r"\b(?:who specifically|audience|customer|serve|target market|consumer|client)\b",
}


def _assistant_asks_field(text):
    for field, pattern in QUESTION_PATTERNS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            return field
    return None


def _fields_answered(history):
    answered = set()
    for i, msg in enumerate(history):
        if msg.get("role") != "assistant":
            continue
        field = _assistant_asks_field(msg.get("content", ""))
        if not field:
            continue
        if i + 1 < len(history) and history[i + 1].get("role") == "user":
            if len((history[i + 1].get("content") or "").strip()) >= 2:
                answered.add(field)
    return answered


def _questions_asked(history):
    count = 0
    for m in history:
        if m.get("role") != "assistant":
            continue
        text = m.get("content", "") or ""
        if any(text.strip().startswith(c[:40]) for c in CLARIFICATION_QUESTIONS):
            count += 1
        elif _assistant_asks_field(text):
            count += 1
    return count


class FounderAgent(BaseAgent):
    name = "founder_understanding"
    description = "Clarifies the idea first, then gathers required founder details."
    system_prompt = "You are a warm, curious product partner. Ask ONE question at a time."

    def run(self, context):
        return self.next_question(context.get("idea", ""), context.get("history", []))

    def next_question(self, idea, history):
        answered = _fields_answered(history)
        missing = [f for f in REQUIRED_FIELDS if f not in answered]
        asked = _questions_asked(history)

        if asked < len(CLARIFICATION_QUESTIONS):
            return {"question": CLARIFICATION_QUESTIONS[asked],
                    "ready_for_brief": False,
                    "missing_fields": missing,
                    "answered_fields": sorted(answered),
                    "phase": "clarify"}

        if not missing or asked >= MAX_QUESTIONS:
            return {"question": "", "ready_for_brief": True,
                    "missing_fields": missing,
                    "answered_fields": sorted(answered),
                    "phase": "ready"}

        target = missing[0]
        try:
            question = self._compose_question(target, idea)
        except Exception:
            question = self._fallback_question(target)
        return {"question": question, "ready_for_brief": False,
                "missing_fields": missing,
                "answered_fields": sorted(answered),
                "phase": "details"}

    def _compose_question(self, field, idea):
        prompts = {
            "budget": "how much money they can realistically spend to start.",
            "skills": "what skills they personally bring to this venture.",
            "education": "their relevant educational or professional background.",
            "target_market": "who specifically they want to serve as their first customers.",
        }
        result = self._chat_json(
            {"venture_idea": idea, "field": field, "ask_about": prompts[field],
             "instruction": "Write ONE short natural question, max 20 words. Must clearly reference the topic being asked about."},
            schema_hint='{"question": "string"}')
        q = str(result.get("question", "")).strip().strip('"').strip()
        if not q or _assistant_asks_field(q) != field:
            return self._fallback_question(field)
        return q

    @staticmethod
    def _fallback_question(field):
        return {
            "budget": "What budget can you realistically spend to get this off the ground?",
            "skills": "What skills do you personally bring to this venture?",
            "education": "What's your relevant educational or professional background?",
            "target_market": "Who specifically is your first target customer or audience?",
        }[field]

    def answer_question(self, venture, question, history=None):
        history = history or []
        brief = venture.get("brief") or {}
        system = (
            "You are a helpful, direct business advisor. "
            "Answer the user's question concisely (2-4 sentences) and specifically. "
            "Use the venture context when relevant; answer general questions generally.\n\n"
            f"Venture idea: {venture.get('idea') or ''}\n"
            f"Business brief: {json.dumps(brief, ensure_ascii=False)}\n"
        )
        messages = []
        for h in history[-10:]:
            role = h.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": h.get("content", "")})
        messages.append({"role": "user", "content": question})
        try:
            return self.client.chat(messages, system=system)
        except Exception as e:
            raise RuntimeError(f"Q&A failed: {e}")

    def analyze_answers(self, answers):
        schema = '{"budget": "string", "skills": "string", "education": "string", "target_market": "string"}'
        return self._chat_json({
            "raw_answers": answers,
            "instruction": (
                "Normalize the founder's raw answers into clean, specific, human-readable phrases. "
                "Do NOT invent facts. Return the SAME four keys.\n"
                "- budget: '<comma-number> <CURRENCY CODE>'. 'like a million dollars' -> '1,000,000 USD'. "
                "'maybe 5000 EGP' -> '5,000 EGP'. Empty -> 'Not specified'.\n"
                "- skills: '<level> experience in <domain>'. Levels: Minimal, Some, Moderate, Extensive, Expert. "
                "Empty -> 'Not specified'.\n"
                "- education: '<degree> in <field> at <institution>' (bachelor -> BSc/BEng/BA, master -> MSc/MA/MBA, phd -> PhD). "
                "'self taught' -> 'Self-taught'. Empty -> 'Not specified'.\n"
                "- target_market: concise audience description, title-cased. Empty -> 'Not specified'.\n"
                "Return only the JSON object."
            ),
        }, schema_hint=schema)

    def draft_brief(self, idea, history):
        schema = (
            '{"name": "string", "category": "technology|education|sustainability|creative|productivity|general", '
            '"concept": "string", "problem": "string", "solution": "string", '
            '"target_audience": "string", "business_model": "string", '
            '"budget": "string", "founder_skills": ["string"], "founder_education": "string", '
            '"theme": {"accent": "#RRGGBB", "accent_2": "#RRGGBB", '
            '"background": "#RRGGBB (DARK)", "surface": "#RRGGBB (DARK)", "mood": "string"}, '
            '"assumptions": ["string"], "constraints": ["string"], "open_questions": ["string"]}'
        )
        return self._chat_json({
            "idea": idea, "conversation": history,
            "instruction": "Draft the Business Brief. Quote founder answers verbatim. Never invent facts. For theme: DARK MODE ONLY. background must be #050508 to #141420. surface slightly lighter. accent vibrant. FORBIDDEN: luminance above 20%.",
        }, schema_hint=schema)
