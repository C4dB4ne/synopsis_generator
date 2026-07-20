from langchain_ollama import ChatOllama

from app.config import settings


def create_writer_llm() -> ChatOllama:
    """
    Модель для творческой генерации текста (бумага-маратель)
    - temperature=0.8: для разнообразия и креативности
    """
    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=0.6,
        reasoning=False,
    )


def create_critic_llm() -> ChatOllama:
    """
    Модель для критики текста (критик)
    """
    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=0.1,
        reasoning=False,
    )


def create_editor_llm() -> ChatOllama:
    """
    Модель для финальной редакции текста (редактор)
    """
    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=0.0,
        reasoning=False,
    )
