from typing import Literal

from pydantic import BaseModel, Field


RequirementField = Literal[
    "idea",
    "genre",
    "style",
    "language",
    "length",
]


class RequirementsAnalysis(BaseModel):
    """
    Результат анализа пользовательского ТЗ.
    """
    idea: str | None = Field(
        default=None,
        description=(
            "Основная идея произведения. "
            "Не придумывай её, если пользователь не сообщил идею."
        ),
    )

    genre: str | None = Field(
        default=None,
        description=(
            "Жанр произведения, указанный пользователем "
            "или явно переданный им на выбор генератору."
        ),
    )

    style: str | None = Field(
        default=None,
        description=(
            "Желаемая художественная стилистика."
        ),
    )

    language: str | None = Field(
        default=None,
        description=(
            "Язык итогового текста."
        ),
    )

    length: str | None = Field(
        default=None,
        description=(
            "Требуемый объём текста."
        ),
    )

    requirements_complete: bool = Field(
        description=(
            "Достаточно ли данных для начала генерации "
            "синопсиса."
        ),
    )

    missing_fields: list[RequirementField] = Field(
        default_factory=list,
        description=(
            "Обязательные поля, которые отсутствуют "
            "или не содержат значения."
        ),
    )

    ambiguous_fields: list[RequirementField] = Field(
        default_factory=list,
        description=(
            "Заполненные поля, смысл которых недостаточно "
            "понятен для генерации."
        ),
    )

    clarification_points: list[str] = Field(
        default_factory=list,
        description=(
            "Краткие причины, по которым требуется "
            "уточнение пользователя."
        ),
    )


class ClarificationRequest(BaseModel):
    """
    Сообщение с вопросами для пользователя.
    """

    message: str = Field(
        min_length=1,
        max_length=1500,
        description=(
            "Краткое и понятное сообщение с вопросами, "
            "необходимыми для уточнения ТЗ."
        ),
    )


class CritiqueResult(BaseModel):
    """
    Результат работы критика.

    LLM должна вернуть данные именно в этой структуре,
    а не произвольный текст.
    """
    score: int = Field(
        ge=1,
        le=10,
        description="Оценка синопсиса по шкале от 1 до 10.",
    )

    must_revise: bool = Field(
        description=(
            "True, если текст требует доработки. "
            "False, если текст можно передать редактору."
        ),
    )

    issues: list[str] = Field(
        default_factory=list,
        description="Список проблем, выявленных критиком в синопсисе.",
    )

    revision_instructions: str = Field(
        description=(
            "Краткие и конкретные инструкции по исправлению текущей "
            "версии для писателя."
        ),
    )


class CharacterMemory(BaseModel):
    """Компактная информация о персонаже."""

    name: str
    role: str = ""
    current_state: str = ""

    goals: list[str] = Field(
        default_factory=list,
    )


class StoryMemory(BaseModel):
    """
    Канонический компактный snapshot произведения.

    Хранится между разными LangGraph threads
    """

    summary: str

    characters: list[
        CharacterMemory
    ] = Field(
        default_factory=list,
    )

    world_facts: list[str] = Field(
        default_factory=list,
    )

    locations: list[str] = Field(
        default_factory=list,
    )

    unresolved_threads: list[str] = Field(
        default_factory=list,
    )

    latest_events: list[str] = Field(
        default_factory=list,
    )

    style_rules: list[str] = Field(
        default_factory=list,
    )
