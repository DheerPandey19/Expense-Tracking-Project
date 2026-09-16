from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

import httpx

from app.config import settings


def _resolve_date(text: str) -> date | None:
    lower = text.lower()
    if "yesterday" in lower:
        return date.today() - timedelta(days=1)
    if "today" in lower:
        return date.today()
    return None

def _category_from_text(
    text: str,
    categories: list[dict[str, Any]],
) -> int | None:
    lower = text.lower()
    for category in categories:
        name = str(category["name"]).lower()
        if re.search(rf"\b{re.escape(name)}\b", lower):
            return int(category["id"])
    return None

def parse_fallback(text: str, categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract amount, date, and an explicitly mentioned category."""
    chunks = [c.strip() for c in re.split(r"\band\b", text, flags=re.I) if c.strip()]
    drafts: list[dict[str, Any]] = []
    for chunk in chunks:
        match = re.search(r"(\d+(?:\.\d+)?)", chunk)
        if not match:
            continue
        amount_str = match.group(1)
        amount = float(amount_str)
        if amount <= 0:
            continue
        resolved = _resolve_date(chunk)
        note = chunk
        note = re.sub(rf"\b{re.escape(amount_str)}\b", " ", note, count=1)
        note = re.sub(r"\b(yesterday|today)\b", " ", note, flags=re.I)
        drafts.append(
            {
                "amount": amount,
                "category_id": _category_from_text(chunk, categories),
                "date": resolved.isoformat() if resolved else None,
                "note": " ".join(note.split()).strip()[:240],
                "confidence": "low",
            }
        )
    return drafts


def _parse_llm(text: str, categories: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    if not settings.openai_api_key:
        return None

    cat_lines = ", ".join(f'{c["id"]}:{c["name"]}' for c in categories)
    system = (
        "You extract expense drafts from a short user message about spending. "
        "Return ONLY valid JSON with this shape: "
        '{"drafts":[{"amount":number,"category_id":number|null,'
        '"date":"YYYY-MM-DD"|null,"note":string,"confidence":"high"|"low"}]}. '
        f"Allowed categories (id:name): {cat_lines}. "
        "Pick category_id by meaning of merchant/brand/activity "
        "(e.g. Swiggy/Zomato/coffee → Food; Uber/Ola/petrol → Transport; "
        "rent → Housing; Netflix/movie → Entertainment). "
        "Do NOT invent categories. If unsure, set category_id null and confidence low. "
        "Resolve yesterday/today relative to today's date. "
        "Split multiple expenses (e.g. joined by 'and'). Never invent amounts."
    )
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Today is {date.today().isoformat()}. Message: {text}",
            },
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            res = client.post(
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        drafts = data.get("drafts")
        if not isinstance(drafts, list):
            return None
        cleaned: list[dict[str, Any]] = []
        valid_ids = {int(c["id"]) for c in categories}
        for d in drafts:
            amount = float(d.get("amount", 0))
            if amount <= 0:
                continue
            cid = d.get("category_id")
            if cid is not None:
                cid = int(cid)
                if cid not in valid_ids:
                    cid = None
            cleaned.append(
                {
                    "amount": amount,
                    "category_id": cid,
                    "date": d.get("date"),
                    "note": str(d.get("note") or "")[:240],
                    "confidence": (
                        d.get("confidence")
                        if d.get("confidence") in ("high", "low")
                        else ("high" if cid else "low")
                    ),
                }
            )
        return cleaned
    except Exception:
        return None


def parse_expenses(text: str, categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = text.strip()
    if not text:
        return []
    llm = _parse_llm(text, categories)
    if llm is not None:
        return llm
    return parse_fallback(text, categories)
