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
