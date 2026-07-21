from typing import Annotated

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from synopsis_mcp.dependencies import get_health_service
from synopsis_mcp.services.health import HealthService
from synopsis_mcp.schemas.health import (
    ServiceCheckResult,
    ServiceName
)


def register_health_tools(
    mcp: FastMCP,
) -> None:
    """Регистрирует инструменты диагностики."""

    @mcp.tool()
    def check_service(
        target: Annotated[
            ServiceName,
            Field(
                description=(
                    "Инфраструктурный сервис, "
                    "доступность которого нужно проверить."
                )
            ),
        ],
        service: HealthService = Depends(
            get_health_service,
        ),
    ) -> ServiceCheckResult:
        """
        Проверяет доступность инфраструктурного сервиса.

        Используй этот инструмент, когда необходимо проверить,
        доступен ли API, Ollama или PostgreSQL.

        Инструмент возвращает статус сервиса, время проверки,
        диагностические данные и описание ошибки при её наличии.
        """

        return service.check_service(target)
