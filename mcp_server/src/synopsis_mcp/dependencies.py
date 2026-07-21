from synopsis_mcp.services.health import HealthService
from synopsis_mcp.services.synopsis import SynopsisService


def get_health_service() -> HealthService:
    """Создаёт сервис проверки инфраструктуры."""
    return HealthService()


def get_synopsis_service() -> SynopsisService:
    """Создаёт сервис работы с синопсисами."""
    return SynopsisService()
