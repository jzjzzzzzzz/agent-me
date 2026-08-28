from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "My Answer Agent"
    app_description: str = "A grounded question-answering agent built from your documents."
    knowledge_dir: str = "knowledge"
    max_question_chars: int = Field(default=8_000, ge=1, le=100_000)
    max_context_chars: int = Field(default=12_000, ge=1, le=100_000)
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    cors_origins: str = "http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
