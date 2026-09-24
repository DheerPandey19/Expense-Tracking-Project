from contextlib import asynccontextmanager
import secrets

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.db import Base, SessionLocal, engine, get_db, ping_db
from app.expense_service import create_expense_record
from app.models import Category, TelegramPendingExpense
from app.parse import parse_expenses
from app.schemas import ExpenseCreate, ExpenseDraft
from app.seed import seed_categories


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_categories(db)

    yield


app = FastAPI(
    title="Expense Tracker Telegram Bot",
    lifespan=lifespan,
)


def telegram_request(method: str, payload: dict) -> dict:
    url = (
        f"https://api.telegram.org/"
        f"bot{settings.telegram_bot_token}/{method}"
    )

    with httpx.Client(timeout=20) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def send_message(
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    telegram_request("sendMessage", payload)


def confirmation_text(
    drafts: list[dict],
    categories: dict[int, str],
) -> str:
    lines = ["Please confirm these expenses:"]

    for index, draft in enumerate(drafts, start=1):
        category_id = draft["category_id"]
        category_name = categories.get(category_id, "Unknown")
        expense_date = draft.get("date") or "Today"
        note = draft.get("note") or "-"

        lines.extend(
            [
                "",
                f"{index}. Rs. {draft['amount']:.2f}",
                f"Category: {category_name}",
                f"Date: {expense_date}",
                f"Note: {note}",
            ]
        )

    return "\n".join(lines)


def category_lookup(db: Session) -> tuple[list[dict], dict[int, str]]:
    categories = list(
        db.scalars(select(Category).order_by(Category.id)).all()
    )
    category_data = [
        {"id": category.id, "name": category.name}
        for category in categories
    ]
    category_names = {
        category.id: category.name for category in categories
    }
    return category_data, category_names


def parse_drafts_from_text(
    text: str,
    category_data: list[dict],
) -> tuple[list[ExpenseDraft] | None, str | None]:
    raw_drafts = parse_expenses(text, category_data)
    drafts = [ExpenseDraft(**draft) for draft in raw_drafts]

    if not drafts:
        return None, "I could not find an expense amount in that message."

    if any(draft.category_id is None for draft in drafts):
        return (
            None,
            "I could not determine the category. "
            "Please rephrase the expense with more detail.",
        )

    return drafts, None


def find_editing_pending(
    db: Session,
    chat_id: int,
) -> TelegramPendingExpense | None:
    return db.scalar(
        select(TelegramPendingExpense)
        .where(
            TelegramPendingExpense.chat_id == chat_id,
            TelegramPendingExpense.status == "editing",
        )
        .order_by(TelegramPendingExpense.created_at.desc())
    )


def send_confirmation(
    pending: TelegramPendingExpense,
    category_names: dict[int, str],
) -> None:
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Confirm",
                    "callback_data": f"confirm:{pending.id}",
                },
                {
                    "text": "Edit",
                    "callback_data": f"edit:{pending.id}",
                },
                {
                    "text": "Cancel",
                    "callback_data": f"cancel:{pending.id}",
                },
            ]
        ]
    }

    send_message(
        pending.chat_id,
        confirmation_text(pending.payload, category_names),
        keyboard,
    )


def send_edit_prompt(
    pending: TelegramPendingExpense,
    message_id: int | None = None,
) -> None:
    text = (
        "Send the corrected expense in natural language.\n"
        "Example: Spent 400 on dinner yesterday."
    )
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Cancel",
                    "callback_data": f"cancel:{pending.id}",
                },
            ]
        ]
    }

    if message_id is not None:
        telegram_request(
            "editMessageText",
            {
                "chat_id": pending.chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": keyboard,
            },
        )
        return

    send_message(pending.chat_id, text, keyboard)


def apply_drafts_to_pending(
    pending: TelegramPendingExpense,
    drafts: list[ExpenseDraft],
) -> None:
    pending.payload = [
        draft.model_dump(mode="json") for draft in drafts
    ]
    flag_modified(pending, "payload")
    pending.status = "pending"


def handle_message(update: dict, db: Session) -> None:
    message = update.get("message") or {}
    chat_id = int((message.get("chat") or {}).get("id", 0))
    text = str(message.get("text") or "").strip()
    update_id = int(update["update_id"])

    if chat_id != settings.telegram_chat_id:
        return

    if text == "/start":
        send_message(
            chat_id,
            "Send me your spending in natural language.\n"
            "Example: Spent 350 on lunch and 120 on an auto.",
        )
        return

    if not text:
        send_message(chat_id, "Please send a text message.")
        return

    category_data, category_names = category_lookup(db)

    editing = find_editing_pending(db, chat_id)
    if editing is not None:
        drafts, error = parse_drafts_from_text(text, category_data)
        if error is not None:
            send_message(chat_id, f"{error}\n\nOr tap Cancel to abort.")
            return

        apply_drafts_to_pending(editing, drafts)
        db.commit()
        send_confirmation(editing, category_names)
        return

    existing = db.scalar(
        select(TelegramPendingExpense).where(
            TelegramPendingExpense.update_id == update_id
        )
    )

    if existing is not None:
        if existing.status == "pending":
            send_confirmation(existing, category_names)
        return

    drafts, error = parse_drafts_from_text(text, category_data)
    if error is not None:
        send_message(chat_id, error)
        return

    pending = TelegramPendingExpense(
        id=secrets.token_hex(16),
        update_id=update_id,
        chat_id=chat_id,
        payload=[
            draft.model_dump(mode="json")
            for draft in drafts
        ],
        status="pending",
    )

    db.add(pending)
    db.commit()

    send_confirmation(pending, category_names)


def handle_callback(callback: dict, db: Session) -> None:
    callback_id = str(callback["id"])
    data = str(callback.get("data") or "")
    message = callback.get("message") or {}
    chat_id = int((message.get("chat") or {}).get("id", 0))
    message_id = message.get("message_id")

    telegram_request(
        "answerCallbackQuery",
        {"callback_query_id": callback_id},
    )

    if chat_id != settings.telegram_chat_id:
        return

    try:
        action, pending_id = data.split(":", maxsplit=1)
    except ValueError:
        return

    pending = db.get(TelegramPendingExpense, pending_id)

    if pending is None or pending.chat_id != chat_id:
        return

    if pending.status not in ("pending", "editing"):
        telegram_request(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"This request is already {pending.status}.",
            },
        )
        return

    if action == "cancel":
        pending.status = "cancelled"
        db.commit()
        telegram_request(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": "Expense cancelled.",
            },
        )
        return

    if action == "edit":
        if pending.status != "pending":
            return
        pending.status = "editing"
        db.commit()
        send_edit_prompt(pending, message_id=message_id)
        return

    if action == "confirm":
        if pending.status != "pending":
            return

        try:
            for draft in pending.payload:
                body = ExpenseCreate(
                    amount=draft["amount"],
                    category_ids=draft["category_ids"],
                    date=draft.get("date"),
                    note=draft.get("note", ""),
                    tags=draft.get("tags", []),
                )
                create_expense_record(db, body)

            pending.status = "confirmed"
            db.commit()
            result = f"Saved {len(pending.payload)} expense(s)."

        except Exception:
            db.rollback()
            result = "Could not save the expense. Please try again."

        telegram_request(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": result,
            },
        )
        return


@app.get("/health")
def health() -> dict:
    ping_db()
    return {"ok": True}


@app.post("/telegram/webhook")
def telegram_webhook(
    update: dict,
    db: Session = Depends(get_db),
    webhook_secret: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
) -> dict:
    if (
        not settings.telegram_webhook_secret
        or not secrets.compare_digest(
            webhook_secret or "",
            settings.telegram_webhook_secret,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook secret",
        )

    if update.get("message"):
        handle_message(update, db)

    elif update.get("callback_query"):
        handle_callback(update["callback_query"], db)

    return {"ok": True}