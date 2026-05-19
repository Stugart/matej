from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from .. import __version__
from ..settings import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    env: str
    time: datetime
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: server beží a vie odpovedať. Závislosti (DB, Redis) sa
    nemerajú — od toho je /ready."""
    s = get_settings()
    return HealthResponse(
        status="ok",
        env=s.app_env,
        time=datetime.now(UTC),
        version=__version__,
    )
