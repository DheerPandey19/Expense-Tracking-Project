from sqlalchemy import select
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
