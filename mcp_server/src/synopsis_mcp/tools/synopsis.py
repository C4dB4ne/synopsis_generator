from typing import Annotated

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from synopsis_mcp.dependencies import get_synopsis_service
from synopsis_mcp.schemas.synopsis import SaveSynopsisResult
from synopsis_mcp.services.synopsis import SynopsisService


def register_synopsis_tools(
    mcp: FastMCP,
) -> None:
    """Регистрирует инструменты работы с синопсисами."""

    @mcp.tool()
    def save_synopsis(
        idea: Annotated[
            str,
            Field(
                min_length=1,
                description="Исходная идея произведения.",
            ),
        ],
        genre: Annotated[
            str,
            Field(
                min_length=1,
                description="Жанр произведения.",
            ),
        ],
        style: Annotated[
            str,
            Field(
                description="Требуемая стилистика.",
            ),
        ],
        language: Annotated[
            str,
            Field(
                description="Язык синопсиса.",
            ),
        ],
        requested_length: Annotated[
            str,
            Field(
                description=(
                    "Требование пользователя "
                    "к объёму синопсиса."
                ),
            ),
        ],
        final_text: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Готовый финальный текст "
                    "синопсиса."
                ),
            ),
        ],
        selected_writer: Annotated[
            str | None,
            Field(
                description=(
                    "Writer-узел, создавший "
                    "синопсис."
                ),
            ),
        ] = None,
        draft: Annotated[
            str | None,
            Field(
                description=(
                    "Последняя версия черновика."
                ),
            ),
        ] = None,
        critique_passed: Annotated[
            bool | None,
            Field(
                description=(
                    "Прошёл ли синопсис "
                    "проверку Critic."
                ),
            ),
        ] = None,
        critique_score: Annotated[
            int | None,
            Field(
                ge=0,
                le=10,
                description="Оценка Critic.",
            ),
        ] = None,
        revision_count: Annotated[
            int,
            Field(
                ge=0,
                description=(
                    "Количество выполненных "
                    "итераций доработки."
                ),
            ),
        ] = 0,
        story_id: Annotated[
            int | None,
            Field(
                ge=1,
                description=(
                    "ID истории, к которой "
                    "относится генерация."
                ),
            ),
        ] = None,
        thread_id: Annotated[
            str | None,
            Field(
                description=(
                    "LangGraph thread_id генерации."
                ),
            ),
        ] = None,
        user_request: Annotated[
            str | None,
            Field(
                description=(
                    "Исходное сообщение пользователя."
                ),
            ),
        ] = None,
        entry_summary: Annotated[
            str | None,
            Field(
                description=(
                    "Краткое содержание данной генерации."
                ),
            ),
        ] = None,
        service: SynopsisService = Depends(
            get_synopsis_service,
        ),
    ) -> SaveSynopsisResult:
        """
        Сохраняет готовый результат генерации синопсиса.

        Используй инструмент только после получения готового
        текста синопсиса.

        Инструмент сохраняет результат в PostgreSQL и возвращает
        идентификатор сохранённой записи.

        При недоступности PostgreSQL возвращает saved=false.
        """

        return service.save_synopsis(
            story_id=story_id,
            thread_id=thread_id,
            user_request=user_request,
            entry_summary=entry_summary,
            idea=idea,
            genre=genre,
            style=style,
            language=language,
            requested_length=requested_length,
            selected_writer=selected_writer,
            draft=draft,
            final_text=final_text,
            critique_passed=critique_passed,
            critique_score=critique_score,
            revision_count=revision_count,
        )
