from app.config import get_settings
from app.schemas import HealthResponse


def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
    )
