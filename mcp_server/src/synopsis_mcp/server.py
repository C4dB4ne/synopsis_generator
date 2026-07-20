from mcp.server.fastmcp import FastMCP

from synopsis_mcp.tools.health import check_service
from synopsis_mcp.tools.synopsis import save_synopsis


mcp = FastMCP(
    name="Synopsis MCP Server",
    host="0.0.0.0",
    port=8001,
    stateless_http=True,
    json_response=True,
)


# Регистрация MCP Tools
mcp.tool()(check_service)
mcp.tool()(save_synopsis)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
