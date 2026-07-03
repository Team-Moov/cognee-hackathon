from __future__ import annotations
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# One shared .env at the repo root now, not backend/.env — resolved as an
# absolute path so it works regardless of the CWD the process is launched
# from (backend/app/config.py -> app -> backend -> repo root).
_ROOT_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV_FILE, case_sensitive=False, extra="ignore")

    # Server
    api_host:      str = "0.0.0.0"
    api_port:      int = 8000
    api_log_level: str = "info"

    # PostgreSQL — asyncpg connection string
    database_url:  str = "postgresql://postgres:postgres@localhost:5432/groundhog"

    # Groq — text generation (chat completions)
    llm_api_key:   str = Field(default="", validation_alias="GROQ_API_KEY")
    # NOTE: distinct env var name from root's LLM_MODEL on purpose — root's
    # cognee config wants the litellm-style "groq/llama-3.3-70b-versatile"
    # prefix, while this app's raw `groq` SDK client wants the bare model
    # name. Sharing one .env with one LLM_MODEL variable would silently
    # break whichever process reads the other's format.
    llm_model:     str = Field(default="llama-3.3-70b-versatile", validation_alias="BACKEND_LLM_MODEL")

    # Backwards-compat aliases (Ganesh's .env naming)
    cloud_llm_api_key: str = ""
    cloud_llm_model:   str = ""

    # Local deterministic embeddings for vector recall
    embedding_dimensions: int = 768

    # Orchestrator tuning
    improve_every_n_runs: int = 10
    artifact_root_dir:    str = "./runs"

    # Cognee memory server (root main.py / memory.py) — the ONLY process that
    # imports cognee directly. This app calls it over HTTP for /remember,
    # /check-config, and /query instead of reimplementing those with Postgres.
    # See backend/app/cognee_client.py.
    cognee_api_url: str = "http://localhost:8010"
    cognee_call_timeout_seconds: float = 60.0
    # If the cognee server is unreachable, fall back to the Postgres-only path
    # instead of failing the request. Set False to make cognee failures loud
    # (e.g. in CI or during a demo where you want to know immediately).
    cognee_fallback_on_error: bool = True

    @property
    def effective_llm_api_key(self) -> str:
        return self.llm_api_key or self.cloud_llm_api_key

    @property
    def effective_llm_model(self) -> str:
        return self.llm_model or self.cloud_llm_model or "llama-3.3-70b-versatile"


settings = Settings()
