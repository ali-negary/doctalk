from typing import Dict

from src.core.rag import RAGEngine as _RAGEngine


class SessionManager:
    """
    Manages isolated RAG Engine instances for different users/sessions.
    In a production cluster (Kubernetes), this would be replaced by Redis
    to share state across pods.
    """

    def __init__(self):
        # Maps session_id -> RAGEngine
        self._sessions: Dict[str, _RAGEngine] = {}

    def get_engine(self, session_id: str) -> _RAGEngine:
        """
        Returns the RAG engine for a specific session.
        Creates a new one if it doesn't exist.
        """
        if session_id not in self._sessions:
            # In a real app, you might load persistent state from a DB here
            print(f"Creating new RAGEngine for session: {session_id}")
            self._sessions[session_id] = _RAGEngine()

        return self._sessions[session_id]

    def clear_session(self, session_id: str):
        """Removes a session to free up memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
