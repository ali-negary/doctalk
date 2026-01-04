from typing import Dict

import structlog

from src.core.rag import RAGEngine as _RAGEngine

# Initialize logger for this module
logger = structlog.get_logger(__name__)


class SessionManager:
    """
    Manages isolated RAG Engine instances for different users/sessions.
    In a production cluster (Kubernetes), this would be replaced by Redis
    to share state across pods.
    """

    def __init__(self):
        # Maps session_id -> RAGEngine
        self._sessions: Dict[str, _RAGEngine] = {}
        logger.info("session_manager_initialized")

    def get_engine(self, session_id: str) -> _RAGEngine:
        """
        Returns the RAG engine for a specific session.
        Creates a new one if it doesn't exist.
        """
        if session_id not in self._sessions:
            # Log creation event with context
            logger.info("creating_new_rag_engine", session_id=session_id)
            self._sessions[session_id] = _RAGEngine()
        else:
            # Use DEBUG level for cache hits to avoid log noise in production
            logger.debug("retrieving_cached_engine", session_id=session_id)

        return self._sessions[session_id]

    def clear_session(self, session_id: str):
        """Removes a session to free up memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("session_cleared", session_id=session_id)
        else:
            logger.warn(
                "session_clear_failed", reason="not_found", session_id=session_id
            )
