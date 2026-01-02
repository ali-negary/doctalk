import os
import tempfile
from typing import List

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from src.core.config import settings as _settings


class IngestionEngine:
    """
    Handles the loading and chunking of uploaded documents.
    """

    def __init__(self):
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=_settings.CHUNK_SIZE, chunk_overlap=_settings.CHUNK_OVERLAP
        )

    def process_file(self, file_bytes: bytes, filename: str) -> List[Document]:
        """
        Saves bytes to a temp file, loads it, cleans up, and returns chunks.
        """
        ext = filename.split(".")[-1].lower()
        tmp_path = None

        try:
            # 1. Write bytes to a temporary file
            # delete=False is mandatory for Windows to allow re-opening by loader
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
                # File is strictly closed here so the Loader can open it safely

            # 2. Load the document
            loader = self._get_loader(tmp_path, ext)
            documents = loader.load()

            # 3. Add metadata and split
            for doc in documents:
                doc.metadata["source"] = filename

            return self._text_splitter.split_documents(documents)

        finally:
            # 4. Cleanup
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except PermissionError:
                    # Sometimes Windows holds on a bit too long; non-fatal
                    # Needs to be tested thoroughly
                    pass

    @staticmethod
    def _get_loader(file_path: str, ext: str):
        if ext == "pdf":
            return PyPDFLoader(file_path)
        elif ext in ["docx", "doc"]:
            return Docx2txtLoader(file_path)
        elif ext in ["txt", "md"]:
            return TextLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
