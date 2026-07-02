from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Server
    api_host:      str = "0.0.0.0"
    api_port:      int = 8000
    api_log_level: str = "info"

    # PostgreSQL — asyncpg connection string
    database_url:  str = "postgresql://postgres:postgres@localhost:5432/groundhog"

    # Groq — text generation (chat completions)
    llm_api_key:   str = Field(default="", validation_alias="GROQ_API_KEY")
    llm_model:     str = "llama-3.3-70b-versatile"

    # Backwards-compat aliases (Ganesh's .env naming)
    cloud_llm_api_key: str = ""
    cloud_llm_model:   str = ""

    # Local deterministic embeddings for vector recall
    embedding_dimensions: int = 768

    # Orchestrator tuning
    improve_every_n_runs: int = 10
    artifact_root_dir:    str = "./runs"

    @property
    def effective_llm_api_key(self) -> str:
        return self.llm_api_key or self.cloud_llm_api_key

    @property
    def effective_llm_model(self) -> str:
        return self.llm_model or self.cloud_llm_model or "llama-3.3-70b-versatile"


settings = Settings()
