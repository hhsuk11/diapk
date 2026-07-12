from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    return HealthRead(
        status="ok",
        app_name=settings.app_name,
        app_env=settings.app_env,
        auth_mode=settings.auth_mode,
        database=settings.database_url.split(":", 1)[0],
    )
