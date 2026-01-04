from typing import Protocol, List, Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings
import structlog

from src.core.config import settings as _settings, LLMProviderType as _LLMProviderType

# Initialize Logger
logger = structlog.get_logger(__name__)


class ILLMProvider(Protocol):
    """Interface for any LLM Provider (Gemini, OpenAI, etc)."""

    def get_chat_model(self) -> BaseChatModel: ...

    def get_embeddings(self) -> Embeddings: ...


# --- MOCK CLASSES (For Testing & CI) ---


class MockChatModel(BaseChatModel):
    """A fake Chat Model that returns deterministic answers without hitting an API."""

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Log that we are in simulation mode
        logger.info("mock_generation_triggered", message_count=len(messages))

        # We return a fixed answer to prove the pipeline works
        response_text = "This is a MOCKED response. The pipeline is working correctly."

        # Wrap it in the LangChain structure
        message = AIMessage(content=response_text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "mock-chat"


class MockEmbeddings(Embeddings):
    """Fake embeddings to bypass API limits and costs."""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        logger.debug("mock_embedding_docs", count=len(texts))
        # Return a fixed vector of size 768 (standard size) for every doc
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        logger.debug("mock_embedding_query", text_length=len(text))
        return [0.1] * 768


class MockProvider(ILLMProvider):
    """The Provider Factory that dispenses our fakes."""

    def get_chat_model(self) -> BaseChatModel:
        return MockChatModel()

    def get_embeddings(self) -> Embeddings:
        return MockEmbeddings()


# --- REAL PROVIDERS ---


class GeminiProvider(ILLMProvider):
    def get_chat_model(self) -> BaseChatModel:
        if not _settings.GEMINI_API_KEY:
            logger.error(
                "provider_config_error", provider="gemini", missing="GEMINI_API_KEY"
            )
            raise ValueError("GEMINI_API_KEY is missing in .env")

        logger.debug(
            "initializing_llm", provider="gemini", model=_settings.GEMINI_MODEL
        )
        return ChatGoogleGenerativeAI(
            model=_settings.GEMINI_MODEL,
            google_api_key=_settings.GEMINI_API_KEY,
            temperature=0.2,
            convert_system_message_to_human=True,
        )

    def get_embeddings(self) -> Embeddings:
        if not _settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing in .env")
        return GoogleGenerativeAIEmbeddings(
            model=_settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=_settings.GEMINI_API_KEY,
        )


class OpenAIProvider(ILLMProvider):  # NOT TESTED
    def get_chat_model(self) -> BaseChatModel:
        if not _settings.OPENAI_API_KEY:
            logger.error(
                "provider_config_error", provider="openai", missing="OPENAI_API_KEY"
            )
            raise ValueError("OPENAI_API_KEY is missing in .env")

        logger.debug(
            "initializing_llm", provider="openai", model=_settings.OPENAI_MODEL
        )
        return ChatOpenAI(
            model=_settings.OPENAI_MODEL,
            api_key=_settings.OPENAI_API_KEY,
            temperature=0,
        )

    def get_embeddings(self) -> Embeddings:
        if not _settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is missing in .env")
        return OpenAIEmbeddings(api_key=_settings.OPENAI_API_KEY)


class OllamaProvider(ILLMProvider):
    def get_chat_model(self) -> BaseChatModel:
        logger.debug(
            "initializing_llm",
            provider="ollama",
            model=_settings.OLLAMA_MODEL,
            url=_settings.OLLAMA_BASE_URL,
        )
        return ChatOllama(
            base_url=_settings.OLLAMA_BASE_URL,
            model=_settings.OLLAMA_MODEL,
            temperature=0,
        )

    def get_embeddings(self) -> Embeddings:
        return OllamaEmbeddings(
            base_url=_settings.OLLAMA_BASE_URL,
            model=_settings.OLLAMA_MODEL,
        )


class PerplexityProvider(ILLMProvider):  # NOT TESTED
    def get_chat_model(self) -> BaseChatModel:
        if not _settings.PERPLEXITY_API_KEY:
            logger.error(
                "provider_config_error",
                provider="perplexity",
                missing="PERPLEXITY_API_KEY",
            )
            raise ValueError("PERPLEXITY_API_KEY is missing")

        logger.debug(
            "initializing_llm", provider="perplexity", model=_settings.PERPLEXITY_MODEL
        )
        return ChatOpenAI(
            model=_settings.PERPLEXITY_MODEL,
            api_key=_settings.PERPLEXITY_API_KEY,
            base_url="https://api.perplexity.ai",
            temperature=0,
        )

    def get_embeddings(self) -> Embeddings:
        # Fallback: Perplexity doesn't do embeddings.
        if _settings.OPENAI_API_KEY:
            return OpenAIEmbeddings(api_key=_settings.OPENAI_API_KEY)
        else:
            logger.error(
                "provider_config_error",
                provider="perplexity",
                detail="requires_openai_for_embeddings",
            )
            raise ValueError(
                "Perplexity Provider requires OPENAI_API_KEY for embeddings (Perplexity has no embedding API)."
            )


class LLMFactory:
    """Factory to return the configured provider."""

    @staticmethod
    def get_provider() -> ILLMProvider:
        provider = _settings.LLM_PROVIDER

        logger.info("llm_provider_selected", provider=provider)

        if provider == _LLMProviderType.GEMINI:
            return GeminiProvider()
        elif provider == _LLMProviderType.OLLAMA:
            return OllamaProvider()
        elif provider == _LLMProviderType.MOCK:
            return MockProvider()
        # elif provider == _LLMProviderType.OPENAI:
        #     return OpenAIProvider()
        # elif provider == _LLMProviderType.PERPLEXITY:
        #     return PerplexityProvider()
        else:
            logger.critical("provider_not_implemented", provider=provider)
            raise NotImplementedError(f"Provider {provider} not implemented")
