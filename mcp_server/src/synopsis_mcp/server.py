from fastmcp import FastMCP

from synopsis_mcp.tools.health import register_health_tools
from synopsis_mcp.tools.synopsis import register_synopsis_tools
from synopsis_mcp.tools.story import register_story_tools


mcp = FastMCP(name="Synopsis MCP Server")


register_health_tools(mcp)
register_synopsis_tools(mcp)
register_story_tools(mcp)


def main() -> None:
    """Запускает Synopsis MCP Server."""

    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8001,
    )


if __name__ == "__main__":
    main()
