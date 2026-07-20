from pydantic import BaseModel, Field

from app.graph.state import SynopsisState
from app.graph.llm import (
    create_writer_llm,
    create_critic_llm,
    create_editor_llm
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


writer_llm = create_writer_llm()
critic_llm = create_critic_llm()
editor_llm = create_editor_llm()


structured_critique_llm = critic_llm.with_structured_output(
    CritiqueResult
)


def collect_requirements(state: SynopsisState):
    """
    Проверяет, достаточно ли данных для генерации синопсиса.

    Пока эта нода полностью ручная, но в будущем хочу попробовать
    использовать LLM для проверки полноты ТЗ.
    """
    required_fields = {
        "idea": "Идея",
        "genre": "Жанр",
        "style": "Стиль",
        "language": "Язык",
        "length": "Желаемый объем",
    }

    missing_fields: list[str] = []

    for field_name, human_name in required_fields.items():
        value = state.get(field_name)

        if not value or not str(value).strip():
            missing_fields.append(human_name)

    if missing_fields:
        return {
            "requirements_complete": False,
            "missing_fields": missing_fields,
            "status": "clarification_required",
        }

    return {
        "requirements_complete": True,
        "missing_fields": [],
        "status": "requirements_collected",
    }


def request_clarification(state: SynopsisState):
    """
    Формирует сообщение о недостающих полях.

    Позже на этой ноде буду тестить LangGraph interrupt()
    чтобы граф реально приостанавливался и ожидал пользователя.
    """
    missing_fields = state.get("missing_fields", [])
    fields_text = ", ".join(missing_fields)

    message = (
        "Для написания синопсиса недостаточно данных. "
        f"Пожалуйста, уточните: {fields_text}."
    )

    return {
        "clarification_message": message,
        "status": "clarification_required",
    }


def genre_router(state: SynopsisState):
    """
    Определяет, какой писатель, должен обработать запрос
    """
    genre = state.get("genre", "").strip().lower()

    genre_map = {
        "фэнтези": "fantasy_writer",
        "fantasy": "fantasy_writer",
        "драма": "drama_writer",
        "drama": "drama_writer",
        "триллер": "thriller_writer",
        "thriller": "thriller_writer",
        "комедия": "comedy_writer",
        "comedy": "comedy_writer",
    }

    selected_writer = genre_map.get(
        genre,
        "universal_writer",
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
