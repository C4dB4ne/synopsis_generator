from typing import Literal

from app.graph.state import SynopsisState


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
    if state.get("requirements_complete", False):
        return "genre_router"

    return "request_clarification"


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

    if revision_count >= max_revisions:
        return "language_editor"

    return route_to_writer(state)
