import pytest


def test_health_check(client):
    """Verify the API is running."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_full_rag_flow(client, sample_file, mock_rag_env):
    """
    Test the full Upload -> RAG -> Chat flow.
    Note: 'mock_rag_env' fixture automatically handles the LLM/Ollama mocking.
    """
    session_id = "test-session-123"
    headers = {"X-Session-ID": session_id}

    # 1. Upload Document
    file_content, filename = sample_file
    files = {"files": (filename, file_content, "text/plain")}

    upload_response = client.post("/upload", headers=headers, files=files)

    # Assert Upload Success
    if upload_response.status_code != 200:
        pytest.fail(f"Upload failed: {upload_response.text}")

    assert upload_response.status_code == 200
    assert upload_response.json()["chunks_processed"] >= 1

    # 2. Chat with Document
    chat_payload = {"message": "What is the project name?"}
    chat_response = client.post("/chat", headers=headers, json=chat_payload)

    # Assert Chat Success
    if chat_response.status_code != 200:
        pytest.fail(f"Chat failed: {chat_response.text}")

    assert chat_response.status_code == 200
    data = chat_response.json()

    # Assert Correctness (Answer comes from our Mock in conftest)
    assert "answer" in data
    assert "mocked answer" in data["answer"]
