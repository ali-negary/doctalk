from contextlib import asynccontextmanager
from typing import List, Annotated

from fastapi import FastAPI, UploadFile, File, HTTPException, status, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.core.rag import RAGEngine as _RAGEngine
from src.core.session import SessionManager as _SessionManager
from src.api.schemas import (
    ChatRequest as _ChatRequest,
    ChatResponse as _ChatResponse,
    UploadResponse as _UploadResponse,
)


# Global Session Manager instance
session_manager: _SessionManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifecycle of the application.
    Initializes the Session Manager on startup.
    """
    global session_manager
    print("Startup: Initializing Session Manager...")
    try:
        session_manager = _SessionManager()
        print("Startup: Session Manager Ready.")
    except Exception as e:
        print(f"Startup Failed: {e}")
        # In production, crash strictly if critical dependencies fail
        # raise e

    yield

    # Cleanup
    print("Shutdown: Cleaning up resources...")
    session_manager = None


app = FastAPI(
    title="DocTalk API",
    description="DocTalk: A lightweight RAG Interface for Document Discussion",
    version="0.1.0",
    lifespan=lifespan,
)

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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System is not initialized",
        )

    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Session-ID header is required",
        )

    return session_manager.get_engine(x_session_id)


# --- Endpoints ---


@app.get("/health", tags=["System"])
async def health_check():
    """Kubernetes/Azure readiness probe."""
    is_ready = session_manager is not None
    return {"status": "ok" if is_ready else "initializing", "service": "doctalk-api"}


@app.post("/upload", response_model=_UploadResponse, tags=["Documents"])
async def upload_documents(
    files: List[UploadFile] = File(...),
    rag_engine: _RAGEngine = Depends(get_rag_engine),
):
    """
    Ingests files (PDF, DOCX, TXT) into the user's specific session.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Read files into memory
    # Note: large file streaming is skipped for assignment scope,
    # but we acknowledge it as a production improvement.
    file_data = []
    filenames = []

    try:
        for file in files:
            content = await file.read()
            file_data.append((content, file.filename))
            filenames.append(file.filename)

        # Call the ASYNC ingest method
        # This now awaits the thread pool execution, keeping the API responsive
        count = await rag_engine.ingest_files(file_data)

        return _UploadResponse(
            message="Ingestion successful",
            chunks_processed=count,
            files_processed=filenames,
        )

    except Exception as e:
        # Log the error with structured logging in production
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.post("/chat", response_model=_ChatResponse, tags=["Chat"])
async def chat(request: _ChatRequest, rag_engine: _RAGEngine = Depends(get_rag_engine)):
    """
    Asks a question to the user's specific RAG engine.
    """
    try:
        # Call the ASYNC ask method
        response = await rag_engine.ask(request.message)
        return response
    except Exception as e:
        print(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


# Safe entry point for debugging
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
