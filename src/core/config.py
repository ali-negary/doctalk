from enum import Enum
import logging

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

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")


# Singleton instance
settings = Settings()


# Logging
def configure_logging():
    # Processors that are common to both JSON and Console logging
    processors = [
        structlog.contextvars.merge_contextvars,  # Merge context vars (e.g. session_id bound in API)
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        structlog.processors.JSONRenderer(),  # Use JSON rendering for production/structured logs
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.LOG_LEVEL.upper())
        ),
        cache_logger_on_first_use=True,
    )


configure_logging()
