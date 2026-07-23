import asyncio
import logging
import json
from typing import Any

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


def find_mcp_tool(
    tools: list[BaseTool],
    tool_name: str,
) -> BaseTool | None:
    """
    Ищет MCP tool по имени среди уже загруженных инструментов.

    Функция не выполняет новое подключение к MCP Server.
    """
    for tool in tools:
        if tool.name == tool_name:
            return tool

    return None


def parse_mcp_tool_result(result: Any):
    """
    Извлекает JSON payload из результата MCP tool

    Поддерживает обычный dict, JSON-строку
    и список text-content blocks
    """
    if isinstance(result, dict):
        text = result.get("text")

        if isinstance(text, str):
            return json.loads(text)

        return result

    if isinstance(result, str):
        return json.loads(result)

    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                text = item.get("text")

                if isinstance(text, str):
                    return json.loads(text)

            text = getattr(
                item,
                "text",
                None,
            )

            if isinstance(text, str):
                return json.loads(text)

    raise ValueError(
        "Unsupported MCP tool result format."
    )
