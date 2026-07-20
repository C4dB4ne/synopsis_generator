import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings
from app.graph.builder import synopsis_graph
from app.api.schemas import SynopsisRequest, SynopsisResponse
from app.mcp.client import get_mcp_tools_safely

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Проверяет запущено ли API."""

    return {
        "status": "ok",
        "app": settings.app_name,
    }


@app.get("/health/dependencies")
def dependencies_health() -> dict:
    """Проверяет подключение API к инфраструктуре PostgreSQL и Ollama."""

    result: dict = {}

    # Проверка Ollama
    try:
        response = httpx.get(
            f"{settings.ollama_base_url}/api/version",
            timeout=5.0,
        )
        response.raise_for_status()

        result["ollama"] = {
            "status": "ok",
            "version": response.json().get("version"),
            "model": settings.llm_model,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama unavailable: {exc}"
        ) from exc

    # Проверка PostgreSQL
    try:
        with psycopg.connect(settings.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), current_user"
                )
                database, user = cursor.fetchone()

        result["postgres"] = {
            "status": "ok",
            "database": database,
            "user": user,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"PostgreSQL unavailable: {exc}",
        ) from exc

    return result


@app.post(
    "/api/v1/synopsis",
    response_model=SynopsisResponse,
)
async def generate_synopsis(request: SynopsisRequest):
    """Запускает LangGraph для генерации синопсиса"""
    initial_state = {
        "idea": request.idea or "",
        "genre": request.genre or "",
        "style": request.style or "",
        "language": request.language or "",
        "length": request.length or "",
        "revision_count": 0,
        "max_revisions": request.max_revisions,
        "status": "started",
    }

    mcp_tools = await get_mcp_tools_safely()

    result = await synopsis_graph.ainvoke(
        initial_state,
        config={
            "recursion_limit": 20,
        },
    )

    return SynopsisResponse(
        status=result.get(
            "status",
            "unknown",
        ),
        selected_writer=result.get(
            "selected_writer",
        ),
        draft=result.get(
            "draft",
        ),
        final_text=result.get(
            "final_text",
        ),
        critique_passed=result.get(
            "critique_passed",
        ),
        critique_score=result.get(
            "critique_score",
        ),
        critique_issues=result.get(
            "critique_issues",
            [],
        ),
        revision_count=result.get(
            "revision_count",
            0,
        ),
        clarification_message=result.get(
            "clarification_message",
        ),
    )
