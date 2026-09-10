from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db, ping_db
from app.models import Category, Expense  # noqa: F401
from app.schemas import (
    CategoryOut,
    CategoryTotal,
    ExpenseCreate,
    ExpenseOut,
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
def create_expense(body: ExpenseCreate, db: Session = Depends(get_db)) -> Expense:
    category = db.get(Category,body.category_id)

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    expense= Expense(
        category_id=body.category_id,
        amount=body.amount,
        date=body.date or date.today(),
        note=body.note.strip(),
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return ExpenseOut(
        id=expense.id,
        category_id=expense.category_id,
        amount=expense.amount,
        date=expense.date,
        note=expense.note,
        category_name=category.name,
    )
    
@app.get("/api/expenses", response_model=list[ExpenseOut])
def list_expenses(db: Session = Depends(get_db)) -> list[ExpenseOut]:
    rows = db.execute(
        select(Expense, Category.name)
        .join(Category, Category.id == Expense.category_id)
        .order_by(Expense.date.desc(), Expense.id.desc())
    ).all()
    return [
        ExpenseOut(
            id=e.id,
            category_id=e.category_id,
            amount=e.amount,
            date=e.date,
            note=e.note,
            category_name=name,
        )
        for e, name in rows
    ]


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"ok": True}


@app.get("/api/summary", response_model=SummaryOut)
def summary(db: Session = Depends(get_db)) -> SummaryOut:
    total = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0.0))) or 0.0
    rows = db.execute(
        select(Category.id, Category.name, func.coalesce(func.sum(Expense.amount), 0.0))
        .outerjoin(Expense, Expense.category_id == Category.id)
        .group_by(Category.id, Category.name)
        .order_by(Category.id)
    ).all()
    return SummaryOut(
        total_spend=float(total),
        by_category=[
            CategoryTotal(category_id=r[0], name=r[1], total=float(r[2])) for r in rows
        ],
    )