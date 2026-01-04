import os
import tempfile
from typing import List

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import structlog

from src.core.config import settings as _settings

# Initialize logger for this module
logger = structlog.get_logger(__name__)


class IngestionEngine:
    """
    Handles the loading and chunking of uploaded documents.
    """

    def __init__(self):
        # Log initialization parameters to help debug config issues
        self._chunk_size = _settings.CHUNK_SIZE
        self._chunk_overlap = _settings.CHUNK_OVERLAP

        logger.info(
            "ingestion_engine_initialized",
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
        )

        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size, chunk_overlap=self._chunk_overlap
        )

    def process_file(self, file_bytes: bytes, filename: str) -> List[Document]:
        """
        Saves bytes to a temp file, loads it, cleans up, and returns chunks.
        """
        # Bind file-specific context to all logs in this method
        log = logger.bind(filename=filename, file_size_bytes=len(file_bytes))

        ext = filename.split(".")[-1].lower()
        tmp_path = None

        try:
            log.info("processing_started", extension=ext)

            # 1. Write bytes to a temporary file
            # delete=False is mandatory for Windows to allow re-opening by loader
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
                # File is strictly closed here so the Loader can open it safely

            log.debug("temp_file_created", tmp_path=tmp_path)

            # 2. Load the document
            loader = self._get_loader(tmp_path, ext)
            log.debug("loader_selected", loader_type=type(loader).__name__)

            documents = loader.load()
            log.info("document_loaded", raw_doc_count=len(documents))

            # 3. Add metadata and split
            for doc in documents:
                doc.metadata["source"] = filename

            chunks = self._text_splitter.split_documents(documents)

            log.info(
                "splitting_complete",
                final_chunk_count=len(chunks),
                avg_chunk_size=(
                    sum(len(c.page_content) for c in chunks) / len(chunks)
                    if chunks
                    else 0
                ),
            )

            return chunks

        except Exception as e:
            # Capture the full stack trace for debugging
            log.error("processing_failed", error=str(e), exc_info=True)
            raise e

        finally:
            # 4. Cleanup
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    log.debug("cleanup_success", tmp_path=tmp_path)
                except PermissionError:
                    # Windows specific issue: Log it as a warning instead of passing silently
                    log.warn(
                        "cleanup_delayed",
                        reason="windows_permission_lock",
                        detail="File explicitly closed but OS holding lock. Temp file may persist.",
                        tmp_path=tmp_path,
                    )
                except Exception as e:
                    log.warn("cleanup_failed", error=str(e), tmp_path=tmp_path)

    @staticmethod
    def _get_loader(file_path: str, ext: str):
        if ext == "pdf":
            return PyPDFLoader(file_path)
        elif ext in ["docx", "doc"]:
            return Docx2txtLoader(file_path)
        elif ext in ["txt", "md"]:
            return TextLoader(file_path)
        else:
            # This error will be caught by the process_file try/except block
            raise ValueError(f"Unsupported file type for document loader: {ext}")
