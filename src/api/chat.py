import time
from contextlib import asynccontextmanager
from typing import List, Annotated

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    status,
    Header,
    Depends,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
import structlog

from src.core.config import settings
from src.core.rag import RAGEngine as _RAGEngine
from src.core.session import SessionManager as _SessionManager
from src.api.schemas import (
    ChatRequest as _ChatRequest,
    ChatResponse as _ChatResponse,
    UploadResponse as _UploadResponse,
)

# Initialize global logger for the module
logger = structlog.get_logger(__name__)

# Global Session Manager instance
session_manager: _SessionManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifecycle of the application.
    Initializes the Session Manager on startup.
    """
    global session_manager
    logger.info("startup_initializing", component="session_manager")
    logger.info(
        "startup_configuration",
        app_env=settings.APP_ENV,
        llm_provider=settings.LLM_PROVIDER,
        api_url=settings.APP_API_URL,
    )
    try:
        session_manager = _SessionManager()
        logger.info("startup_complete", component="session_manager", status="ready")
    except Exception as e:
        logger.critical("startup_failed", error=str(e), exc_info=True)
        # In production, crash strictly if critical dependencies fail
        # raise e

    yield

    # Cleanup
    logger.info("shutdown_started")
    session_manager = None
    logger.info("shutdown_complete")


app = FastAPI(
    title="DocTalk API",
    description="DocTalk: A lightweight RAG Interface for Document Discussion",
    version="0.1.0",
    lifespan=lifespan,
)


# Observability Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    # 1. Start Timer
    start_time = time.perf_counter()

    # 2. Process Request
    response = await call_next(request)

    # 3. Calculate Latency
    process_time = time.perf_counter() - start_time

    # 4. Log Metrics (Latency & Status)
    logger.info(
        "api_request_metrics",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        latency_seconds=round(process_time, 4),
        client_ip=request.client.host if request.client else "unknown",
    )

    # 5. Add Header (Optional visibility for the frontend)
    response.headers["X-Process-Time"] = str(process_time)

    return response


# CORS: Allow the UI (Streamlit) to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_rag_engine(
    x_session_id: Annotated[str, Header(description="Unique ID for the user session")],
) -> _RAGEngine:
    """
    Dependency Injection:
    Extracts the Session ID from headers and retrieves/creates the specific RAG Engine.
    """
    if not session_manager:
        logger.error("service_unavailable", reason="session_manager_not_initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System is not initialized",
        )

    if not x_session_id:
        logger.warn("bad_request", reason="missing_session_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Session-ID header is required",
        )

    # Note: We don't log every 'get_engine' call to avoid noise,
    # but the binding in the endpoints will capture the session_id.
    return session_manager.get_engine(x_session_id)


# --- Endpoints ---


@app.get("/health", tags=["System"])
async def health_check():
    """Kubernetes/Azure readiness probe."""
    is_ready = session_manager is not None

    logger.debug("health_check", status="ok" if is_ready else "initializing")

    return {"status": "ok" if is_ready else "initializing", "service": "doctalk-api"}


@app.post("/upload", response_model=_UploadResponse, tags=["Documents"])
async def upload_documents(
    files: List[UploadFile] = File(...),
    rag_engine: _RAGEngine = Depends(get_rag_engine),
    x_session_id: str = Header(...),  # Capture explicitly for logging context
):
    """
    Ingests files (PDF, DOCX, TXT) into the user's specific session.
    """
    # Bind session_id to logger so all logs in this function have it
    log = logger.bind(session_id=x_session_id, handler="upload_documents")

    if not files:
        log.warn("upload_failed", reason="no_files_provided")
        raise HTTPException(status_code=400, detail="No files provided")

    file_data = []
    filenames = []

    try:
        log.info("upload_started", file_count=len(files))

        for file in files:
            content = await file.read()
            file_data.append((content, file.filename))
            filenames.append(file.filename)

        # Call the ASYNC ingest method
        count = await rag_engine.ingest_files(file_data)

        log.info(
            "ingestion_complete", chunks_processed=count, files_processed=filenames
        )

        return _UploadResponse(
            message="Ingestion successful",
            chunks_processed=count,
            files_processed=filenames,
        )

    except Exception as e:
        log.error("upload_error", error=str(e), filenames=filenames, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.post("/chat", response_model=_ChatResponse, tags=["Chat"])
async def chat(
    request: _ChatRequest,
    rag_engine: _RAGEngine = Depends(get_rag_engine),
    x_session_id: str = Header(...),  # Capture explicitly for logging context
):
    """
    Asks a question to the user's specific RAG engine.
    """
    # Bind session_id to logger so all logs in this function have it
    log = logger.bind(session_id=x_session_id, handler="chat")

    try:
        log.info("chat_request_received", question_length=len(request.message))

        # Call the ASYNC ask method
        response = await rag_engine.ask(request.message)

        log.info(
            "chat_response_generated", citation_count=len(response.get("citations", []))
        )
        return response

    except Exception as e:
        log.error("chat_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


# Safe entry point for debugging
if __name__ == "__main__":
    import uvicorn

    # Structlog will already be configured by the import of settings/config logic
    uvicorn.run(app, host="0.0.0.0", port=8000)
