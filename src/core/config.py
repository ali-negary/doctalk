from enum import Enum

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class LLMProviderType(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    PERPLEXITY = "perplexity"
    MOCK = "mock"


class Settings(BaseSettings):
    # App Config
    APP_ENV: str = "development"
    APP_API_URL: str = "http://localhost:8000"
    LOG_LEVEL: str = "INFO"

    LLM_PROVIDER: LLMProviderType = Field(default=LLMProviderType.GEMINI)

    GOOGLE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OLLAMA_API_KEY: str | None = None
    PERPLEXITY_API_KEY: str | None = None

    # RAG Parameters
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Model Specifics
    GEMINI_MODEL: str = "gemini-pro"
    OPENAI_MODEL: str = "gpt-4-turbo"
    PERPLEXITY_MODEL: str = "llama-3.1-sonar-small-128k-online"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Pydantic Config to read .env.local file
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")


# Singleton instance
settings = Settings()


# Configure Logging
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
