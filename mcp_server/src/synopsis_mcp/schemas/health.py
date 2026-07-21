from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ServiceName(str, Enum):
    """Инфраструктурные сервисы, доступные для проверки."""

    API = "api"
    OLLAMA = "ollama"
    POSTGRES = "postgres"


class ServiceStatus(str, Enum):
    """Статус доступности сервиса"""

    OK = "ok"
    UNAVAILABLE = "unavailable"


class ServiceCheckResult(BaseModel):
    """Результат проверки инфраструктурного сервиса"""

    service: ServiceName
    status: ServiceStatus

    latency_ms: float = Field(
        ge=0,
        description="Время выполнения проверки в мс."
    )

    details: dict[str, Any] | None = None
    error: str | None = None
