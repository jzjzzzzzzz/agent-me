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
    max_document_bytes: int = Field(default=1_000_000, ge=1, le=50_000_000)
    max_history_chars: int = Field(default=24_000, ge=1, le=200_000)
    max_answer_chars: int = Field(default=50_000, ge=1, le=200_000)
    max_provider_response_bytes: int = Field(default=2_000_000, ge=1_024, le=50_000_000)
    max_request_body_bytes: int = Field(default=262_144, ge=1_024, le=10_000_000)
    provider_timeout_seconds: float = Field(default=60, ge=1, le=300)
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    cors_origins: str = "http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def provider_state(self) -> str:
        configured = [self.llm_base_url, self.llm_api_key, self.llm_model]
        if not any(configured):
            return "extractive"
        return "openai-compatible" if all(configured) else "misconfigured"


@lru_cache
def get_settings() -> Settings:
    return Settings()
