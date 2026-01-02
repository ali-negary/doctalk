# tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from langchain_core.embeddings import Embeddings

from src.api.chat import app


# --- Helper Classes ---
class FakeEmbeddings(Embeddings):
    """Fake embeddings to avoid FAISS errors and API costs."""

    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 768


# --- Fixtures ---


@pytest.fixture
def client():
    """Returns a FastAPI TestClient."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_file():
    """Returns a dummy text file for upload tests."""
    content = b"This is a test document about Project Phoenix-99."
    return content, "test_doc.txt"


@pytest.fixture
def mock_rag_env():
    """
    Auto-patches the LLMFactory to use Mocks.
    Yields the mock_provider so you can customize return values if needed in specific tests.
    """
    # Patch the Factory globally. This catches ALL provider types (Ollama, Gemini, etc.)
    with patch("src.core.llm_factory.LLMFactory.get_provider") as mock_get_provider:
        # 1. Create the Mock Provider Object
        mock_provider_instance = MagicMock()
        mock_get_provider.return_value = mock_provider_instance

        # 2. Mock the Chat Model (Async Runnable)
        async def fake_llm_func(input_arg):
            # This is the default answer for all tests
            return AIMessage(
                content="This is a mocked answer based on Project Phoenix-99."
            )

        # Use RunnableLambda so LangChain's pipe '|' operator works
        mock_llm = RunnableLambda(fake_llm_func)
        mock_provider_instance.get_chat_model.return_value = mock_llm

        # 3. Mock the Embeddings (Fixes FAISS)
        mock_provider_instance.get_embeddings.return_value = FakeEmbeddings()

        yield mock_provider_instance
