from langgraph.types import interrupt

from app.graph.state import SynopsisState
from app.core.logger import logger
from app.graph.llm import (
    create_requirements_llm,
    create_clarification_llm,
    create_writer_llm,
    create_critic_llm,
    create_editor_llm,
)
from app.graph.prompts import (
    REQUIREMENTS_ANALYSIS_PROMPT,
    CLARIFICATION_REQUEST_PROMPT,
)
from app.graph.schemas import (
    ClarificationRequest,
    RequirementField,
    RequirementsAnalysis,
    CritiqueResult,
)


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


writer_llm = create_writer_llm()
critic_llm = create_critic_llm()
editor_llm = create_editor_llm()


structured_critique_llm = critic_llm.with_structured_output(
    CritiqueResult
)


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
                "complete=%s | "
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
