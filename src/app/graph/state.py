from typing import TypedDict


class SynopsisState(TypedDict, total=False):
    """Состояние LangGraph."""

    # Исходное ТЗ
    idea: str
    genre: str
    style: str
    language: str
    length: str

    # Проверка полноты ТЗ
    requirements_complete: bool
    missing_fields: list[str]
    ambiguous_fields: list[str]
    clarification_points: list[str]
    clarification_message: str

    # Маршрутизация
    selected_writer: str

    # Текущая рабочая версия синопсиса
    draft: str

    # Последний результат - критика
    critique_passed: bool
    critique_score: int
    critique_issues: list[str]
    revision_instructions: str

    # Контроль цикла писатель - критик - писатель
    revision_count: int
    max_revisions: int

    final_text: str
    status: str
