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

    # ── Multi-provider chat LLM (groq | gemini | aimlapi) ────────────────────
    # The subagents call this via litellm, so one provider selector drives both
    # the root cognee server (llm_setup.py) and this app's own LLM calls.
    groundhog_llm_provider: str = Field(default="groq", validation_alias="GROUNDHOG_LLM_PROVIDER")
    groq_api_key:    str = Field(default="", validation_alias="GROQ_API_KEY")
    gemini_api_key:  str = Field(default="", validation_alias="GEMINI_API_KEY")
    aimlapi_api_key: str = Field(default="", validation_alias="AIMLAPI_API_KEY")

    # Legacy alias kept so older code/.env referencing GROQ_API_KEY still works.
    llm_api_key:   str = Field(default="", validation_alias="GROQ_API_KEY")
    llm_model:     str = Field(default="llama-3.3-70b-versatile", validation_alias="BACKEND_LLM_MODEL")

    # Backwards-compat aliases (Ganesh's .env naming)
    cloud_llm_api_key: str = ""
    cloud_llm_model:   str = ""

    # Orchestrator tuning
    improve_every_n_runs: int = 10

    # Cognee memory server (root main.py / memory.py) — this app calls it over
    # HTTP for /remember, /check-config, /query, and related graph operations.
    # See backend/app/cognee_client.py.
    cognee_api_url: str = "http://localhost:8010"
    cognee_call_timeout_seconds: float = 60.0
    # Keep failures loud; the backend no longer has a Postgres fallback.
    cognee_fallback_on_error: bool = False

    @property
    def effective_llm_api_key(self) -> str:
        return self.llm_api_key or self.cloud_llm_api_key

    @property
    def effective_llm_model(self) -> str:
        return self.llm_model or self.cloud_llm_model or "llama-3.3-70b-versatile"

    def resolve_llm(self) -> dict:
        """
        Resolve the selected provider into litellm call kwargs so the subagents
        work with any one of groq / gemini / aimlapi keys.

        Returns dict: {model, api_key, api_base|None}.
        """
        provider = (self.groundhog_llm_provider or "groq").strip().lower()
        if provider == "gemini":
            return {
                "model": "gemini/gemini-2.0-flash",
                "api_key": self.gemini_api_key,
                "api_base": None,
            }
        if provider == "aimlapi":
            # OpenAI-compatible endpoint.
            return {
                "model": "openai/gpt-4o-mini",
                "api_key": self.aimlapi_api_key,
                "api_base": "https://api.aimlapi.com/v1",
            }
        # default: groq
        return {
            "model": f"groq/{self.effective_llm_model}",
            "api_key": self.groq_api_key or self.effective_llm_api_key,
            "api_base": None,
        }


settings = Settings()
