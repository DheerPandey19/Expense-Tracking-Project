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
    ("Other", "#6C757D"),
]

def seed_categories(db: Session) -> None:
    # Ask the database: "does at least one category already exist?"
    # select(Category.id).limit(1) builds a query that grabs just one id,
    # and db.scalar() runs it and returns that single value (or None if empty).
    if db.scalar(select(Category.id).limit(1)):
        # If we got a truthy result back, categories already exist,
        # so stop here and don't add duplicates.
        return

    # If we reach this point, the table was empty — safe to seed it.
    # Loop through each (name, color) pair in our default list.
    for name, color in DEFAULT_CATEGORIES:
        # Create a new Category object and stage it to be saved.
        # This does NOT write to the database yet — it just queues it up.
        db.add(Category(name=name, color=color))

    # Now actually save everything we staged above to the database
    # in one go (a single transaction).
    db.commit()