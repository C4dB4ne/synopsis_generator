import os

from typing import TypedDict

import psycopg


class SaveSynopsisResult(TypedDict):
    """Результат сохранения синопсиса."""

    saved: bool
    synopsis_id: int | None
    created_at: str | None
    error: str | None


def save_synopsis(
    idea: str,
    genre: str,
    style: str,
    language: str,
    requested_length: str,
    selected_writer: str | None,
    draft: str | None,
    final_text: str | None,
    critique_passed: bool | None,
    critique_score: int | None,
    revision_count: int,
) -> SaveSynopsisResult:
    """
    Сохраняет результат генерации синопсиса в PostgreSQL.

    При недоступности PostgreSQL возращает saved=False,
    а MCP Server продолжает работать.
    """
    try:
        database_url = os.environ.get("DATABASE_URL")

        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured")

        with psycopg.connect(
            database_url,
            connect_timeout=3,
        ) as connection:

            with connection.cursor() as cursor:
                _ensure_synopsis_table(cursor)

                cursor.execute(
                    """
                    INSERT INTO synopsis_generations (
                        idea,
                        genre,
                        style,
                        language,
                        requested_length,
                        selected_writer,
                        draft,
                        final_text,
                        critique_passed,
                        critique_score,
                        revision_count
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING
                        id,
                        created_at
                    """,
                    (
                        idea,
                        genre,
                        style,
                        language,
                        requested_length,
                        selected_writer,
                        draft,
                        final_text,
                        critique_passed,
                        critique_score,
                        revision_count,
                    ),
                )
                synopsis_id, created_at = cursor.fetchone()

            connection.commit()

        return {
            "saved": True,
            "synopsis_id": synopsis_id,
            "created_at": created_at.isoformat(),
            "error": None,
        }

    except Exception as exc:
        return {
            "saved": False,
            "synopsis_id": None,
            "created_at": None,
            "error": str(exc),
        }


def _ensure_synopsis_table(
    cursor: psycopg.Cursor,
) -> None:
    """
    Создаёт таблицу для истории генераций,
    если она ещё не существует.
    """

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS synopsis_generations (
            id BIGSERIAL PRIMARY KEY,

            idea TEXT NOT NULL,
            genre TEXT NOT NULL,
            style TEXT NOT NULL,
            language TEXT NOT NULL,
            requested_length TEXT NOT NULL,

            selected_writer TEXT,

            draft TEXT,
            final_text TEXT,

            critique_passed BOOLEAN,
            critique_score INTEGER,
            revision_count INTEGER NOT NULL DEFAULT 0,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
