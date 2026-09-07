from sqlalchemy.orm import Session

from app.models import AppSetting, Category

SEED_CATEGORIES = [
    {"name": "Food", "color": "#f97316", "icon": "utensils"},
    {"name": "Transport", "color": "#3b82f6", "icon": "car"},
    {"name": "Housing", "color": "#8b5cf6", "icon": "home"},
    {"name": "Utilities", "color": "#06b6d4", "icon": "zap"},
    {"name": "Entertainment", "color": "#ec4899", "icon": "film"},
    {"name": "Shopping", "color": "#14b8a6", "icon": "bag"},
    {"name": "Health", "color": "#22c55e", "icon": "heart"},
    {"name": "Other", "color": "#64748b", "icon": "tag"},
]


def seed_if_empty(db: Session) -> None:
    if db.query(Category).count() == 0:
        for item in SEED_CATEGORIES:
            db.add(Category(**item, enabled=True, expected_monthly=0))
    if db.get(AppSetting, "currency") is None:
        db.add(AppSetting(key="currency", value="INR"))
    db.commit()
