from pydantic import BaseModel, Field
from typing import List


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's question to the AI")


class Citation(BaseModel):
    source: str = Field(..., description="Filename of the source document")
    text: str = Field(..., description="Relevant snippet from the document")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="The AI generated answer")
    citations: List[Citation] = Field(
        default_factory=list, description="List of sources used"
    )


class UploadResponse(BaseModel):
    message: str
    chunks_processed: int
    files_processed: List[str]
