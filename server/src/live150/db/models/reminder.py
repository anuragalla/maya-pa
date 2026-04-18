import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from live150.db.base import Base


class Reminder(Base):
    __tablename__ = "reminder"

    reminder_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)  # user | agent
    title: Mapped[str] = mapped_column(String, nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_kind: Mapped[str] = mapped_column(String, nullable=False)  # once | cron | interval
    schedule_expr: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False)
    job_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("created_by IN ('user','agent')", name="ck_reminder_created_by"),
        CheckConstraint("schedule_kind IN ('once','cron','interval')", name="ck_reminder_schedule_kind"),
        CheckConstraint("status IN ('active','paused','cancelled')", name="ck_reminder_status"),
        Index("ix_reminder_user_status", "user_id", "status"),
    )
