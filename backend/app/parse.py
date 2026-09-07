from __future__ import annotations

import json
import re
from calendar import monthrange
from datetime import date, timedelta

import httpx

from app.config import settings
from app.models import Category

KEYWORD_MAP: dict[str, list[str]] = {
    "Food": [
        "coffee",
        "cafe",
        "lunch",
        "dinner",
        "breakfast",
        "food",
        "swiggy",
        "zomato",
        "grocery",
        "groceries",
        "snack",
        "restaurant",
        "tea",
        "milk",
        "pizza",
    ],
    "Transport": [
        "uber",
        "ola",
        "rapido",
        "petrol",
        "diesel",
        "fuel",
        "metro",
        "bus",
        "train",
        "cab",
        "auto",
        "parking",
        "toll",
    ],
    "Housing": ["rent", "deposit", "maintenance", "housing", "pg"],
    "Utilities": [
        "electricity",
        "water",
        "wifi",
        "internet",
        "gas",
        "phone",
        "recharge",
        "utility",
        "utilities",
    ],
    "Entertainment": [
        "movie",
        "netflix",
        "spotify",
        "game",
        "concert",
        "ott",
        "entertainment",
    ],
    "Shopping": [
        "amazon",
        "flipkart",
        "myntra",
        "shopping",
        "clothes",
        "shoes",
        "store",
    ],
    "Health": [
        "medicine",
        "pharmacy",
        "doctor",
        "hospital",
        "gym",
        "health",
        "clinic",
    ],
}

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

AMOUNT_RE = re.compile(
    r"(?:(?:rs|inr|₹)\s*)?(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)
SPLIT_RE = re.compile(r"\b(?:and|&|,|;)\b", re.IGNORECASE)


def _today() -> date:
    return date.today()


def resolve_relative_date(text: str, today: date | None = None) -> date:
    today = today or _today()
    lower = text.lower()

    if "day before yesterday" in lower:
        return today - timedelta(days=2)
    if "yesterday" in lower:
        return today - timedelta(days=1)
    if "today" in lower:
        return today
    if "tomorrow" in lower:
        return today + timedelta(days=1)

    last_match = re.search(
        r"last\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        lower,
    )
    if last_match:
        target = WEEKDAYS[last_match.group(1)]
        delta = (today.weekday() - target) % 7
        if delta == 0:
            delta = 7
        return today - timedelta(days=delta)

    for name, weekday in WEEKDAYS.items():
        if re.search(rf"\b{name}\b", lower):
            delta = (today.weekday() - weekday) % 7
            return today - timedelta(days=delta)

    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lower)
    if iso:
        try:
            return date.fromisoformat(iso.group(1))
        except ValueError:
            pass

    dmy = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", lower)
    if dmy:
        day, month = int(dmy.group(1)), int(dmy.group(2))
        year = int(dmy.group(3)) if dmy.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            try:
                return date(year, day, month)
            except ValueError:
                pass

    return today


def _category_by_name(categories: list[Category], name: str) -> Category | None:
    lowered = name.strip().lower()
    for cat in categories:
        if cat.name.lower() == lowered:
            return cat
    return None


def match_category(text: str, categories: list[Category]) -> Category | None:
    lower = text.lower()
    enabled = [c for c in categories if c.enabled]

    for cat in enabled:
        if re.search(rf"\b{re.escape(cat.name.lower())}\b", lower):
            return cat

    for cat_name, keywords in KEYWORD_MAP.items():
        cat = _category_by_name(enabled, cat_name)
        if not cat:
            continue
        for word in keywords:
            if re.search(rf"\b{re.escape(word)}\b", lower):
                return cat

    other = _category_by_name(enabled, "Other")
    return other or (enabled[0] if enabled else None)


def _clean_note(chunk: str, amount: float, when: date) -> str:
    note = chunk
    note = re.sub(r"(?:rs|inr|₹)\s*", "", note, flags=re.IGNORECASE)
    note = re.sub(rf"\b{re.escape(str(int(amount) if amount.is_integer() else amount))}\b", "", note)
    note = re.sub(
        r"\b(yesterday|today|tomorrow|day before yesterday|last\s+\w+|spent|paid|for|on|of)\b",
        "",
        note,
        flags=re.IGNORECASE,
    )
    note = re.sub(r"\s+", " ", note).strip(" -.,")
    return note[:240]


def fallback_parse(text: str, categories: list[Category]) -> list[dict]:
    today = _today()
    chunks = [c.strip() for c in SPLIT_RE.split(text) if c.strip()]
    if not chunks:
        chunks = [text.strip()]

    drafts: list[dict] = []
    for chunk in chunks:
        amounts = AMOUNT_RE.findall(chunk)
        if not amounts:
            continue
        raw = amounts[-1].replace(",", "")
        amount = float(raw)
        when = resolve_relative_date(chunk, today)
        category = match_category(chunk, categories)
        note = _clean_note(chunk, amount, when)
        drafts.append(
            {
                "amount": amount,
                "categoryId": category.id if category else None,
                "date": when,
                "note": note,
                "confidence": 0.7 if category else 0.4,
                "warning": None if category else "Could not match a category",
            }
        )
    return drafts


async def llm_parse(text: str, categories: list[Category]) -> list[dict] | None:
    if not settings.openai_api_key.strip():
        return None

    enabled = [c for c in categories if c.enabled]
    today = _today()
    catalog = [{"id": c.id, "name": c.name} for c in enabled]
    prompt = (
        "Extract expense entries from the user message. "
        "Use only the given category ids. Resolve relative dates against today. "
        "Return JSON only: {\"drafts\":[{\"amount\":number,\"categoryId\":number|null,"
        "\"date\":\"YYYY-MM-DD\",\"note\":string,\"confidence\":0-1,\"warning\":string|null}]}. "
        "Split multiple expenses. Amounts are in the user's local currency."
    )
    payload = {
        "model": settings.openai_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "today": today.isoformat(),
                        "categories": catalog,
                        "text": text,
                    }
                ),
            },
        ],
    }

    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
    except Exception:
        return None

    enabled_ids = {c.id for c in enabled}
    drafts: list[dict] = []
    for item in data.get("drafts") or []:
        try:
            amount = float(item.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0
        category_id = item.get("categoryId")
        if category_id not in enabled_ids:
            category_id = None
        raw_date = item.get("date") or today.isoformat()
        try:
            when = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            when = resolve_relative_date(text, today)
        drafts.append(
            {
                "amount": amount if amount > 0 else None,
                "categoryId": category_id,
                "date": when,
                "note": str(item.get("note") or "")[:240],
                "confidence": float(item.get("confidence") or 0.6),
                "warning": item.get("warning"),
            }
        )
    return drafts or None


async def parse_text(text: str, categories: list[Category]) -> tuple[list[dict], bool]:
    llm_drafts = await llm_parse(text, categories)
    if llm_drafts:
        return llm_drafts, True
    return fallback_parse(text, categories), False


def month_bounds(today: date | None = None) -> tuple[date, date, int, int]:
    today = today or _today()
    start = today.replace(day=1)
    days_in_month = monthrange(today.year, today.month)[1]
    end = today.replace(day=days_in_month)
    return start, end, today.day, days_in_month
