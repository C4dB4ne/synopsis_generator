from langgraph.graph import END, START, StateGraph

from app.graph.state import SynopsisState
from app.graph.routes import (
    route_after_requirements,
    route_to_writer,
    route_after_critic,
)
from app.graph.nodes import (
    collect_requirements,
    comedy_writer,
    critic,
    drama_writer,
    fantasy_writer,
    genre_router,
    language_editor,
    request_clarification,
    wait_for_clarification,
    clarification_limit_reached,
    thriller_writer,
    universal_writer,
    load_story_context,
    ensure_story_project,
    memory_manager,
    persist_story,
)
from app.core.logger import log_graph_node


def build_graph(checkpointer=None):
    """
    Создает и компилирует основной LangGraph.
    """
    builder = StateGraph(SynopsisState)

    # УЗЛЫ
    builder.add_node(
        "load_story_context",
        log_graph_node(
            "load_story_context",
            load_story_context,
        ),
    )

    builder.add_node(
        "ensure_story_project",
        log_graph_node(
            "ensure_story_project",
            ensure_story_project,
        ),
    )

    builder.add_node(
        "memory_manager",
        log_graph_node(
            "memory_manager",
            memory_manager,
        ),
    )

    builder.add_node(
        "persist_story",
        log_graph_node(
            "persist_story",
            persist_story,
        ),
    )

    builder.add_node(
        "collect_requirements",
        log_graph_node(
            "collect_requirements",
            collect_requirements,
        ),
    )

    builder.add_node(
        "request_clarification",
        log_graph_node(
            "request_clarification",
            request_clarification,
        ),
    )

    builder.add_node(
        "wait_for_clarification",
        wait_for_clarification,
    )

    builder.add_node(
        "clarification_limit_reached",
        log_graph_node(
            "clarification_limit_reached",
            clarification_limit_reached,
        ),
    )

    builder.add_node(
        "genre_router",
        genre_router,
    )

    builder.add_node(
        "fantasy_writer",
        log_graph_node(
            "fantasy_writer",
            fantasy_writer,
        ),
    )

    builder.add_node(
        "drama_writer",
        log_graph_node(
            "drama_writer",
            drama_writer,
        ),
    )

    builder.add_node(
        "thriller_writer",
        log_graph_node(
            "thriller_writer",
            thriller_writer,
        ),
    )

    builder.add_node(
        "comedy_writer",
        log_graph_node(
            "comedy_writer",
            comedy_writer,
        ),
    )

    builder.add_node(
        "universal_writer",
        log_graph_node(
            "universal_writer",
            universal_writer,
        ),
    )

    builder.add_node(
        "critic",
        log_graph_node(
            "critic",
            critic,
        ),
    )

    builder.add_node(
        "language_editor",
        log_graph_node(
            "language_editor",
            language_editor,
        ),
    )

    # МАРШРУТЫ

    builder.add_edge(
        START,
        "load_story_context",
    )

    builder.add_edge(
        "load_story_context",
        "collect_requirements",
    )

    builder.add_edge(
        "ensure_story_project",
        "genre_router",
    )

    # МАРШРУТИЗАЦИЯ ТРЕБОВАНИЙ - ПРОСТЕНЬКОЕ УСЛОВНОЕ РЕБРО
    builder.add_conditional_edges(
        "collect_requirements",
        route_after_requirements,
    )

    builder.add_edge(
        "request_clarification",
        "wait_for_clarification",
    )

    builder.add_edge(
        "wait_for_clarification",
        "collect_requirements",
    )

    builder.add_edge(
        "clarification_limit_reached",
        END,
    )

    # МАРШРУТИЗАЦИЯ ПО ПИСАТЕЛЯМ
    builder.add_conditional_edges(
        "genre_router",
        route_to_writer,
    )

    # ОТ ПИСАТЕЛЕЙ К КРИТИКУ
    for writer_node in [
        "fantasy_writer",
        "drama_writer",
        "thriller_writer",
        "comedy_writer",
        "universal_writer",
    ]:
        builder.add_edge(
            writer_node,
            "critic",
        )

    # УСЛОВНОЕ РЕБРО КРИТИКА С ЦИКЛОМ ВОЗРАТА ПИСАТЕЛЮ
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
    )

    # ФИНАЛЬНЫЙ ШАГ - К РЕДАКТОРУ + Сохранение
    builder.add_edge(
        "language_editor",
        "memory_manager",
    )

    builder.add_edge(
        "memory_manager",
        "persist_story",
    )

    builder.add_edge(
        "persist_story",
        END,
    )

    return builder.compile(checkpointer=checkpointer)
