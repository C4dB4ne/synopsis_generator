import httpx
import psycopg
from uuid import uuid4
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from fastapi import FastAPI, HTTPException, Request

from app.config import settings
from app.graph.builder import build_graph
from app.api.schemas import (
    SynopsisRequest,
    SynopsisResumeRequest,
    SynopsisResponse
)
from app.mcp.client import get_mcp_tools_safely, find_mcp_tool
from app.core.logger import logger


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    logger.info(
        "Starting application: %s",
        settings.app_name,
    )

    try:
        async with (
            AsyncPostgresSaver
            .from_conn_string(
                settings.database_url
            )
        ) as checkpointer:

            logger.info(
                "Initializing LangGraph "
                "PostgreSQL checkpointer."
            )

            await checkpointer.setup()

            app.state.synopsis_graph = (
                build_graph(
                    checkpointer=checkpointer,
                )
            )

            logger.info(
                "LangGraph checkpointer ready."
            )

            yield

    except Exception:
        logger.exception(
            "Unhandled application "
            "lifespan error."
        )
        raise

    finally:
        logger.info(
            "Stopping application: %s",
            settings.app_name,
        )


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
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
async def generate_synopsis(
    payload: SynopsisRequest,
    request: Request,
):
    """
    Запускает новый LangGraph workflow.
    """

    thread_id = str(
        uuid4()
    )

    logger.info(
        "GRAPH START | thread_id=%s",
        thread_id,
    )

    initial_state = {
        "thread_id": thread_id,

        "latest_user_message": (
            payload.message
        ),

        "idea": (
            payload.idea or ""
        ),
        "genre": (
            payload.genre or ""
        ),
        "style": (
            payload.style or ""
        ),
        "language": (
            payload.language or ""
        ),
        "length": (
            payload.length or ""
        ),

        "clarification_count": 0,
        "max_clarifications": (
            payload.max_clarifications
        ),

        "revision_count": 0,
        "max_revisions": (
            payload.max_revisions
        ),

        "status": "started",
    }

    graph = (
        request.app.state.synopsis_graph
    )

    result = await graph.ainvoke(
        initial_state,
        config=_graph_config(
            thread_id,
        ),
    )

    interrupt_payload = (
        _get_interrupt_payload(
            result,
        )
    )

    if interrupt_payload:
        logger.info(
            (
                "GRAPH PAUSED | "
                "thread_id=%s | "
                "reason=clarification"
            ),
            thread_id,
        )

    else:
        await _persist_synopsis(
            result,
        )

        logger.info(
            (
                "GRAPH FINISHED | "
                "thread_id=%s | "
                "status=%s"
            ),
            thread_id,
            result.get(
                "status",
            ),
        )

    return _build_response(
        result,
        thread_id,
    )


@app.post(
    "/api/v1/synopsis/resume",
    response_model=SynopsisResponse,
)
async def resume_synopsis(
    payload: SynopsisResumeRequest,
    request: Request,
):
    """
    Продолжает ранее приостановленный
    LangGraph workflow.
    """

    thread_id = payload.thread_id

    logger.info(
        (
            "GRAPH RESUME | "
            "thread_id=%s"
        ),
        thread_id,
    )

    graph = (
        request.app.state.synopsis_graph
    )

    result = await graph.ainvoke(
        Command(
            resume=payload.message,
        ),
        config=_graph_config(
            thread_id,
        ),
    )

    interrupt_payload = (
        _get_interrupt_payload(
            result,
        )
    )

    if interrupt_payload:
        logger.info(
            (
                "GRAPH PAUSED AGAIN | "
                "thread_id=%s"
            ),
            thread_id,
        )

    else:
        await _persist_synopsis(
            result,
        )

        logger.info(
            (
                "GRAPH FINISHED | "
                "thread_id=%s | "
                "status=%s"
            ),
            thread_id,
            result.get(
                "status",
            ),
        )

    return _build_response(
        result,
        thread_id,
    )


def _graph_config(
    thread_id: str,
) -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 30,
    }


def _get_interrupt_payload(
    result: dict,
) -> dict | None:
    interrupts = result.get(
        "__interrupt__",
    )

    if not interrupts:
        return None

    first_interrupt = interrupts[0]

    value = getattr(
        first_interrupt,
        "value",
        first_interrupt,
    )

    if isinstance(
        value,
        dict,
    ):
        return value

    return {
        "message": str(value),
    }


def _build_response(
    result: dict,
    thread_id: str,
) -> SynopsisResponse:
    interrupt_payload = (
        _get_interrupt_payload(
            result,
        )
    )

    interrupted = (
        interrupt_payload is not None
    )

    clarification_message = (
        result.get(
            "clarification_message",
        )
    )

    if interrupt_payload:
        clarification_message = (
            interrupt_payload.get(
                "message",
                clarification_message,
            )
        )

    return SynopsisResponse(
        thread_id=thread_id,
        interrupted=interrupted,

        status=(
            "needs_clarification"
            if interrupted
            else result.get(
                "status",
                "unknown",
            )
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
        clarification_count=result.get(
            "clarification_count",
            0,
        ),
        clarification_message=(
            clarification_message
        ),
    )


async def _persist_synopsis(
    result: dict,
) -> None:
    final_text = result.get(
        "final_text",
    )

    if not final_text:
        return

    mcp_tools = (
        await get_mcp_tools_safely()
    )

    save_tool = find_mcp_tool(
        mcp_tools,
        "save_synopsis",
    )

    if save_tool is None:
        if mcp_tools:
            logger.warning(
                "MCP Server is available, "
                "but save_synopsis was not found."
            )

        return

    try:
        save_result = (
            await save_tool.ainvoke(
                {
                    "idea": result.get(
                        "idea",
                        "",
                    ),
                    "genre": result.get(
                        "genre",
                        "",
                    ),
                    "style": result.get(
                        "style",
                        "",
                    ),
                    "language": result.get(
                        "language",
                        "",
                    ),
                    "requested_length": (
                        result.get(
                            "length",
                            "",
                        )
                    ),
                    "selected_writer": (
                        result.get(
                            "selected_writer",
                        )
                    ),
                    "draft": result.get(
                        "draft",
                    ),
                    "final_text": final_text,
                    "critique_passed": (
                        result.get(
                            "critique_passed",
                        )
                    ),
                    "critique_score": (
                        result.get(
                            "critique_score",
                        )
                    ),
                    "revision_count": (
                        result.get(
                            "revision_count",
                            0,
                        )
                    ),
                }
            )
        )

        logger.info(
            "save_synopsis MCP result: %s",
            save_result,
        )

    except Exception as exc:
        logger.warning(
            (
                "Failed to persist synopsis "
                "through MCP. Error: %s"
            ),
            exc,
        )
