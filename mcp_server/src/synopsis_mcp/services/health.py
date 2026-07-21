import os

from time import perf_counter
from typing import Any

import httpx
import psycopg

from synopsis_mcp.schemas.health import (
    ServiceName,
    ServiceStatus,
    ServiceCheckResult
)


class HealthService:
    """
    Сервис проверки инфраструктурных зависимостей
    """

    def check_service(
        self,
        target: ServiceName
    ) -> ServiceCheckResult:
        started_at = perf_counter()

        try:
            checker = self._get_checker(target)
            details = checker()

            return ServiceCheckResult(
                service=target,
                status=ServiceStatus.OK,
                latency_ms=self._latency_ms(started_at),
                details=details,
                error=None,
            )

        except Exception as exc:
            return ServiceCheckResult(
                service=target,
                status=ServiceStatus.UNAVAILABLE,
                latency_ms=self._latency_ms(started_at),
                details=None,
                error=str(exc),
            )

    def _get_checker(self, target: ServiceName):
        checkers = {
            ServiceName.API: self._check_api,
            ServiceName.OLLAMA: self._check_ollama,
            ServiceName.POSTGRES: self._check_postgres,
        }

        return checkers[target]

    def _check_api(self) -> dict[str, Any]:
        base_url = os.environ.get(
            "API_BASE_URL",
            "http://api:8000",
        )

        response = httpx.get(
            f"{base_url}/health",
            timeout=3.0,
        )

        response.raise_for_status()

        return response.json()

    def _check_ollama(self) -> dict[str, Any]:
        base_url = os.environ.get(
            "OLLAMA_BASE_URL",
            "http://ollama:11434",
        )

        response = httpx.get(
            f"{base_url}/api/version",
            timeout=3.0,
        )

        response.raise_for_status()

        data = response.json()

        return {
            "version": data.get(
                "version",
            ),
        }

    def _check_postgres(self) -> dict[str, Any]:
        database_url = os.environ.get(
            "DATABASE_URL",
        )

        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured."
            )

        with psycopg.connect(
            database_url,
            connect_timeout=3,
        ) as connection:

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        current_database(),
                        current_user
                    """
                )

                database, user = cursor.fetchone()

        return {"database": database, "user": user}

    @staticmethod
    def _latency_ms(started_at: float) -> float:
        return round((perf_counter() - started_at) * 1000, 2)
