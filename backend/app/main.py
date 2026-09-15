from contextlib import asynccontextmanager
from calendar import monthrange
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.db import Base, engine, get_db, ping_db
from app.models import Budget, Category, Expense, Tag  # noqa: F401
from app.parse import parse_expenses
from app.schemas import (
    BudgetProgress,
    BudgetUpsert,
    CategoryOut,
    CategoryTotal,
    ExpenseCreate,
    ExpenseDraft,
    ExpenseOut,
    ExpenseUpdate,
    ParseIn,
    ParseOut,
    SummaryOut,
    TagOut,
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
        tags=sorted(t.name for t in expense.tags),
    )


def _resolve_tags(db: Session, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in names:
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


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


@app.get("/api/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db)) -> list[Tag]:
    return list(db.scalars(select(Tag).order_by(Tag.name)).all())


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
    expense.tags = _resolve_tags(db, body.tags)
    db.add(expense)
    db.commit()
    expense = db.scalar(
        select(Expense)
        .options(selectinload(Expense.tags))
        .where(Expense.id == expense.id)
    )
    assert expense is not None
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
        .options(selectinload(Expense.tags))
        .order_by(Expense.date.desc(), Expense.id.desc())
    )
    for f in _date_filters(from_date, to_date):
        stmt = stmt.where(f)

    rows = db.execute(stmt).unique().all()
    return [_expense_out(e, name) for e, name in rows]


@app.patch("/api/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int, body: ExpenseUpdate, db: Session = Depends(get_db)
) -> ExpenseOut:
    expense = db.scalar(
        select(Expense)
        .options(selectinload(Expense.tags))
        .where(Expense.id == expense_id)
    )
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
    if "tags" in data and data["tags"] is not None:
        expense.tags = _resolve_tags(db, data["tags"])

    db.commit()
    db.refresh(expense)
    expense = db.scalar(
        select(Expense)
        .options(selectinload(Expense.tags))
        .where(Expense.id == expense_id)
    )
    assert expense is not None
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


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


@app.get("/api/budgets", response_model=list[BudgetProgress])
def list_budgets(
    db: Session = Depends(get_db),
    year: int | None = None,
    month: int | None = None,
) -> list[BudgetProgress]:
    today = date.today()
    y = year if year is not None else today.year
    m = month if month is not None else today.month
    if not (1 <= m <= 12):
        raise HTTPException(status_code=400, detail="month must be 1–12")
    if year is not None and year < 2000:
        raise HTTPException(status_code=400, detail="year out of range")

    start, end = _month_bounds(y, m)
    budgets = list(
        db.execute(
            select(Budget, Category)
            .join(Category, Category.id == Budget.category_id)
            .order_by(Category.id)
        ).all()
    )
    if not budgets:
        return []

    spent_rows = db.execute(
        select(Expense.category_id, func.coalesce(func.sum(Expense.amount), 0.0))
        .where(Expense.date >= start, Expense.date <= end)
        .group_by(Expense.category_id)
    ).all()
    spent_map = {cid: float(total) for cid, total in spent_rows}

    out: list[BudgetProgress] = []
    for budget, category in budgets:
        spent = spent_map.get(budget.category_id, 0.0)
        limit = float(budget.amount)
        remaining = limit - spent
        pct = (spent / limit * 100.0) if limit > 0 else 0.0
        out.append(
            BudgetProgress(
                category_id=category.id,
                category_name=category.name,
                color=category.color,
                limit=limit,
                spent=spent,
                remaining=remaining,
                over=spent > limit,
                pct=round(pct, 1),
            )
        )
    return out


@app.put("/api/budgets", response_model=BudgetProgress)
def upsert_budget(body: BudgetUpsert, db: Session = Depends(get_db)) -> BudgetProgress:
    category = db.get(Category, body.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    budget = db.scalar(
        select(Budget).where(Budget.category_id == body.category_id)
    )
    if budget:
        budget.amount = body.amount
    else:
        budget = Budget(category_id=body.category_id, amount=body.amount)
        db.add(budget)

    db.commit()
    db.refresh(budget)

    today = date.today()
    start, end = _month_bounds(today.year, today.month)
    spent = (
        db.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0.0)).where(
                Expense.category_id == body.category_id,
                Expense.date >= start,
                Expense.date <= end,
            )
        )
        or 0.0
    )
    spent_f = float(spent)
    limit = float(budget.amount)
    remaining = limit - spent_f
    pct = (spent_f / limit * 100.0) if limit > 0 else 0.0
    return BudgetProgress(
        category_id=category.id,
        category_name=category.name,
        color=category.color,
        limit=limit,
        spent=spent_f,
        remaining=remaining,
        over=spent_f > limit,
        pct=round(pct, 1),
    )


@app.delete("/api/budgets/{category_id}")
def delete_budget(category_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    budget = db.scalar(select(Budget).where(Budget.category_id == category_id))
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(budget)
    db.commit()
    return {"ok": True}
