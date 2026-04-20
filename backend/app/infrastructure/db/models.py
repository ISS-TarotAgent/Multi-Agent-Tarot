from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Text, UniqueConstraint
from sqlalchemy import Uuid as SqlAlchemyUuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class SessionModel(Base):
    """Represents a single tarot reflection session."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(SqlAlchemyUuid(as_uuid=False), primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    spread_type: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["SessionMessageModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    reading: Mapped["ReadingModel | None"] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    trace_events: Mapped[list["TraceEventModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class SessionMessageModel(Base):
    """Stores a time-ordered message within a session."""

    __tablename__ = "session_messages"

    id: Mapped[str] = mapped_column(SqlAlchemyUuid(as_uuid=False), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        SqlAlchemyUuid(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_type: Mapped[str] = mapped_column(Text, nullable=False)
    sender_role: Mapped[str] = mapped_column(Text, nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[SessionModel] = relationship(back_populates="messages")


class ReadingModel(Base):
    """Stores the persisted reading aggregate for a session."""

    __tablename__ = "readings"

    id: Mapped[str] = mapped_column(SqlAlchemyUuid(as_uuid=False), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        SqlAlchemyUuid(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    normalized_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_advice: Mapped[str | None] = mapped_column(Text, nullable=True)
    reflection_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(Text, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[SessionModel] = relationship(back_populates="reading")
    cards: Mapped[list["ReadingCardModel"]] = relationship(
        back_populates="reading",
        cascade="all, delete-orphan",
        order_by="ReadingCardModel.sort_order",
    )
    safety_review: Mapped["SafetyReviewModel | None"] = relationship(
        back_populates="reading",
        cascade="all, delete-orphan",
        uselist=False,
    )
    trace_events: Mapped[list["TraceEventModel"]] = relationship(back_populates="reading")


class ReadingCardModel(Base):
    """Stores one card drawn for a reading."""

    __tablename__ = "reading_cards"
    __table_args__ = (UniqueConstraint("reading_id", "position"),)

    id: Mapped[str] = mapped_column(SqlAlchemyUuid(as_uuid=False), primary_key=True)
    reading_id: Mapped[str] = mapped_column(
        SqlAlchemyUuid(as_uuid=False),
        ForeignKey("readings.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    card_code: Mapped[str] = mapped_column(Text, nullable=False)
    card_name: Mapped[str] = mapped_column(Text, nullable=False)
    orientation: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    reading: Mapped[ReadingModel] = relationship(back_populates="cards")


class SafetyReviewModel(Base):
    """Stores the final safety decision for a reading."""

    __tablename__ = "safety_reviews"

    id: Mapped[str] = mapped_column(SqlAlchemyUuid(as_uuid=False), primary_key=True)
    reading_id: Mapped[str] = mapped_column(
        SqlAlchemyUuid(as_uuid=False),
        ForeignKey("readings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    risk_level: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    safe_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    reading: Mapped[ReadingModel] = relationship(back_populates="safety_review")


class TraceEventModel(Base):
    """Stores a structured workflow event."""

    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(SqlAlchemyUuid(as_uuid=False), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        SqlAlchemyUuid(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reading_id: Mapped[str | None] = mapped_column(
        SqlAlchemyUuid(as_uuid=False),
        ForeignKey("readings.id", ondelete="CASCADE"),
        nullable=True,
    )
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    event_status: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[SessionModel] = relationship(back_populates="trace_events")
    reading: Mapped[ReadingModel | None] = relationship(back_populates="trace_events")
