"""Application service: the use cases the API exposes, independent of HTTP."""

import logging
from dataclasses import replace
from typing import Any

from app.domain import reducer
from app.domain.models import FieldPath, WishesState
from app.domain.updates import ProposedUpdate, UpdateKind, UpdateSource
from app.domain.validation import validate_updates
from app.llm.contracts import HistoryMessage
from app.llm.interface import LLMProvider
from app.services.interview import TurnOutcome, handle_turn, opening_message
from app.services.session_store import (
    Session,
    SessionRepository,
    StoredMessage,
    VersionConflict,
)

logger = logging.getLogger(__name__)


class EditRejected(Exception):
    """A direct field edit failed validation."""


class SessionService:
    def __init__(self, repository: SessionRepository, provider: LLMProvider) -> None:
        self._repository = repository
        self._provider = provider

    def start(self) -> Session:
        session = Session.new(opening_message(WishesState.empty()))
        self._repository.add(session)
        logger.info("session_started id=%s", session.id)
        return session

    def get(self, session_id: str) -> Session:
        return self._repository.get(session_id)

    def send_message(
        self, session_id: str, content: str, expected_version: int
    ) -> tuple[Session, TurnOutcome]:
        session = self._repository.get(session_id)
        # Fail fast before paying for a model call; save() checks again atomically.
        _check_version(session, expected_version)

        turn = session.turn + 1
        history = [HistoryMessage(m.role, m.content) for m in session.messages]
        outcome = handle_turn(self._provider, session.state, history, content, turn)

        updated = replace(
            session,
            state=outcome.state,
            turn=turn,
            messages=(
                *session.messages,
                StoredMessage("user", content, turn),
                StoredMessage("assistant", outcome.reply, turn),
            ),
            change_log=(*session.change_log, *outcome.changes),
        )
        saved = self._repository.save(updated, expected_version)
        logger.info(
            "turn id=%s turn=%s changes=%s conflicts=%s rejected=%s warnings=%s",
            session_id,
            turn,
            len(outcome.changes),
            len(outcome.conflicts),
            len(outcome.rejected),
            ",".join(outcome.warnings) or "-",
        )
        return saved, outcome

    def edit_field(
        self, session_id: str, path: FieldPath, value: Any, expected_version: int
    ) -> Session:
        """Direct edit from the UI: same validation and reducer as chat, as a correction."""
        session = self._repository.get(session_id)
        _check_version(session, expected_version)

        update = ProposedUpdate(
            path=path, value=value, kind=UpdateKind.CORRECTION, source=UpdateSource.UI_EDIT
        )
        validation = validate_updates([update], session.state, user_message="")
        if validation.rejected:
            raise EditRejected(validation.rejected[0].reason)

        result = reducer.apply(session.state, list(validation.accepted), session.turn)
        updated = replace(
            session,
            state=result.state,
            change_log=(*session.change_log, *result.changes),
        )
        logger.info("field_edited id=%s path=%s", session_id, path)
        return self._repository.save(updated, expected_version)


def _check_version(session: Session, expected_version: int) -> None:
    if session.version != expected_version:
        raise VersionConflict(expected_version, session.version)
