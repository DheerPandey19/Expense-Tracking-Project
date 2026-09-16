from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Expense, Tag
from app.schemas import ExpenseCreate


def _resolve_categories(
    db: Session,
    category_ids: list[int],
) -> list[Category]:
    categories: list[Category] = []

    for category_id in category_ids:
        category = db.get(Category, category_id)
        if category is None:
            raise ValueError(f"Category not found: {category_id}")
        categories.append(category)

    return categories


def _resolve_tags(
    db: Session,
    names: list[str],
) -> list[Tag]:
    tags: list[Tag] = []

    for name in names:
        tag = db.scalar(select(Tag).where(Tag.name == name))

        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()

        tags.append(tag)

    return tags


def create_expense_record(
    db: Session,
    body: ExpenseCreate,
) -> Expense:
    assert body.category_ids is not None

    expense = Expense(
        category_id=body.category_ids[0],
        amount=body.amount,
        date=body.date or date.today(),
        note=body.note.strip(),
    )

    expense.categories = _resolve_categories(
        db,
        body.category_ids,
    )
    expense.tags = _resolve_tags(db, body.tags)

    db.add(expense)
    db.flush()

    return expense