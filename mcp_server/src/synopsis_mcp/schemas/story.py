from typing import Any

from pydantic import BaseModel, Field


class CreateStoryResult(BaseModel):
    """Результат создания проекта истории"""

    created: bool

    story_id: int | None = Field(
        default=None,
        ge=1,
    )

    created_at: str | None = None
    error: str | None = None


class GetStoryContextResult(BaseModel):
    """Текущий контекст истории."""

    found: bool

    story_id: int | None = Field(
        default=None,
        ge=1,
    )

    title: str | None = None
    premise: str | None = None
    genre: str | None = None
    style: str | None = None
    language: str | None = None

    memory: dict[str, Any] = Field(
        default_factory=dict,
    )

    memory_version: int = Field(
        default=0,
        ge=0,
    )

    created_at: str | None = None
    updated_at: str | None = None

    error: str | None = None


class SaveStoryMemoryResult(BaseModel):
    """Результат сохранения новой версии памяти."""

    saved: bool

    story_id: int | None = Field(
        default=None,
        ge=1,
    )

    memory_version: int | None = Field(
        default=None,
        ge=1,
    )

    updated_at: str | None = None
    error: str | None = None
