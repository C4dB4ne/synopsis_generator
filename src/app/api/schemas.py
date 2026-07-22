from pydantic import BaseModel, Field


class SynopsisRequest(BaseModel):

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


class SynopsisResponse(BaseModel):
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

    clarification_message: str | None = None
