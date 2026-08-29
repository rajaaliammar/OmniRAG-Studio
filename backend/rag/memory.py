"""In-process conversational memory for multi-turn RAG chat."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from backend.config import get_settings


@dataclass(frozen=True)
class ChatTurn:
    """One utterance in a chat session."""

    role: str
    content: str


@dataclass
class ConversationMemory:
    """Thread-safe session store for recent chat turns.

    History is kept in process memory (not SQLite). Each session retains at
    most ``max_turns`` user/assistant pairs.
    """

    max_turns: int = 12
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _sessions: dict[str, list[ChatTurn]] = field(default_factory=dict)

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append a turn and trim the session to the configured window.

        Args:
            session_id: Conversation identifier.
            role: ``user`` or ``assistant``.
            content: Message text.
        """
        cleaned_id = (session_id or "").strip()
        cleaned_role = (role or "").strip().lower() or "user"
        cleaned = (content or "").strip()
        if not cleaned_id or not cleaned:
            return
        max_messages = max(self.max_turns, 1) * 2
        with self._lock:
            history = self._sessions.setdefault(cleaned_id, [])
            history.append(ChatTurn(role=cleaned_role, content=cleaned))
            if len(history) > max_messages:
                self._sessions[cleaned_id] = history[-max_messages:]

    def history(self, session_id: str) -> list[ChatTurn]:
        """Return a copy of the session transcript.

        Args:
            session_id: Conversation identifier.

        Returns:
            Ordered turns, possibly empty.
        """
        cleaned_id = (session_id or "").strip()
        with self._lock:
            return list(self._sessions.get(cleaned_id, []))

    def format_for_prompt(self, session_id: str) -> str:
        """Render history as plain text for the grounded user prompt.

        Args:
            session_id: Conversation identifier.

        Returns:
            A readable transcript, or an empty string.
        """
        lines: list[str] = []
        for turn in self.history(session_id):
            label = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{label}: {turn.content}")
        return "\n".join(lines)

    def clear(self, session_id: str) -> bool:
        """Drop one session.

        Args:
            session_id: Conversation identifier.

        Returns:
            True if a session was removed.
        """
        cleaned_id = (session_id or "").strip()
        with self._lock:
            return self._sessions.pop(cleaned_id, None) is not None

    def clear_all(self) -> None:
        """Drop every session (used by unit tests)."""
        with self._lock:
            self._sessions.clear()


_memory: ConversationMemory | None = None
_memory_lock = threading.Lock()


def get_memory() -> ConversationMemory:
    """Return the process-wide conversation memory singleton."""
    global _memory
    if _memory is not None:
        return _memory
    with _memory_lock:
        if _memory is None:
            settings = get_settings()
            _memory = ConversationMemory(max_turns=settings.chat_memory_max_turns)
        return _memory


def reset_memory() -> None:
    """Replace the singleton (used by unit tests)."""
    global _memory
    with _memory_lock:
        _memory = None
