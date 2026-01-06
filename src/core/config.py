from enum import Enum
import logging
from typing import Optional

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

from src.core.secrets_manager import AzureSecretManager as _ASM


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

    # Azure Integration (Triggers Key Vault loading if set)
    AZURE_KEYVAULT_URL: Optional[str] = None

    # LLM Configuration
    LLM_PROVIDER: LLMProviderType = Field(default=LLMProviderType.GEMINI)

    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OLLAMA_API_KEY: str | None = None
    PERPLEXITY_API_KEY: str | None = None

    # RAG Parameters
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Model Specifics
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"
    OPENAI_MODEL: str = "gpt-4-turbo"
    PERPLEXITY_MODEL: str = "llama-3.1-sonar-small-128k-online"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_azure_secrets()

    def _load_azure_secrets(self):
        """
        If AZURE_KEYVAULT_URL is set, hydrate secrets from Azure.
        """
        if self.AZURE_KEYVAULT_URL:
            # Connect to Azure
            manager = _ASM(self.AZURE_KEYVAULT_URL, self.APP_ENV)

            # Map Azure Secret Names -> Pydantic Fields
            secret_map = {
                "GEMINI-API-KEY": "GEMINI_API_KEY",
                "OPENAI-API-KEY": "OPENAI_API_KEY",
                "PERPLEXITY-API-KEY": "PERPLEXITY_API_KEY",
            }

            # Inject values
            manager.load_secrets_into_settings(self, secret_map)


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
