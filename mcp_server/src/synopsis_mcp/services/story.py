import os
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from synopsis_mcp.schemas.story import (
    CreateStoryResult,
    GetStoryContextResult,
    SaveStoryMemoryResult,
)


class StoryService:
    """Сервис долговременной памяти историй."""

    @staticmethod
    def _get_database_url() -> str:
        database_url = os.environ.get(
            "DATABASE_URL",
        )

        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured."
            )

        return database_url

    def create_story(
        self,
        title: str,
        premise: str,
        genre: str,
        style: str,
        language: str,
    ) -> CreateStoryResult:
        """
        Создаёт новый проект истории

        Память создаётся пустой с memory_version=0.
        """

        try:
            with psycopg.connect(
                self._get_database_url(),
                connect_timeout=3,
            ) as connection:

                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO story_projects (
                            title,
                            premise,
                            genre,
                            style,
                            language
                        )
                        VALUES (
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
                            title,
                            premise,
                            genre,
                            style,
                            language,
                        ),
                    )

                    row = cursor.fetchone()

                    if row is None:
                        raise RuntimeError(
                            "Story INSERT returned no row."
                        )

                    story_id, created_at = row

                connection.commit()

            return CreateStoryResult(
                created=True,
                story_id=story_id,
                created_at=created_at.isoformat(),
                error=None,
            )

        except Exception as exc:
            return CreateStoryResult(
                created=False,
                story_id=None,
                created_at=None,
                error=str(exc),
            )

    def get_story_context(
        self,
        story_id: int,
    ) -> GetStoryContextResult:
        """Возвращает актуальный snapshot памяти истории,"""

        try:
            with psycopg.connect(
                self._get_database_url(),
                connect_timeout=3,
            ) as connection:

                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            id,
                            title,
                            premise,
                            genre,
                            style,
                            language,
                            memory,
                            memory_version,
                            created_at,
                            updated_at
                        FROM story_projects
                        WHERE id = %s
                        """,
                        (story_id,),
                    )

                    row = cursor.fetchone()

            if row is None:
                return GetStoryContextResult(
                    found=False,
                    story_id=story_id,
                    error=None,
                )

            (
                stored_story_id,
                title,
                premise,
                genre,
                style,
                language,
                memory,
                memory_version,
                created_at,
                updated_at,
            ) = row

            return GetStoryContextResult(
                found=True,
                story_id=stored_story_id,
                title=title,
                premise=premise,
                genre=genre,
                style=style,
                language=language,
                memory=memory or {},
                memory_version=memory_version,
                created_at=created_at.isoformat(),
                updated_at=updated_at.isoformat(),
                error=None,
            )

        except Exception as exc:
            return GetStoryContextResult(
                found=False,
                story_id=story_id,
                error=str(exc),
            )

    def save_story_memory(
        self,
        story_id: int,
        memory: dict[str, Any],
        source_generation_id: int | None = None,
    ) -> SaveStoryMemoryResult:
        """
        Атомарно сохраняет новую версию памяти.

        Обновляет текущий snapshot в story_projects
        и добавляет immutable-запись в
        story_memory_versions.
        """

        try:
            with psycopg.connect(
                self._get_database_url(),
                connect_timeout=3,
            ) as connection:

                with connection.cursor() as cursor:

                    # Блокирую story на время вычисления
                    # следующей версии, чтобы версия памяти
                    # увеличивалась последовательно.
                    cursor.execute(
                        """
                        SELECT memory_version
                        FROM story_projects
                        WHERE id = %s
                        FOR UPDATE
                        """,
                        (story_id,),
                    )

                    row = cursor.fetchone()

                    if row is None:
                        return SaveStoryMemoryResult(
                            saved=False,
                            story_id=story_id,
                            memory_version=None,
                            updated_at=None,
                            error=(
                                f"Story {story_id} "
                                "was not found."
                            ),
                        )

                    current_version = row[0]
                    new_version = (
                        current_version + 1
                    )

                    cursor.execute(
                        """
                        UPDATE story_projects
                        SET
                            memory = %s,
                            memory_version = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING updated_at
                        """,
                        (
                            Jsonb(memory),
                            new_version,
                            story_id,
                        ),
                    )

                    updated_row = cursor.fetchone()

                    if updated_row is None:
                        raise RuntimeError(
                            "Story UPDATE returned no row."
                        )

                    updated_at = updated_row[0]

                    cursor.execute(
                        """
                        INSERT INTO story_memory_versions (
                            story_id,
                            version,
                            memory,
                            source_generation_id
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        """,
                        (
                            story_id,
                            new_version,
                            Jsonb(memory),
                            source_generation_id,
                        ),
                    )

                connection.commit()

            return SaveStoryMemoryResult(
                saved=True,
                story_id=story_id,
                memory_version=new_version,
                updated_at=updated_at.isoformat(),
                error=None,
            )

        except Exception as exc:
            return SaveStoryMemoryResult(
                saved=False,
                story_id=story_id,
                memory_version=None,
                updated_at=None,
                error=str(exc),
            )
