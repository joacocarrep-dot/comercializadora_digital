from fastapi import APIRouter
from app.config.settings import settings

router = APIRouter(tags=["health"])

@router.get("/health", summary="Health check endpoint")
async def health_check() -> dict:
    """
    Returns the current health status of the API.
    """
    return {
        "status": "ok",
        "environment": settings.env,
        "database": "connected",
    }
