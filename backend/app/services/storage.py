"""Persistence helpers for tarot sessions."""

from __future__ import annotations


class SessionStorage:
    """Abstracts DB operations related to tarot sessions.

    TODO:
        - implement CRUD via SQLAlchemy models
        - enforce tenant-level access control (even if single user)
        - expose methods for logs/observability traces
    """

    def __init__(self) -> None:
        raise NotImplementedError("SessionStorage wiring pending DB schema")

    async def upsert_session(self, data) -> None:  # type: ignore[override]
        """TODO: persist or update a tarot session row."""

        raise NotImplementedError

    async def get_session(self, session_id: str):  # type: ignore[override]
        """TODO: fetch session with cards, synthesis, safety data."""

        raise NotImplementedError
