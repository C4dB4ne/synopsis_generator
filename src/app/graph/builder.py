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
    thriller_writer,
    universal_writer,
)


def build_graph():
    """
    Создает и компилирует основной LangGraph.
    """
    builder = StateGraph(SynopsisState)

    # УЗЛЫ
    builder.add_node(
        "collect_requirements",
        collect_requirements,
    )

    builder.add_node(
        "request_clarification",
        request_clarification,
    )

    builder.add_node(
        "genre_router",
        genre_router,
    )

    builder.add_node(
        "fantasy_writer",
        fantasy_writer,
    )

    builder.add_node(
        "drama_writer",
        drama_writer,
    )

    builder.add_node(
        "thriller_writer",
        thriller_writer,
    )

    builder.add_node(
        "comedy_writer",
        comedy_writer,
    )

    builder.add_node(
        "universal_writer",
        universal_writer,
    )

    builder.add_node(
        "critic",
        critic,
    )

    builder.add_node(
        "language_editor",
        language_editor,
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

    return builder.compile()


synopsis_graph = build_graph()
