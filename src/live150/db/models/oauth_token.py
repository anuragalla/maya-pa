import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from live150.db.base import Base


class OAuthToken(Base):
    __tablename__ = "oauth_token"

    oauth_token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    access_token_ct: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    access_token_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_ct: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    refresh_token_nonce: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", "provider_account_id", name="uq_oauth_token_user_provider"),
        Index("ix_oauth_token_user", "user_id", "provider"),
    )
