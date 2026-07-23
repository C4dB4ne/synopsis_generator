from pydantic import BaseModel, Field


class SynopsisRequest(BaseModel):

    story_id: int | None = Field(
        default=None,
        ge=1,
        description=(
            "ID существующей истории. "
            "Не передавать для новой истории."
        ),
    )

    message: str = Field(
        min_length=1,
        description=(
            "Свободное описание того, какой текст "
            "пользователь хочет получить."
        ),
    )

    idea: str | None = None
    genre: str | None = None
    style: str | None = None
    language: str | None = None
    length: str | None = None

    max_revisions: int = Field(
        default=3,
        ge=0,
        le=10,
    )

    max_clarifications: int = Field(
        default=3,
        ge=1,
        le=10,
    )


class SynopsisResumeRequest(BaseModel):

    thread_id: str = Field(
        min_length=1,
        max_length=255,
        description=(
            "Идентификатор ранее "
            "приостановленного workflow."
        ),
    )

    message: str = Field(
        min_length=1,
        description=(
            "Свободный ответ пользователя "
            "на уточняющий вопрос."
        ),
    )


class SynopsisResponse(BaseModel):

    story_id: int | None = None
    synopsis_id: int | None = None

    story_memory_version: int = 0
    story_memory_saved: bool = False

    thread_id: str
    interrupted: bool = False

    status: str

    selected_writer: str | None = None

    draft: str | None = None
    final_text: str | None = None

    critique_passed: bool | None = None
    critique_score: int | None = None
    critique_issues: list[str] = Field(
        default_factory=list,
    )

    revision_count: int = 0
    clarification_count: int = 0

    clarification_message: str | None = None
