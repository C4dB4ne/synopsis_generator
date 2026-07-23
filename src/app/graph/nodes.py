import json

from langgraph.types import interrupt

from app.graph.state import SynopsisState
from app.core.logger import logger
from app.graph.llm import (
    create_requirements_llm,
    create_clarification_llm,
    create_writer_llm,
    create_critic_llm,
    create_editor_llm,
    create_memory_llm
)
from app.graph.prompts import (
    REQUIREMENTS_ANALYSIS_PROMPT,
    CLARIFICATION_REQUEST_PROMPT,
    MEMORY_UPDATE_PROMPT
)
from app.graph.schemas import (
    ClarificationRequest,
    RequirementField,
    RequirementsAnalysis,
    CritiqueResult,
    StoryMemory
)
from app.mcp.client import (
    find_mcp_tool,
    get_mcp_tools_safely,
    parse_mcp_tool_result,
)


REQUIRED_FIELDS: tuple[
    RequirementField,
    ...,
] = (
    "idea",
    "genre",
    "style",
    "language",
    "length",
)


FIELD_LABELS: dict[
    RequirementField,
    str,
] = {
    "idea": "идею произведения",
    "genre": "жанр",
    "style": "желаемую стилистику",
    "language": "язык итогового текста",
    "length": "требуемый объём",
}


requirements_analyzer = (
    create_requirements_llm()
    .with_structured_output(
        RequirementsAnalysis,
        method="json_schema",
    )
)

clarification_generator = (
    create_clarification_llm()
    .with_structured_output(
        ClarificationRequest,
        method="json_schema",
    )
)

writer_llm = create_writer_llm()
critic_llm = create_critic_llm()

memory_llm = (
    create_memory_llm()
    .with_structured_output(
        StoryMemory,
        method="json_schema",
    )
)

editor_llm = create_editor_llm()


structured_critique_llm = critic_llm.with_structured_output(
    CritiqueResult
)


async def load_story_context(
    state: SynopsisState,
):
    """
    Загружает долговременную память существующей истории.

    При отсутствии story_id ничего не загружает:
    новый story project будет создан после сбора требований.
    """

    story_id = state.get("story_id")
    if not story_id:
        logger.info(
            "STORY MEMORY | new story requested"
        )

        return {
            "story_memory": {},
            "story_memory_version": 0,
            "story_context_loaded": False,
            "status": "story_context_empty",
        }

    tools = await get_mcp_tools_safely()

    get_context_tool = find_mcp_tool(
        tools,
        "get_story_context",
    )

    if get_context_tool is None:
        logger.warning(
            (
                "STORY MEMORY | "
                "get_story_context unavailable | "
                "story_id=%s"
            ),
            story_id,
        )

        return {
            "story_memory": {},
            "story_memory_version": 0,
            "story_context_loaded": False,
            "status": "story_context_unavailable",
        }

    try:
        raw_result = await get_context_tool.ainvoke(
            {
                "story_id": story_id,
            }
        )

        context = parse_mcp_tool_result(raw_result)

        if not context.get(
            "found",
            False,
        ):
            error = context.get("error")

            if error:
                logger.warning(
                    (
                        "STORY MEMORY | "
                        "load failed | "
                        "story_id=%s | error=%s"
                    ),
                    story_id,
                    error,
                )

                return {
                    "story_memory": {},
                    "story_context_loaded": False,
                    "status": "story_context_unavailable",
                }

            raise ValueError(
                f"Story {story_id} was not found."
            )

        logger.info(
            (
                "STORY MEMORY LOADED | "
                "story_id=%s | version=%s"
            ),
            story_id,
            context.get(
                "memory_version",
                0,
            ),
        )

        return {
            "story_title": (
                context.get("title") or ""
            ),

            "story_memory": (
                context.get("memory") or {}
            ),

            "story_memory_version": (
                context.get(
                    "memory_version",
                    0,
                )
            ),

            "story_context_loaded": True,

            "idea": (
                context.get("premise")
                or state.get("idea", "")
            ),

            "genre": (
                context.get("genre")
                or state.get("genre", "")
            ),

            "style": (
                context.get("style")
                or state.get("style", "")
            ),

            "language": (
                context.get("language")
                or state.get(
                    "language",
                    "",
                )
            ),

            "status": "story_context_loaded",
        }

    except ValueError:
        raise

    except Exception as exc:
        logger.warning(
            (
                "STORY MEMORY | "
                "unexpected load error | "
                "story_id=%s | error=%s"
            ),
            story_id,
            exc,
        )

        return {
            "story_memory": {},
            "story_context_loaded": False,
            "status": "story_context_unavailable",
        }


def _build_story_title(
    idea: str,
) -> str:
    """
    Создает техническое название истории
    без дополнительного LLM-вызова
    """

    cleaned = " ".join(
        idea.split()
    )

    if len(cleaned) <= 100:
        return cleaned

    return (
        cleaned[:97].rstrip()
        + "..."
    )


async def ensure_story_project(
    state: SynopsisState,
):
    """
    Создает story project для новой истории.

    Для существующего story_id ничего не создает.
    """

    story_id = state.get("story_id")

    if story_id:
        return {
            "status": "story_project_ready",
        }

    tools = await get_mcp_tools_safely()

    create_tool = find_mcp_tool(
        tools,
        "create_story",
    )

    if create_tool is None:
        logger.warning(
            "STORY MEMORY | create_story unavailable"
        )

        return {
            "status": "story_project_unavailable",
        }

    title = _build_story_title(
        state.get(
            "idea",
            "Без названия",
        )
    )

    try:
        raw_result = await create_tool.ainvoke(
            {
                "title": title,
                "premise": state.get(
                    "idea",
                    "",
                ),
                "genre": state.get(
                    "genre",
                    "",
                ),
                "style": state.get(
                    "style",
                    "",
                ),
                "language": state.get(
                    "language",
                    "",
                ),
            }
        )

        result = parse_mcp_tool_result(
            raw_result
        )

        if not result.get(
            "created",
            False,
        ):
            logger.warning(
                (
                    "STORY MEMORY | "
                    "create_story failed | error=%s"
                ),
                result.get("error"),
            )

            return {
                "status": "story_project_unavailable",
            }

        story_id = result.get(
            "story_id"
        )

        logger.info(
            (
                "STORY CREATED | "
                "story_id=%s | title=%r"
            ),
            story_id,
            title,
        )

        return {
            "story_id": story_id,
            "story_title": title,
            "story_memory": {},
            "story_memory_version": 0,
            "story_context_loaded": True,
            "status": "story_project_ready",
        }

    except Exception as exc:
        logger.warning(
            (
                "STORY MEMORY | "
                "create_story error | %s"
            ),
            exc,
        )

        return {
            "status": "story_project_unavailable",
        }


def collect_requirements(state: SynopsisState):
    """
    Проверяет, достаточно ли данных для генерации синопсиса,
    через LLM со structured output.
    """
    try:
        messages = (
            REQUIREMENTS_ANALYSIS_PROMPT
            .format_messages(
                idea=state.get("idea", ""),
                genre=state.get("genre", ""),
                style=state.get("style", ""),
                language=state.get("language", ""),
                length=state.get("length", ""),
                latest_user_message=state.get(
                    "latest_user_message",
                    "",
                ),
            )
        )

        analysis = requirements_analyzer.invoke(
            messages,
        )

        if not isinstance(
            analysis,
            RequirementsAnalysis,
        ):
            raise TypeError(
                "Requirements analyzer returned "
                "an unexpected result type."
            )

        resolved_idea = _merge_requirement(
            state.get("idea"),
            analysis.idea,
        )

        resolved_genre = _merge_genre(
            state.get("genre"),
            analysis.genre,
        )

        resolved_style = _merge_requirement(
            state.get("style"),
            analysis.style,
        )

        resolved_language = _merge_requirement(
            state.get("language"),
            analysis.language,
        )

        resolved_length = _merge_requirement(
            state.get("length"),
            analysis.length,
        )

        resolved_requirements = {
            "idea": resolved_idea,
            "genre": resolved_genre,
            "style": resolved_style,
            "language": resolved_language,
            "length": resolved_length,
        }

        detected_missing_fields = [
            field
            for field in REQUIRED_FIELDS
            if not resolved_requirements[
                field
            ]
        ]

        missing_fields = _unique_fields(
            [
                *analysis.missing_fields,
                *detected_missing_fields,
            ]
        )

        ambiguous_fields = [
            field
            for field in _unique_fields(
                analysis.ambiguous_fields,
            )
            if field not in missing_fields
        ]

        clarification_points = [
            point.strip()
            for point in analysis.clarification_points
            if point.strip()
        ]

        if (
            missing_fields
            and not clarification_points
        ):
            clarification_points = [
                (
                    f"Необходимо уточнить "
                    f"{FIELD_LABELS[field]}."
                )
                for field in missing_fields
            ]

        requirements_complete = not (
            missing_fields
            or ambiguous_fields
        )

        logger.info(
            (
                "Requirements analyzed | "
                "llm_complete=%s | "
                "resolved_complete=%s | "
                "genre=%r | "
                "style=%r | "
                "language=%r | "
                "length=%r | "
                "missing=%s | "
                "ambiguous=%s"
            ),
            analysis.requirements_complete,
            requirements_complete,
            resolved_genre,
            resolved_style,
            resolved_language,
            resolved_length,
            missing_fields,
            ambiguous_fields,
        )

        return {
            "idea": resolved_idea,
            "genre": resolved_genre,
            "style": resolved_style,
            "language": resolved_language,
            "length": resolved_length,

            "requirements_complete": (
                requirements_complete
            ),

            "missing_fields": missing_fields,
            "ambiguous_fields": ambiguous_fields,
            "clarification_points": (
                clarification_points
            ),

            "clarification_message": "",

            "status": (
                "requirements_complete"
                if requirements_complete
                else "requirements_incomplete"
            ),
        }

    except Exception as exc:
        logger.warning(
            "LLM requirements analysis failed. "
            "Using deterministic fallback. Error: %s",
            exc,
        )

        return _fallback_requirements_analysis(
            state,
        )


def _clean_requirement(
    value: str | None,
) -> str:
    if value is None:
        return ""

    cleaned = value.strip()

    invalid_values = {
        "не указано",
        "не указан",
        "не указана",
        "не определено",
        "неизвестно",
        "none",
        "null",
        "n/a",
    }

    if cleaned.lower() in invalid_values:
        return ""

    return cleaned


def _clean_genre(
    value: str | None,
) -> str:
    genre = _clean_requirement(
        value,
    )

    internal_values = {
        "universal_writer",
        "fantasy_writer",
        "drama_writer",
        "thriller_writer",
        "comedy_writer",
    }

    if genre.lower() in internal_values:
        return ""

    return genre


def _merge_requirement(
    current_value: str | None,
    new_value: str | None,
) -> str:
    new_cleaned = _clean_requirement(
        new_value,
    )

    if new_cleaned:
        return new_cleaned

    return _clean_requirement(
        current_value,
    )


def _merge_genre(
    current_value: str | None,
    new_value: str | None,
) -> str:
    new_genre = _clean_genre(
        new_value,
    )

    if new_genre:
        return new_genre

    return _clean_genre(
        current_value,
    )


def _unique_fields(
    fields: list[RequirementField],
) -> list[RequirementField]:
    """
    Удаляет повторяющиеся названия полей,
    сохраняя исходный порядок.
    """
    return list(
        dict.fromkeys(
            fields,
        )
    )


def _fallback_requirements_analysis(state: SynopsisState):
    """
    Резервная проверка обязательных полей
    без использования LLM
    """

    missing_fields: list[
        RequirementField
    ] = [
        field
        for field in REQUIRED_FIELDS
        if not str(
            state.get(
                field,
                "",
            )
        ).strip()
    ]

    clarification_points = [
        (
            f"Необходимо указать "
            f"{FIELD_LABELS[field]}."
        )
        for field in missing_fields
    ]

    requirements_complete = (
        len(missing_fields) == 0
    )

    return {
        "requirements_complete": (
            requirements_complete
        ),
        "missing_fields": missing_fields,
        "ambiguous_fields": [],
        "clarification_points": (
            clarification_points
        ),
        "clarification_message": "",
        "status": (
            "requirements_complete"
            if requirements_complete
            else "requirements_incomplete"
        ),
    }


def request_clarification(state: SynopsisState):
    """
    Формирует сообщение о недостающих полях.
    """
    try:
        language = (
            state.get(
                "language",
                "",
            ).strip()
            or "русский"
        )

        messages = (
            CLARIFICATION_REQUEST_PROMPT
            .format_messages(
                language=language,
                missing_fields=_format_field_list(
                    state.get(
                        "missing_fields",
                        [],
                    )
                ),
                ambiguous_fields=_format_field_list(
                    state.get(
                        "ambiguous_fields",
                        [],
                    )
                ),
                clarification_points=(
                    _format_clarification_points(
                        state.get(
                            "clarification_points",
                            [],
                        )
                    )
                ),
            )
        )

        clarification = (
            clarification_generator.invoke(
                messages,
            )
        )

        if not isinstance(
            clarification,
            ClarificationRequest,
        ):
            raise TypeError(
                "Clarification generator returned "
                "an unexpected result type."
            )

        message = clarification.message.strip()

        if not message:
            raise ValueError(
                "Clarification message is empty."
            )

    except Exception as exc:
        logger.warning(
            "LLM clarification generation failed. "
            "Using deterministic fallback. Error: %s",
            exc,
        )

        message = _build_fallback_clarification(
            state,
        )

    return {
        "clarification_message": message,
        "status": "needs_clarification",
    }


def _format_field_list(fields: list[str]):
    if not fields:
        return "нет"

    return ", ".join(fields)


def _format_clarification_points(points: list[str]):
    if not points:
        return "нет"

    return "\n".join(
        f"- {point}"
        for point in points
    )


def _build_fallback_clarification(state: SynopsisState):
    """
    Формирует вопрос без LLM,
    если structured output завершился ошибкой
    """
    missing_fields = state.get("missing_fields", [])
    ambiguous_fields = state.get("ambiguous_fields", [])

    field_names = list(
        dict.fromkeys(
            [
                *missing_fields,
                *ambiguous_fields,
            ]
        )
    )

    readable_names = [
        FIELD_LABELS.get(
            field,
            field,
        )
        for field in field_names
    ]

    if readable_names:
        return (
            "Пожалуйста, уточните следующие параметры: "
            + ", ".join(
                readable_names,
            )
            + "."
        )

    clarification_points = state.get(
        "clarification_points",
        [],
    )

    if clarification_points:
        return (
            "Пожалуйста, уточните техническое "
            "задание с учётом следующих замечаний: "
            + "; ".join(
                clarification_points,
            )
            + "."
        )

    return (
        "Пожалуйста, уточните параметры "
        "будущего синопсиса."
    )


def wait_for_clarification(
    state: SynopsisState,
):
    """
    Приостанавливает выполнение графа и ожидает
    свободный ответ пользователя.

    Нода не использует LLM.
    После resume ответ становится новым
    latest_user_message.
    """

    human_message = interrupt(
        {
            "type": "clarification",
            "message": state.get(
                "clarification_message",
                "",
            ),
            "missing_fields": state.get(
                "missing_fields",
                [],
            ),
            "ambiguous_fields": state.get(
                "ambiguous_fields",
                [],
            ),
            "attempt": (
                state.get(
                    "clarification_count",
                    0,
                )
                + 1
            ),
            "max_attempts": state.get(
                "max_clarifications",
                3,
            ),
        }
    )

    message = str(
        human_message
    ).strip()

    clarification_count = (
        state.get(
            "clarification_count",
            0,
        )
        + 1
    )

    logger.info(
        (
            "HITL RESUME RECEIVED | "
            "thread_id=%s | "
            "clarification=%d/%d"
        ),
        state.get("thread_id", "unknown"),
        clarification_count,
        state.get("max_clarifications", 3),
    )

    return {
        "latest_user_message": message,
        "clarification_count": clarification_count,
        "clarification_message": "",
        "status": "clarification_received",
    }


def clarification_limit_reached(
    state: SynopsisState,
):
    """
    Завершает workflow, если пользователь несколько раз
    не предоставил достаточных требований.
    """

    logger.warning(
        (
            "Clarification limit reached | "
            "thread_id=%s | "
            "count=%d"
        ),
        state.get(
            "thread_id",
            "unknown",
        ),
        state.get(
            "clarification_count",
            0,
        ),
    )

    return {
        "status": "clarification_limit_reached",
        "clarification_message": (
            "Не удалось получить достаточно информации "
            "для генерации синопсиса. "
            "Пожалуйста, создайте новый запрос "
            "с более подробным описанием."
        ),
    }


def genre_router(state: SynopsisState):
    """
    Определяет, какой писатель, должен обработать запрос
    """
    genre = (state.get("genre", "").strip().lower())

    genre_keywords = {
        "fantasy_writer": (
            "фэнтези",
            "fantasy",
        ),
        "drama_writer": (
            "драма",
            "drama",
            "драматический",
            "dramatic",
        ),
        "thriller_writer": (
            "триллер",
            "thriller",
        ),
        "comedy_writer": (
            "комедия",
            "comedy",
            "комедийный",
        ),
    }

    selected_writer = "universal_writer"

    for writer, keywords in genre_keywords.items():
        if any(
            keyword in genre
            for keyword in keywords
        ):
            selected_writer = writer
            break

    logger.info(
        "Genre routing | genre=%r | writer=%s",
        genre,
        selected_writer,
    )

    return {
        "selected_writer": selected_writer,
        "status": "writer_selected",
    }


def _run_writer(
    state: SynopsisState,
    writer_role: str,
):
    """
    Внутренняя функция для всех writer-нод.

    При первом запуске создает текст с нуля.
    При повторном запуске перерабатывает draft
    согласно последней критике.
    """
    current_draft = state.get("draft", "")
    revision_instructions = state.get(
        "revision_instructions",
        ""
    )

    is_revision = bool(
        current_draft
        and revision_instructions
        and not state.get("critique_passed", False)
    )

    system_prompt = f"""
Ты профессиональный сценарист.
Твоя специализация: {writer_role}.

Подготовь качественный синопсис строго по техническому заданию.

КРИТИЧЕСКИЕ ПРАВИЛА:

1. Пиши исключительно на языке:
   {state.get("language", "русский")}

2. Не смешивай разные языки в одном тексте.

3. Не используй иностранные слова,
   если этого прямо не требует техническое задание.

4. Текст должен быть грамматически связным.

5. Соблюдай жанр и заявленную стилистику.

Не добавляй комментарии о своей работе.
Не объясняй процесс генерации.
Верни только готовый текст.
""".strip()

    story_memory = state.get(
        "story_memory",
        {},
    )

    memory_context = (
        json.dumps(
            story_memory,
            ensure_ascii=False,
            indent=2,
        )
        if story_memory
        else "Предыдущей памяти нет."
    )

    base_request = f"""
ИСХОДНОЕ ТЕХНИЧЕСКОЕ ЗАДАНИЕ

Идея:
{state.get("idea", "")}

Жанр:
{state.get("genre", "")}

Стилистика:
{state.get("style", "")}

Язык:
{state.get("language", "")}

Желаемый объем:
{state.get("length", "")}


НОВОЕ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ

{state.get("latest_user_message", "")}


ДОЛГОВРЕМЕННЫЙ КОНТЕКСТ ПРОИЗВЕДЕНИЯ

{memory_context}

Используй долговременный контекст для сохранения
последовательности событий, персонажей, отношений
и правил мира.

Новый явный запрос пользователя имеет приоритет,
если он сознательно изменяет предыдущие факты.
""".strip()

    if is_revision:
        user_prompt = f"""
{base_request}

ТЕКУЩАЯ ВЕРСИЯ

{current_draft}

ЗАМЕЧАНИЯ КРИТИКА

{revision_instructions}

Переработай текущую версию.

Исправь указанные содержательные проблемы,
но сохрани сильные стороны текста и исходное техническое задание.

Верни только новую полную версию текста.

ДОЛГОВРЕМЕННЫЙ КОНТЕКСТ ПРОИЗВЕДЕНИЯ

{memory_context}

Используй этот контекст для сохранения
последовательности событий, персонажей и правил мира.

Новый явный запрос пользователя имеет приоритет,
если он сознательно изменяет предыдущие факты.
""".strip()

    else:
        user_prompt = f"""
{base_request}

Создай первую версию синопсиса.

Верни только готовый текст.
""".strip()

    response = writer_llm.invoke(
        [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
    )

    updates: dict = {
        "draft": str(response.content),
        "status": "draft_generated",
    }

    if is_revision:
        updates["revision_count"] = (
            state.get("revision_count", 0) + 1
        )

    logger.info(
        (
            "Writer execution | "
            "writer=%s | "
            "revision=%s | "
            "revision_count=%d"
        ),
        writer_role,
        is_revision,
        state.get(
            "revision_count",
            0,
        ),
    )

    return updates


def fantasy_writer(state: SynopsisState):
    return _run_writer(
        state,
        writer_role=(
            "фэнтези: миростроение, атмосфера, "
            "мифология и внутренние правила мира"
        ),
    )


def drama_writer(state: SynopsisState):
    return _run_writer(
        state,
        writer_role=(
            "драма: характеры, эмоциональный конфликт, "
            "развитие отношений и трагическая судьба"
        ),
    )


def thriller_writer(state: SynopsisState):
    return _run_writer(
        state,
        writer_role=(
            "триллер: напряжение, опасность, "
            "неопределенность и повышение ставок"
        ),
    )


def comedy_writer(state: SynopsisState):
    return _run_writer(
        state,
        writer_role=(
            "комедия: комедийные ситуации, контраст, "
            "темп и выразительные характеры"
        ),
    )


def universal_writer(state: SynopsisState):
    return _run_writer(
        state,
        writer_role=(
            "универсальная сценарная драматургия"
        ),
    )


def critic(state: SynopsisState):
    """
    Оценивает только текущую версию текста.

    Предыдущие версии и предыдущие оценки не передаются
    модели.
    """
    story_memory = json.dumps(
        state.get(
            "story_memory",
            {},
        ),
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
Ты строгий профессиональный сценарный критик.

Оцени текущий синопсис независимо от предыдущих итераций.

Проверь:

1. Соответствие исходной идее.
2. Соответствие жанру.
3. Соответствие заявленной стилистике.
4. Логичность событий.
5. Наличие понятного центрального конфликта.
6. Мотивацию персонажей.
7. Связность повествования.
8. Выразительность и интерес истории.
9. Полностью ли текст написан на указанном пользователем языке,
   без необоснованного смешивания языков.
10. Строго ли соблюдены формальные требования пользователя:
    - требуемый объем;
    - количество абзацев, если оно указано;

Если пользователь явно указал количество абзацев или другой
формальный параметр, его нарушение считается причиной для доработки.

Не оценивай орфографию и пунктуацию:
этим займется отдельный языковой редактор.

ИСХОДНОЕ ТЕХНИЧЕСКОЕ ЗАДАНИЕ

Идея:
{state.get("idea", "")}

Жанр:
{state.get("genre", "")}

Стилистика:
{state.get("style", "")}

Язык:
{state.get("language", "")}

Желаемый объем:
{state.get("length", "")}

ТЕКУЩАЯ ВЕРСИЯ

{state.get("draft", "")}

Правила оценки:

- 8–10: текст можно передавать редактору;
- 1–7: требуется содержательная переработка.

Если требуется переработка,
дай конкретные инструкции писателю.

КОНТЕКСТ ПРЕДЫДУЩИХ ЧАСТЕЙ

{story_memory}

При оценке проверь,
что новая версия не противоречит установленным
фактам истории без явного указания пользователя.
""".strip()

    result = structured_critique_llm.invoke(prompt)

    passed = (
        not result.must_revise
        and result.score >= 8
    )

    logger.info(
        (
            "Critic result | "
            "score=%d | "
            "passed=%s | "
            "issues=%d | "
            "revision=%d/%d"
        ),
        result.score,
        passed,
        len(result.issues),
        state.get("revision_count", 0),
        state.get("max_revisions", 3),
    )

    return {
        "critique_passed": passed,
        "critique_score": result.score,
        "critique_issues": result.issues,
        "revision_instructions": (
            result.revision_instructions
        ),
        "status": (
            "critique_passed"
            if passed
            else "revision_required"
        ),
    }


def language_editor(state: SynopsisState):
    """
    Не меняет сюжет и содержательную часть.

    Выполняет только языковую редактуру.
    """
    system_prompt = """
Ты профессиональный литературный редактор.

КРИТИЧЕСКОЕ ПРАВИЛО:
твой ответ должен содержать ТОЛЬКО окончательную
отредактированную версию текста.

Запрещено:
- объяснять изменения;
- перечислять исправления;
- добавлять вступления;
- добавлять примечания;
- писать комментарии редактора.

Не изменяй сюжет, персонажей, события и смысл.
""".strip()

    user_prompt = f"""
Язык текста:
{state.get("language", "русский")}

Исправь:
- грамматику;
- орфографию;
- пунктуацию;
- лексические повторы;
- неестественные формулировки;
- плохо читаемые конструкции.

ТЕКСТ:

{state.get("draft", "")}
""".strip()

    response = editor_llm.invoke(
        [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
    )

    return {
        "final_text": str(response.content),
        "status": (
            "completed"
            if state.get("critique_passed", False)
            else "completed_with_warnings"
        ),
    }


def memory_manager(
    state: SynopsisState,
):
    """
    Обновляет компактную долговременную память
    после получения финального текста.
    """

    final_text = state.get(
        "final_text",
        "",
    )

    if not final_text:
        return {
            "story_memory_ready": False,
            "status": "memory_skipped",
        }

    previous_memory = state.get(
        "story_memory",
        {},
    )

    try:
        messages = (
            MEMORY_UPDATE_PROMPT
            .format_messages(
                story_title=state.get(
                    "story_title",
                    "",
                ),
                premise=state.get(
                    "idea",
                    "",
                ),
                genre=state.get(
                    "genre",
                    "",
                ),
                style=state.get(
                    "style",
                    "",
                ),
                language=state.get(
                    "language",
                    "",
                ),
                previous_memory=json.dumps(
                    previous_memory,
                    ensure_ascii=False,
                    indent=2,
                ),
                user_request=state.get(
                    "latest_user_message",
                    "",
                ),
                final_text=final_text,
            )
        )

        memory = memory_llm.invoke(
            messages
        )

        if not isinstance(
            memory,
            StoryMemory,
        ):
            raise TypeError(
                "Memory manager returned "
                "unexpected result type."
            )

        memory_payload = (
            memory.model_dump()
        )

        logger.info(
            (
                "STORY MEMORY COMPACTED | "
                "story_id=%s | "
                "characters=%d | "
                "facts=%d | "
                "threads=%d"
            ),
            state.get("story_id"),
            len(memory.characters),
            len(memory.world_facts),
            len(memory.unresolved_threads),
        )

        return {
            "story_memory": memory_payload,
            "story_memory_ready": True,
            "status": "memory_ready",
        }

    except Exception as exc:
        # Очень важно:
        # не портим существующую memory
        # при неудаче LLM.
        logger.warning(
            (
                "STORY MEMORY COMPACTION FAILED | "
                "story_id=%s | error=%s"
            ),
            state.get("story_id"),
            exc,
        )

        return {
            "story_memory_ready": False,
            "status": "memory_failed",
        }


async def persist_story(
    state: SynopsisState,
):
    """
    Сохраняет generation и затем новую версию
    долговременной памяти через MCP.
    """

    final_status = (
        "completed"
        if state.get(
            "critique_passed",
            False,
        )
        else "completed_with_warnings"
    )

    tools = await get_mcp_tools_safely()

    if not tools:
        return {
            "story_memory_saved": False,
            "status": final_status,
        }

    save_synopsis_tool = find_mcp_tool(
        tools,
        "save_synopsis",
    )

    save_memory_tool = find_mcp_tool(
        tools,
        "save_story_memory",
    )

    synopsis_id = None

    # 1. Сохраняем generation.
    if save_synopsis_tool is not None:
        try:
            memory = state.get(
                "story_memory",
                {},
            )

            raw_result = (
                await save_synopsis_tool.ainvoke(
                    {
                        "story_id": state.get(
                            "story_id",
                        ),
                        "thread_id": state.get(
                            "thread_id",
                        ),
                        "user_request": state.get(
                            "original_user_request",
                            state.get(
                                "latest_user_message",
                                "",
                            ),
                        ),
                        "entry_summary": (
                            memory.get(
                                "summary"
                            )
                            if memory
                            else None
                        ),
                        "idea": state.get(
                            "idea",
                            "",
                        ),
                        "genre": state.get(
                            "genre",
                            "",
                        ),
                        "style": state.get(
                            "style",
                            "",
                        ),
                        "language": state.get(
                            "language",
                            "",
                        ),
                        "requested_length": (
                            state.get(
                                "length",
                                "",
                            )
                        ),
                        "selected_writer": (
                            state.get(
                                "selected_writer",
                            )
                        ),
                        "draft": state.get(
                            "draft",
                        ),
                        "final_text": state.get(
                            "final_text",
                            "",
                        ),
                        "critique_passed": (
                            state.get(
                                "critique_passed",
                            )
                        ),
                        "critique_score": (
                            state.get(
                                "critique_score",
                            )
                        ),
                        "revision_count": (
                            state.get(
                                "revision_count",
                                0,
                            )
                        ),
                    }
                )
            )

            save_result = (
                parse_mcp_tool_result(
                    raw_result
                )
            )

            if save_result.get(
                "saved",
                False,
            ):
                synopsis_id = (
                    save_result.get(
                        "synopsis_id"
                    )
                )

                logger.info(
                    (
                        "SYNOPSIS PERSISTED | "
                        "synopsis_id=%s | "
                        "story_id=%s"
                    ),
                    synopsis_id,
                    state.get("story_id"),
                )

        except Exception as exc:
            logger.warning(
                "save_synopsis failed: %s",
                exc,
            )

    # 2. Сохраняем memory.
    story_id = state.get(
        "story_id"
    )

    memory_ready = state.get(
        "story_memory_ready",
        False,
    )

    if (
        story_id
        and memory_ready
        and save_memory_tool is not None
    ):
        try:
            raw_result = (
                await save_memory_tool.ainvoke(
                    {
                        "story_id": story_id,
                        "memory": state.get(
                            "story_memory",
                            {},
                        ),
                        "source_generation_id": (
                            synopsis_id
                        ),
                    }
                )
            )

            save_memory_result = (
                parse_mcp_tool_result(
                    raw_result
                )
            )

            if save_memory_result.get(
                "saved",
                False,
            ):
                version = (
                    save_memory_result.get(
                        "memory_version",
                        state.get(
                            "story_memory_version",
                            0,
                        ),
                    )
                )

                logger.info(
                    (
                        "STORY MEMORY SAVED | "
                        "story_id=%s | version=%s"
                    ),
                    story_id,
                    version,
                )

                return {
                    "synopsis_id": synopsis_id,
                    "story_memory_saved": True,
                    "story_memory_version": version,
                    "status": final_status,
                }

        except Exception as exc:
            logger.warning(
                "save_story_memory failed: %s",
                exc,
            )

    return {
        "synopsis_id": synopsis_id,
        "story_memory_saved": False,
        "status": final_status,
    }
