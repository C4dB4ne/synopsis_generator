import logging
import sys
import inspect

from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from functools import wraps
from time import perf_counter
from typing import Any, Callable

from app.config import settings


def log_graph_node(
    node_name: str,
    node: Callable,
) -> Callable:
    """
    Оборачивает LangGraph node и логирует
    начало, завершение и ошибки.
    """

    if inspect.iscoroutinefunction(
        node
    ):

        @wraps(node)
        async def async_wrapper(
            state: dict,
            *args: Any,
            **kwargs: Any,
        ):
            started_at = perf_counter()

            logger.info(
                "GRAPH NODE START | %s | status=%s",
                node_name,
                state.get("status"),
            )

            try:
                result = await node(
                    state,
                    *args,
                    **kwargs,
                )

            except Exception:
                logger.exception(
                    "GRAPH NODE ERROR | %s",
                    node_name,
                )
                raise

            logger.info(
                (
                    "GRAPH NODE END | %s | "
                    "duration_ms=%.2f | "
                    "new_status=%s"
                ),
                node_name,
                (
                    perf_counter()
                    - started_at
                )
                * 1000,
                (
                    result.get("status")
                    if isinstance(result, dict)
                    else None
                ),
            )

            return result

        return async_wrapper

    @wraps(node)
    def sync_wrapper(
        state: dict,
        *args: Any,
        **kwargs: Any,
    ):
        started_at = perf_counter()

        logger.info(
            "GRAPH NODE START | %s | status=%s",
            node_name,
            state.get("status"),
        )

        try:
            result = node(
                state,
                *args,
                **kwargs,
            )

        except Exception:
            logger.exception(
                "GRAPH NODE ERROR | %s",
                node_name,
            )
            raise

        logger.info(
            (
                "GRAPH NODE END | %s | "
                "duration_ms=%.2f | "
                "new_status=%s"
            ),
            node_name,
            (
                perf_counter()
                - started_at
            )
            * 1000,
            (
                result.get("status")
                if isinstance(result, dict)
                else None
            ),
        )

        return result

    return sync_wrapper


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("synopsis-generator")

    logger.setLevel(
        getattr(
            logging,
            settings.log_level.upper(),
            logging.INFO,
        )
    )

    logger.propagate = False

    # Важно при uvicorn --reload:
    # не добавляем handlers повторно.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        (
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(
        sys.stdout
    )

    console_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        console_handler
    )

    try:
        logs_dir = Path(
            settings.logs_directory
        )

        logs_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_handler = TimedRotatingFileHandler(
            filename=logs_dir / "app.log",
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )

        file_handler.setFormatter(
            formatter
        )

        file_handler.suffix = "%Y-%m-%d"

        logger.addHandler(
            file_handler
        )

        logger.info(
            "File logging enabled: %s",
            logs_dir / "app.log",
        )

    except OSError as exc:
        logger.warning(
            "File logging unavailable. "
            "Console logging only. Error: %s",
            exc,
        )

    return logger


logger = _build_logger()
