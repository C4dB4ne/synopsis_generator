import os

from time import perf_counter
from typing import Any, Literal, TypedDict
from collections.abc import Callable

import httpx
import psycopg

from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    name="Synopsis MCP Server",
    host="0.0.0.0",
    port=8001,
    stateless_http=True,
    json_response=True,
)


ServiceName = Literal[
    "api",
    "ollama",
    "postgres",
]


ServiceStatus = Literal[
    "ok",
    "unavailable",
]


class SaveSynopsisResult(TypedDict):
    """Результат сохранения синопсиса."""

    saved: bool
    synopsis_id: int | None
    created_at: str | None
    error: str | None


class ServiceCheckResult(TypedDict):
    """Cловарь для структурирования результата сервиса"""

    service: ServiceName
    status: ServiceStatus
    latency_ms: float
    details: dict[str, Any] | None
    error: str | None


# Функция-проверка возвращает только полезные детали сервиса.
ServiceChecker = Callable[[], dict[str, Any]]


# ----------------------------------------------------------
#                      CHECK_SERVICE
# ----------------------------------------------------------


@mcp.tool()
def check_service(target: ServiceName) -> ServiceCheckResult:
    """
    Проверяет доступность инфраструктурного сервиса.

    Сервисы можно добавлять, для этого достаточно добавить:
    1. имя в Literal схему ServiceName: func
    2. функцию проверки типа: def _check_func() -> dict[str, Any]
    3. запись в реестр SERVICE_CHECKERS: "func": _check_func

    При этом сам check_service() менять не нужно.

    tool не выбрасывает исключение наружу при недоступности сервиса,
    а просто возращает status="unavailable"
    """
    started_at = perf_counter()

    try:
        checker = SERVICE_CHECKERS[target]
        details = checker()

        return _build_success_result(
            service=target,
            started_at=started_at,
            details=details,
        )

    except Exception as exc:
        return _build_error_result(
            service=target,
            started_at=started_at,
            error=exc,
        )


def _check_api() -> dict[str, Any]:
    """Проверка основной Synopsis api через /health"""
    base_url = os.environ.get("API_BASE_URL", "http://api:8000")

    response = httpx.get(f"{base_url}/health", timeout=3.0)

    response.raise_for_status()

    return response.json()


def _check_ollama() -> dict[str, Any]:
    """Проверка Ollama через /api/version"""
    base_url = os.environ.get(
        "OLLAMA_BASE_URL",
        "http://ollama:11434"
    )

    response = httpx.get(f"{base_url}/api/version", timeout=3.0)

    response.raise_for_status()

    data = response.json()

    return {"version": data.get("version")}


def _check_postgres() -> dict[str, Any]:
    """Проверка соединения с PostgreSQL"""
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

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

    return {
        "database": database,
        "user": user,
    }


# РЕЕСТР ПРОВЕРОК
SERVICE_CHECKERS: dict[
    ServiceName,
    ServiceChecker,
] = {
    "api": _check_api,
    "ollama": _check_ollama,
    "postgres": _check_postgres,
}


def _build_success_result(
    service: ServiceName,
    started_at: float,
    details: dict[str, Any],
) -> ServiceCheckResult:
    return {
        "service": service,
        "status": "ok",
        "latency_ms": _latency_ms(started_at),
        "details": details,
        "error": None,
    }


def _build_error_result(
    service: ServiceName,
    started_at: float,
    error: Exception,
) -> ServiceCheckResult:
    return {
        "service": service,
        "status": "unavailable",
        "latency_ms": _latency_ms(started_at),
        "details": None,
        "error": str(error),
    }


def _latency_ms(started_at: float) -> float:
    """Время выполнения проверки в ms"""
    return round((perf_counter() - started_at) * 1000, 2)


# ----------------------------------------------------------
#                      SAVE_SYNOPSIS
# ----------------------------------------------------------


@mcp.tool()
def save_synopsis(
    idea: str,
    genre: str,
    style: str,
    language: str,
    requested_length: str,
    selected_writer: str | None,
    draft: str | None,
    final_text: str | None,
    critique_passed: bool | None,
    critique_score: int | None,
    revision_count: int,
) -> SaveSynopsisResult:
    """
    Сохраняет результат генерации синопсиса в PostgreSQL.

    При недоступности PostgreSQL возращает saved=False,
    а MCP Server продолжает работать.
    """
    try:
        database_url = os.environ.get("DATABASE_URL")

        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured")

        with psycopg.connect(
            database_url,
            connect_timeout=3,
        ) as connection:

            with connection.cursor() as cursor:
                _ensure_synopsis_table(cursor)

                cursor.execute(
                    """
                    INSERT INTO synopsis_generations (
                        idea,
                        genre,
                        style,
                        language,
                        requested_length,
                        selected_writer,
                        draft,
                        final_text,
                        critique_passed,
                        critique_score,
                        revision_count
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING
                        id,
                        created_at
                    """,
                    (
                        idea,
                        genre,
                        style,
                        language,
                        requested_length,
                        selected_writer,
                        draft,
                        final_text,
                        critique_passed,
                        critique_score,
                        revision_count,
                    ),
                )
                synopsis_id, created_at = cursor.fetchone()

            connection.commit()

        return {
            "saved": True,
            "synopsis_id": synopsis_id,
            "created_at": created_at.isoformat(),
            "error": None,
        }

    except Exception as exc:
        return {
            "saved": False,
            "synopsis_id": None,
            "created_at": None,
            "error": str(exc),
        }


def _ensure_synopsis_table(
    cursor: psycopg.Cursor,
) -> None:
    """
    Создаёт таблицу для истории генераций,
    если она ещё не существует.
    """

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS synopsis_generations (
            id BIGSERIAL PRIMARY KEY,

            idea TEXT NOT NULL,
            genre TEXT NOT NULL,
            style TEXT NOT NULL,
            language TEXT NOT NULL,
            requested_length TEXT NOT NULL,

            selected_writer TEXT,

            draft TEXT,
            final_text TEXT,

            critique_passed BOOLEAN,
            critique_score INTEGER,
            revision_count INTEGER NOT NULL DEFAULT 0,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
