from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    """Real check (pings the DB), unlike the frontend's current hardcoded
    "Engine online" pill — see docs/api-contract.md §2 in the pill-check repo.
    """
    try:
        db.execute(text("SELECT 1"))
        return HealthResponse(status="ok")
    except Exception:
        return HealthResponse(status="down")
