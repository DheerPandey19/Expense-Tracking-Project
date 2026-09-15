from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Category

DEFAULT_CATEGORIES = [
    ("Food", "#E07A5F"),
    ("Transport", "#3D405B"),
    ("Housing", "#81B29A"),
    ("Utilities", "#F2CC8F"),
    ("Entertainment", "#E9C46A"),
    ("Shopping", "#264653"),
    ("Health", "#2A9D8F"),
    ("Parents", "#9B5DE5"),
    ("Misc", "#778DA9"),
    ("Other", "#6C757D"),
]


def seed_categories(db: Session) -> None:
    """Insert any missing default categories (safe to run on every startup)."""
    existing = {name for (name,) in db.execute(select(Category.name)).all()}
    added = False
    for name, color in DEFAULT_CATEGORIES:
        if name in existing:
            continue
        db.add(Category(name=name, color=color))
        added = True
    if added:
        db.commit()


def backfill_expense_categories(db: Session) -> None:
    """Copy legacy expenses.category_id into expense_categories when missing."""
    db.execute(
        text(
            """
            INSERT INTO expense_categories (expense_id, category_id)
            SELECT e.id, e.category_id
            FROM expenses e
            WHERE NOT EXISTS (
                SELECT 1 FROM expense_categories ec
                WHERE ec.expense_id = e.id
            )
            """
        )
    )
    db.commit()
