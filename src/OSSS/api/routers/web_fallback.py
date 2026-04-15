# src/OSSS/api/routers/web_fallback.py
from __future__ import annotations

import os
import re
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ai/admin", tags=["ai-admin"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
GEMINI_API_BASE = os.getenv(
    "GEMINI_API_BASE",
    "https://generativelanguage.googleapis.com/v1beta"
).strip()

PERSON_NAME_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-z'\-]+){1,3})\b"
)

NEGATIVE_NAME_PHRASES = {
    "Board Workshop",
    "Regular Meeting",
    "School District",
    "Board Report",
    "Student Services",
}


class WebFallbackRequest(BaseModel):
    query: str
    index: str = "main"
    reason: Dict[str, Any] = Field(default_factory=dict)


class WebFallbackResponse(BaseModel):
    answer: str
    confidence: float
    sources: List[str] = Field(default_factory=list)
    extracted_names: List[str] = Field(default_factory=list)


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip())


def _extract_candidate_names(text: str) -> List[str]:
    names: List[str] = []
    for match in PERSON_NAME_RE.findall(text or ""):
        n = _normalize_name(match)
        if len(n.split()) < 2:
            continue
        if n in NEGATIVE_NAME_PHRASES:
            continue
        names.append(n)

    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _build_prompt(query: str) -> str:
    return f"""
You are a web fallback resolver.

Task:
Answer this query using current public web knowledge:
{query}

Requirements:
- Prefer official sources first.
- If the query is about school board members, look for the district site or official meeting pages.
- Return the likely current names if available.
- If uncertain, say so briefly.
- Include source URLs inline at the end under a heading "Sources:".
- Keep the answer concise and factual.
""".strip()


async def _call_gemini(query: str) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")

    url = f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _build_prompt(query)}
                ]
            }
        ]
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get("candidates") or []
    if not candidates:
        return ""

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text_parts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    return "\n".join(tp for tp in text_parts if tp).strip()


def _extract_sources(answer: str) -> List[str]:
    return re.findall(r"https?://[^\s)]+", answer or "")


def _score_answer(answer: str, names: List[str], sources: List[str]) -> float:
    score = 0.0
    lowered = (answer or "").lower()

    if answer:
        score += 0.25
    if len(names) >= 3:
        score += 0.35
    elif len(names) >= 2:
        score += 0.2
    if sources:
        score += 0.2
    if "uncertain" not in lowered and "not sure" not in lowered:
        score += 0.1

    return min(score, 0.99)


@router.post("/web-fallback", response_model=WebFallbackResponse)
async def web_fallback(req: WebFallbackRequest) -> WebFallbackResponse:
    answer = await _call_gemini(req.query)

    sources = _extract_sources(answer)
    names = _extract_candidate_names(answer)
    confidence = _score_answer(answer, names, sources)

    return WebFallbackResponse(
        answer=answer,
        confidence=confidence,
        sources=sources,
        extracted_names=names[:10],
    )