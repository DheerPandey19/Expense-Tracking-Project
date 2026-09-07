from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import settings
from app.db import get_db, init_db
from app.models import AppSetting, Category, Expense
from app.parse import month_bounds, parse_text
from app.schemas import (
    CategoryCreate,
    CategoryOut,
    CategorySummary,
    CategoryUpdate,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    ParseRequest,
    ParseResponse,
    SettingsOut,
    SettingsUpdate,
    SummaryOut,
)
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = next(get_db())
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Expense Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _expense_out(row: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=row.id,
        amount=row.amount,
        categoryId=row.category_id,
        date=row.date,
        note=row.note or "",
        source=row.source,
        createdAt=row.created_at.isoformat() if row.created_at else None,
    )


def _get_currency(db: Session) -> str:
    row = db.get(AppSetting, "currency")
    return row.value if row else "INR"


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)) -> SettingsOut:
    return SettingsOut(
        currency=_get_currency(db),
        llmConfigured=bool(settings.openai_api_key.strip()),
    )


@app.put("/api/settings", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsOut:
    if body.currency:
        row = db.get(AppSetting, "currency")
        if row is None:
            db.add(AppSetting(key="currency", value=body.currency.upper()))
        else:
            row.value = body.currency.upper()
        db.commit()
    return get_settings(db)


@app.get("/api/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    rows = db.query(Category).order_by(Category.id).all()
    return [CategoryOut.from_orm_model(c) for c in rows]


@app.post("/api/categories", response_model=CategoryOut)
def create_category(body: CategoryCreate, db: Session = Depends(get_db)) -> CategoryOut:
    existing = db.query(Category).filter(func.lower(Category.name) == body.name.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")
    cat = Category(name=body.name.strip(), color=body.color, icon="tag", enabled=True)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return CategoryOut.from_orm_model(cat)


@app.patch("/api/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, body: CategoryUpdate, db: Session = Depends(get_db)
) -> CategoryOut:
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if body.name is not None:
        cat.name = body.name.strip()
    if body.color is not None:
        cat.color = body.color
    if body.enabled is not None:
        cat.enabled = body.enabled
    if body.expectedMonthly is not None:
        cat.expected_monthly = body.expectedMonthly
    db.commit()
    db.refresh(cat)
    return CategoryOut.from_orm_model(cat)


@app.get("/api/expenses", response_model=list[ExpenseOut])
def list_expenses(
    month: str | None = None,
    db: Session = Depends(get_db),
) -> list[ExpenseOut]:
    query = db.query(Expense)
    if month:
        try:
            year, mon = [int(p) for p in month.split("-")]
            start = date(year, mon, 1)
            _, last, _, _days = month_bounds(start)
        except ValueError:
            raise HTTPException(status_code=400, detail="month must be YYYY-MM")
        query = query.filter(Expense.date >= start, Expense.date <= last)
    rows = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    return [_expense_out(r) for r in rows]


@app.post("/api/expenses", response_model=ExpenseOut)
def create_expense(body: ExpenseCreate, db: Session = Depends(get_db)) -> ExpenseOut:
    cat = db.get(Category, body.categoryId)
    if cat is None:
        raise HTTPException(status_code=400, detail="Unknown category")
    if not cat.enabled:
        raise HTTPException(status_code=400, detail="Category is disabled")
    row = Expense(
        amount=body.amount,
        category_id=body.categoryId,
        date=body.date,
        note=body.note.strip(),
        source=body.source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _expense_out(row)


@app.patch("/api/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int, body: ExpenseUpdate, db: Session = Depends(get_db)
) -> ExpenseOut:
    row = db.get(Expense, expense_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    if body.amount is not None:
        row.amount = body.amount
    if body.categoryId is not None:
        cat = db.get(Category, body.categoryId)
        if cat is None:
            raise HTTPException(status_code=400, detail="Unknown category")
        row.category_id = body.categoryId
    if body.date is not None:
        row.date = body.date
    if body.note is not None:
        row.note = body.note.strip()
    db.commit()
    db.refresh(row)
    return _expense_out(row)


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(Expense, expense_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@app.post("/api/parse", response_model=ParseResponse)
async def parse_expense(body: ParseRequest, db: Session = Depends(get_db)) -> ParseResponse:
    categories = db.query(Category).all()
    drafts, used_llm = await parse_text(body.text.strip(), categories)
    return ParseResponse(drafts=drafts, usedLlm=used_llm)


@app.get("/api/summary", response_model=SummaryOut)
def get_summary(db: Session = Depends(get_db)) -> SummaryOut:
    start, end, days_elapsed, days_in_month = month_bounds()
    categories = db.query(Category).order_by(Category.id).all()
    spent_rows = (
        db.query(Expense.category_id, func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.date >= start, Expense.date <= end)
        .group_by(Expense.category_id)
        .all()
    )
    spent_map = {cid: float(total) for cid, total in spent_rows}

    summaries: list[CategorySummary] = []
    total_spent = 0.0
    total_expected = 0.0
    for cat in categories:
        actual = spent_map.get(cat.id, 0.0)
        total_spent += actual
        expected = cat.expected_monthly if cat.enabled else 0.0
        if cat.enabled and cat.expected_monthly > 0:
            total_expected += cat.expected_monthly
            variance = cat.expected_monthly - actual
        else:
            variance = None
        summaries.append(
            CategorySummary(
                categoryId=cat.id,
                name=cat.name,
                color=cat.color,
                enabled=cat.enabled,
                expected=cat.expected_monthly,
                actual=actual,
                variance=variance,
            )
        )

    projected = (total_spent / days_elapsed) * days_in_month if days_elapsed else 0.0
    return SummaryOut(
        month=start.strftime("%Y-%m"),
        daysElapsed=days_elapsed,
        daysInMonth=days_in_month,
        totalSpent=total_spent,
        totalExpected=total_expected,
        projectedMonthEnd=round(projected, 2),
        categories=summaries,
    )
