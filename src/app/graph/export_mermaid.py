from pathlib import Path

from app.graph.builder import synopsis_graph


ARTIFACTS_DIR = Path("/app/artifacts")
MERMAID_FILE = ARTIFACTS_DIR / "synopsis_graph.mmd"
PNG_FILE = ARTIFACTS_DIR / "synopsis_graph.png"


def export_graph():
    """
    Экспортирует текущий LangGraph в .mmd и .png
    """
    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    drawable_graph = synopsis_graph.get_graph()

    # Получение исходного Mermaid-кода
    mermaid_code = drawable_graph.draw_mermaid()

    MERMAID_FILE.write_text(
        mermaid_code,
        encoding="utf-8",
    )

    # Рендер Мермейд в ПНГ
    drawable_graph.draw_mermaid_png(
        output_file_path=str(PNG_FILE)
    )

    print(f"Mermaid файл сохранен : {MERMAID_FILE}")
    print(f"PNG сохранен : {PNG_FILE}")


if __name__ == "__main__":
    export_graph()
