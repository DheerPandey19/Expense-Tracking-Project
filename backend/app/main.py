from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db, ping_db
from app.models import Category  # noqa: F401 — register models on Base.metadata
from app.models import Expense, Profile  # noqa: F401
from app.schemas import CategoryOut
from app.seed import seed_categories

app = FastAPI(title="Expense Tracker", lifespan=lifespan)

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        seed_categories(db)
    finally:
        db.close()
    yield
    
@app.get("/api/health")
def health() -> dict:
    try:
        ping_db()
        return {"ok": True, "db": True}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"db unavailable: {exc}") from exc


@app.get("/api/categories",
def list_categories(db: Session = Depends(get_db))->list[Category]:
    return list(db.scalars(select(Category).order_by(Category.id)).all()))