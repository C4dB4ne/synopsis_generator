from pathlib import Path

from app.graph.builder import build_graph

ARTIFACTS_DIR = Path("/app/artifacts")
MERMAID_FILE = ARTIFACTS_DIR / "synopsis_graph.mmd"
PNG_FILE = ARTIFACTS_DIR / "synopsis_graph.png"


def export_graph():
    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    synopsis_graph = build_graph()

    drawable_graph = (
        synopsis_graph.get_graph()
    )

    mermaid_code = (
        drawable_graph.draw_mermaid()
    )

    MERMAID_FILE.write_text(
        mermaid_code,
        encoding="utf-8",
    )

    drawable_graph.draw_mermaid_png(
        output_file_path=str(
            PNG_FILE
        )
    )

    print(
        f"Mermaid файл сохранен: "
        f"{MERMAID_FILE}"
    )

    print(
        f"PNG сохранен: "
        f"{PNG_FILE}"
    )


if __name__ == "__main__":
    export_graph()
