import asyncio
import logging

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.config import settings


logger = logging.getLogger("uvicorn.error")


async def get_mcp_tools_safely() -> list[BaseTool]:
    """
    Пытается получить доступные MCP Tools с MCP Server.

    Функция вызывается во время выполнения приложения,
    а не при старте API.

    Если MCP Server недоступен, возращается пустой список,
    но основное приложение продолжает работу.
    """
    client = MultiServerMCPClient(
        {
            "synopsis": {
                "transport": "http",
                "url": settings.mcp_server_url,
            },
        }
    )

    try:
        tools = await asyncio.wait_for(
            client.get_tools(),
            timeout=settings.mcp_connect_timeout_seconds,
        )

    except TimeoutError:
        logger.warning(
            "MCP Server connection timeout after "
            "%.1f seconds. Continuing without MCP tools.",
            settings.mcp_connect_timeout_seconds,
        )
        return []

    except Exception as exc:
        logger.warning(
            "MCP Server  unavailable. "
            "Continuing without MCP tools. Error: %s",
            exc,
        )
        return []

    logger.info(
        "MCP Server available. "
        "Loaded %d tool(s): %s",
        len(tools),
        [
            tool.name
            for tool in tools
        ],
    )

    return tools
