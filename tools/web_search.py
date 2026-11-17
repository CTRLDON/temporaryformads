"""Web search — ddgs primary, HTML fallback, query simplification."""
from __future__ import annotations
import time
from typing import Any


def _ddgs(query: str, max_results: int):
    try:
        from ddgs import DDGS
    except ImportError:
        return None
    try:
        with DDGS() as d:
            raw = list(d.text(query, max_results=max_results))
        out = [{"title": r.get("title", ""),
                "url": r.get("href") or r.get("url", ""),
                "snippet": r.get("body", "")}
               for r in raw if r.get("href") or r.get("url")]
        return out or None
    except Exception:
        return None


def _html(query: str, max_results: int):
    try:
        from urllib.parse import quote_plus
        import httpx
        from bs4 import BeautifulSoup
        r = httpx.get(
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
            timeout=15, headers={"User-Agent": "Mozilla/5.0 VentureOS"},
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for link in soup.select(".result")[:max_results]:
            a = link.select_one(".result__a")
            if a:
                out.append({"title": a.get_text(strip=True),
                            "url": a.get("href", ""), "snippet": ""})
        return out or None
    except Exception:
        return None


def _variants(query: str) -> list[str]:
    q = query.strip()
    variants = [q]
    lower = q.lower()
    if " for " in lower:
        i = lower.index(" for ")
        before, after = q[:i], q[i + 5:]
        keyword = before.split()[0] if before.split() else ""
        variants.append(f"{after} {keyword}".strip())
        variants.append(after.strip())
    words = q.split()
    if len(words) > 6:
        variants.append(" ".join(words[-5:]))
    seen, out = set(), []
    for v in variants:
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def search(query: str, max_results: int = 6) -> dict[str, Any]:
    errors = []
    for variant in _variants(query):
        for attempt in range(2):
            res = _ddgs(variant, max_results)
            if res:
                return {"results": res, "error": None, "query_used": variant}
            if attempt == 0:
                time.sleep(0.8)
        res = _html(variant, max_results)
        if res:
            return {"results": res, "error": None, "query_used": variant}
        errors.append(f"'{variant[:40]}…' no results")
    return {"results": [], "error": " | ".join(errors) or "all failed",
            "query_used": query}
