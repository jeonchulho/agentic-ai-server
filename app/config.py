from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str
    openai_model: str = "gpt-4o"
    agent_max_iterations: int = 10
    # Comma-separated list of allowed CORS origins, e.g. "https://example.com,https://app.example.com"
    # Use "*" only for local development.
    cors_allow_origins: str = "*"

    @field_validator("openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("OPENAI_API_KEY must be set in the environment or .env file.")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()
