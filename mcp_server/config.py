"""Groundhog MCP Server — configuration."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # URL of the Groundhog app backend REST API (Cognee-backed, port 8000)
    groundhog_api_url: str = "http://localhost:8000"

    # Port this MCP server itself listens on
    mcp_port: int = 8002
    mcp_host: str = "0.0.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
