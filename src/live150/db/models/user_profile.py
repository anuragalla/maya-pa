from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from live150.db.base import Base


class UserProfile(Base):
    __tablename__ = "user_profile"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")
    locale: Mapped[str] = mapped_column(String, nullable=False, default="en-US")
    profile_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_user_profile_last_synced", "last_synced_at"),)
