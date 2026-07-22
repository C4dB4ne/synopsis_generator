from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    app_name: str = "Synopsis Generator"

    ollama_base_url: str
    llm_model: str

    database_url: str

    mcp_server_url: str
    mcp_connect_timeout_seconds: float

    log_level: str = "INFO"
    logs_directory: str = "/app/logs"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
