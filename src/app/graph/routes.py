from typing import Literal

from app.graph.state import SynopsisState
from app.core.logger import logger


RequirementsRoute = Literal[
    "request_clarification",
    "genre_router",
]


WriterNode = Literal[
    "fantasy_writer",
    "drama_writer",
    "thriller_writer",
    "comedy_writer",
    "universal_writer",
]


CriticRoute = Literal[
    "fantasy_writer",
    "drama_writer",
    "thriller_writer",
    "comedy_writer",
    "universal_writer",
    "language_editor",
]


def route_after_requirements(state: SynopsisState) -> RequirementsRoute:
    """
    После проверки ТЗ - либо просим уточнения,
    либо продолжаем генерацию.
    """
    if state.get(
        "requirements_complete",
        False,
    ):
        route = "genre_router"

    else:
        route = "request_clarification"

    logger.info(
        "GRAPH ROUTE | collect_requirements -> %s",
        route,
    )

    return route


def route_to_writer(state: SynopsisState) -> WriterNode:
    """
    Выбираем узел-писатель, определенную genre_router()
    """
    selected_writer = state.get(
        "selected_writer",
        "universal_writer",
    )

    allowed_writers = {
        "fantasy_writer",
        "drama_writer",
        "thriller_writer",
        "comedy_writer",
        "universal_writer",
    }

    if selected_writer not in allowed_writers:
        return "universal_writer"

    logger.info(
        "GRAPH ROUTE | genre_router -> %s",
        selected_writer,
    )

    return selected_writer


def route_after_critic(state: SynopsisState) -> CriticRoute:
    """
    Определяет, нужно ли повторно отправить текст писателю.

    Цикл останавливается, если:
    - Критик одобрил текст
    или
    - достигнут max_revisions
    """
    if state.get("critique_passed", False):
        return "language_editor"

    revision_count = state.get(
        "revision_count",
        0,
    )

    max_revisions = state.get(
        "max_revisions",
        3,
    )

    route = "request_clarification"

    if revision_count >= max_revisions:
        return "language_editor"

    logger.info(
        (
            "GRAPH ROUTE | critic | "
            "passed=%s | revision=%d/%d | next=%s"
        ),
        state.get(
            "critique_passed",
            False,
        ),
        revision_count,
        max_revisions,
        route,
    )

    return route_to_writer(state)
