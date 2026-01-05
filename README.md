# 🤖 DocTalk: Discuss Your Documents

**DocTalk** is a lightweight, secure Retrieval-Augmented Generation (RAG) system allowing users to chat with their internal documents (PDF, DOCX, TXT). It is designed with a "Microservices First" architecture, ready for Azure deployment.

---

## 🛠️ Tech Stack

### Core Components
* **Language:** Python 3.11
* **Dependency Management:** [Poetry](https://python-poetry.org/) (v1.8+)
* **Containerization:** Docker & Docker Compose

### Application Architecture
* **Frontend:** [Streamlit](https://streamlit.io/) (Interactive Chat UI)
* **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Async API, Validation, Swagger UI)
* **Orchestration:** [LangGraph](https://python.langchain.com/docs/langgraph) (Stateful Agentic Workflows)
* **Vector Store:** [FAISS](https://github.com/facebookresearch/faiss) (In-Memory / Volatile for security)
* **LLM Layer:** Configurable Provider (Ollama / OpenAI / Google Gemini)

### Observability & Quality
* **Logging:** `structlog` (Structured JSON logs for easy parsing)
* **Testing:** `pytest` + `pytest-cov` (Unit tests & Coverage reports)
* **Linting:** `ruff` & `black`

---

## 🚀 Quickstart

### Docker (Recommended)
This starts the full stack (UI + API) in isolated containers.

```bash
# 1. Create a .env file
cp .env.example .env

# 2. Build and Run
docker-compose up --build
```

- Frontend: http://localhost:9091
- API Docs: http://localhost:9090/docs
