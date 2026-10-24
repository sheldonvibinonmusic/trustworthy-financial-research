"""Health check endpoint."""

from typing import Dict
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="System health check")
def health_check() -> Dict[str, str]:
    """Returns standard service health status."""
    return {"status": "ok"}
