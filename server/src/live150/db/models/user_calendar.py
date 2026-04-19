import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from live150.db.base import Base


class UserCalendar(Base):
    __tablename__ = "user_calendar"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, primary_key=True)  # google | microsoft | apple
    calendar_id: Mapped[str | None] = mapped_column(String, nullable=True)  # Live150 sub-calendar id
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String, nullable=True)  # ok | auth_failed | quota_exceeded | other
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_user_calendar_preferred", "user_id", unique=True, postgresql_where="preferred"),
    )
