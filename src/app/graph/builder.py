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
)
from app.core.logger import log_graph_node


def build_graph(checkpointer=None):
    """
    Создает и компилирует основной LangGraph.
    """
    builder = StateGraph(SynopsisState)

    # УЗЛЫ
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

    # ТОЧКА ВХОДА
    builder.add_edge(
        START,
        "collect_requirements",
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

    # ФИНАЛЬНЫЙ ШАГ - К РЕДАКТОРУ
    builder.add_edge(
        "language_editor",
        END,
    )

    return builder.compile(checkpointer=checkpointer)

