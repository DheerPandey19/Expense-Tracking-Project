from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://expense:expense@localhost:5433/expense_tracker"
    )
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    telegram_bot_token: str = ""
    telegram_chat_id: int = 0
    telegram_webhook_secret: str = ""


settings = Settings()