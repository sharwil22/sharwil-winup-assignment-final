"""Session storage behind a small interface.

Sessions are immutable snapshots. Saving uses optimistic concurrency: the caller passes the
version it started from, and a save against a newer version fails. This is what stops two
overlapping requests (two tabs, a double click) from silently overwriting each other.
"""

import threading
import uuid
from dataclasses import dataclass, field, replace
from typing import Literal, Protocol

from app.domain.models import WishesState
from app.domain.reducer import Change


@dataclass(frozen=True)
class StoredMessage:
    role: Literal["user", "assistant"]
    content: str
    turn: int


@dataclass(frozen=True)
class Session:
    id: str
    state: WishesState
    messages: tuple[StoredMessage, ...] = ()
    change_log: tuple[Change, ...] = ()
    turn: int = 0  # number of user messages handled
    version: int = 0  # bumps on every save; clients send it back as expected_version

    @classmethod
    def new(cls, opening_message: str) -> "Session":
        return cls(
            id=uuid.uuid4().hex,
            state=WishesState.empty(),
            messages=(StoredMessage("assistant", opening_message, 0),),
        )


class SessionNotFound(Exception):
    pass


class VersionConflict(Exception):
    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"expected version {expected}, current version is {actual}")
        self.expected = expected
        self.actual = actual


class SessionRepository(Protocol):
    def add(self, session: Session) -> None: ...

    def get(self, session_id: str) -> Session: ...

    def save(self, session: Session, expected_version: int) -> Session: ...


@dataclass
class InMemorySessionRepository:
    _sessions: dict[str, Session] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.id] = session

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(session_id)
        return session

    def save(self, session: Session, expected_version: int) -> Session:
        """Store `session` as the next version, if nobody saved since `expected_version`."""
        with self._lock:
            current = self._sessions.get(session.id)
            if current is None:
                raise SessionNotFound(session.id)
            if current.version != expected_version:
                raise VersionConflict(expected_version, current.version)
            saved = replace(session, version=current.version + 1)
            self._sessions[session.id] = saved
            return saved
