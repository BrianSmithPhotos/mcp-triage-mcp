from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Planner MCP server (aixolotl/microsoft-planner-mcp), run via docker-compose
    planner_mcp_url: str = "http://localhost:8000/mcp"

    # OpenRouter
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_triage_model: str = "openai/gpt-4o-mini"
    openrouter_chat_model: str = "anthropic/claude-sonnet-4.6"

    # Triage target
    message_center_plan_name: str = "Message Center Posts"
    todo_bucket_name: str = "To Do"
    fallback_bucket_name: str = "To Be Deleted"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8001


settings = Settings()
