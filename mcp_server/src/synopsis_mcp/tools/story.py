from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from synopsis_mcp.dependencies import (
    get_story_service,
)
from synopsis_mcp.schemas.story import (
    CreateStoryResult,
    GetStoryContextResult,
    SaveStoryMemoryResult,
)
from synopsis_mcp.services.story import StoryService


def register_story_tools(
    mcp: FastMCP,
) -> None:
    """Регистрирует инструменты долговременной памяти."""

    @mcp.tool()
    def create_story(
        title: Annotated[
            str,
            Field(
                min_length=1,
                description="Название истории.",
            ),
        ],
        premise: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Основная концепция истории."
                ),
            ),
        ],
        genre: Annotated[
            str,
            Field(
                min_length=1,
                description="Жанр истории.",
            ),
        ],
        style: Annotated[
            str,
            Field(
                min_length=1,
                description=(
                    "Художественная стилистика."
                ),
            ),
        ],
        language: Annotated[
            str,
            Field(
                min_length=1,
                description="Язык истории.",
            ),
        ],
        service: StoryService = Depends(
            get_story_service,
        ),
    ) -> CreateStoryResult:
        """
        Создаёт новый проект истории.

        Использовать при начале нового независимого
        произведения. Возвращает story_id.
        """

        return service.create_story(
            title=title,
            premise=premise,
            genre=genre,
            style=style,
            language=language,
        )

    @mcp.tool()
    def get_story_context(
        story_id: Annotated[
            int,
            Field(
                ge=1,
                description=(
                    "Идентификатор истории."
                ),
            ),
        ],
        service: StoryService = Depends(
            get_story_service,
        ),
    ) -> GetStoryContextResult:
        """
        Возвращает актуальный долговременный
        контекст истории по story_id.
        """

        return service.get_story_context(
            story_id=story_id,
        )

    @mcp.tool()
    def save_story_memory(
        story_id: Annotated[
            int,
            Field(
                ge=1,
                description=(
                    "Идентификатор истории."
                ),
            ),
        ],
        memory: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Новый полный snapshot "
                    "долговременной памяти истории."
                ),
            ),
        ],
        source_generation_id: Annotated[
            int | None,
            Field(
                ge=1,
                description=(
                    "Генерация, на основании "
                    "которой обновлена память."
                ),
            ),
        ] = None,
        service: StoryService = Depends(
            get_story_service,
        ),
    ) -> SaveStoryMemoryResult:
        """
        Сохраняет новую полную версию памяти.

        Инструмент не объединяет память самостоятельно:
        передаваемый memory считается новым
        каноническим snapshot.
        """

        return service.save_story_memory(
            story_id=story_id,
            memory=memory,
            source_generation_id=(
                source_generation_id
            ),
        )
