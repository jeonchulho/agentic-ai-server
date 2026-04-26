from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM provider: openai | ollama | claude | gemini
    llm_provider: str = "openai"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Ollama (OpenAI-compatible local server)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.2"

    # Anthropic (Claude)
    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"

    # Google (Gemini)
    google_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    agent_max_iterations: int = 10
    # Comma-separated list of allowed CORS origins, e.g. "https://example.com,https://app.example.com"
    # Use "*" only for local development.
    cors_allow_origins: str = "*"

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> "Settings":
        provider = self.llm_provider.lower()
        if provider == "openai" and not self.openai_api_key.strip():
            raise ValueError(
                "OPENAI_API_KEY must be set when LLM_PROVIDER=openai."
            )
        if provider in ("claude", "anthropic") and not self.anthropic_api_key.strip():
            raise ValueError(
                "ANTHROPIC_API_KEY must be set when LLM_PROVIDER=claude."
            )
        if provider in ("gemini", "google") and not self.google_api_key.strip():
            raise ValueError(
                "GOOGLE_API_KEY must be set when LLM_PROVIDER=gemini."
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()
