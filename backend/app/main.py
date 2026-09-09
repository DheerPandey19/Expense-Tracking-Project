from fastapi import FastAPI, HTTPException

from app.db import ping_db

app = FastAPI(title="Expense Tracker")


@app.get("/api/health")
def health() -> dict:
    try:
        ping_db()
        return {"ok": True, "db": True}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"db unavailable: {exc}") from exc