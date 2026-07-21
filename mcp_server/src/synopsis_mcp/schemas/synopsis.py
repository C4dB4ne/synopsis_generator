from pydantic import BaseModel, Field


class SaveSynopsisResult(BaseModel):
    """Результат сохранения синопсиса."""

    saved: bool

    synopsis_id: int | None = Field(
        default=None,
        ge=1,
    )

    created_at: str | None = None
    error: str | None = None
