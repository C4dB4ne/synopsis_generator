from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    name="Synopsis MCP Server",
    host="0.0.0.0",
    port=8001,
    stateless_http=True,
    json_response=True,
)


def main() -> None:
    """
    Запускает MCP Server через Streamable HTTP.

    Пока тестово без тулов
    """
    mcp.run(transport="streamable-http",)


if __name__ == "__main__":
    main()
