from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db, ping_db
from app.models import Category, Expense  # noqa: F401
from app.parse import parse_expenses
from app.schemas import (
    CategoryOut,
    CategoryTotal,
    ExpenseCreate,
    ExpenseDraft,
    ExpenseOut,
    ExpenseUpdate,
    ParseIn,
    ParseOut,
    SummaryOut,
)
from app.seed import seed_categories


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        seed_categories(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Expense Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _expense_out(expense: Expense, category_name: str | None) -> ExpenseOut:
    return ExpenseOut(
        id=expense.id,
        category_id=expense.category_id,
        amount=expense.amount,
        date=expense.date,
        note=expense.note,
        category_name=category_name,
    )


def _date_filters(from_date: date | None, to_date: date | None):
    filters = []
    if from_date is not None:
        filters.append(Expense.date >= from_date)
    if to_date is not None:
        filters.append(Expense.date <= to_date)
    return filters


@app.get("/api/health")
def health() -> dict:
    try:
        ping_db()
        return {"ok": True, "db": True}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"db unavailable: {exc}") from exc


@app.get("/api/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.id)).all())


@app.post("/api/expenses", response_model=ExpenseOut)
def create_expense(body: ExpenseCreate, db: Session = Depends(get_db)) -> ExpenseOut:
    category = db.get(Category, body.category_id)

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    expense = Expense(
        category_id=body.category_id,
        amount=body.amount,
        date=body.date or date.today(),
        note=body.note.strip(),
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return _expense_out(expense, category.name)


@app.get("/api/expenses", response_model=list[ExpenseOut])
def list_expenses(
    db: Session = Depends(get_db),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
) -> list[ExpenseOut]:
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="'from' must be on or before 'to'")

    stmt = (
        select(Expense, Category.name)
        .join(Category, Category.id == Expense.category_id)
        .order_by(Expense.date.desc(), Expense.id.desc())
    )
    for f in _date_filters(from_date, to_date):
        stmt = stmt.where(f)

    rows = db.execute(stmt).all()
    return [_expense_out(e, name) for e, name in rows]


@app.patch("/api/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int, body: ExpenseUpdate, db: Session = Depends(get_db)
) -> ExpenseOut:
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    data = body.model_dump(exclude_unset=True)
    if "category_id" in data:
        category = db.get(Category, data["category_id"])
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        expense.category_id = data["category_id"]
    if "amount" in data and data["amount"] is not None:
        expense.amount = data["amount"]
    if "date" in data and data["date"] is not None:
        expense.date = data["date"]
    if "note" in data and data["note"] is not None:
        expense.note = data["note"].strip()

    db.commit()
    db.refresh(expense)
    category = db.get(Category, expense.category_id)
    return _expense_out(expense, category.name if category else None)


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"ok": True}


@app.get("/api/summary", response_model=SummaryOut)
def summary(
    db: Session = Depends(get_db),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
) -> SummaryOut:
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="'from' must be on or before 'to'")

    filters = _date_filters(from_date, to_date)

    total_stmt = select(func.coalesce(func.sum(Expense.amount), 0.0))
    for f in filters:
        total_stmt = total_stmt.where(f)
    total = db.scalar(total_stmt) or 0.0

    join_on = Expense.category_id == Category.id
    if filters:
        join_on = and_(join_on, *filters)

    rows = db.execute(
        select(
            Category.id,
            Category.name,
            Category.color,
            func.coalesce(func.sum(Expense.amount), 0.0),
        )
        .outerjoin(Expense, join_on)
        .group_by(Category.id, Category.name, Category.color)
        .order_by(Category.id)
    ).all()
    return SummaryOut(
        total_spend=float(total),
        by_category=[
            CategoryTotal(
                category_id=r[0], name=r[1], color=r[2], total=float(r[3])
            )
            for r in rows
        ],
    )


@app.post("/api/parse", response_model=ParseOut)
def parse_expense_text(body: ParseIn, db: Session = Depends(get_db)) -> ParseOut:
    categories = list(db.scalars(select(Category).order_by(Category.id)).all())
    cat_dicts = [{"id": c.id, "name": c.name} for c in categories]
    raw = parse_expenses(body.text, cat_dicts)
    return ParseOut(drafts=[ExpenseDraft(**d) for d in raw])
