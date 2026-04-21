import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from live150.db.base import Base


class Document(Base):
    __tablename__ = "document"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="file_upload")
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_detailed: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True, server_default="{}")
    structured: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    expiry_alert_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('lab_result','prescription','insurance','imaging','visit_note','vaccine','other')",
            name="ck_document_doc_type",
        ),
        CheckConstraint(
            "status IN ('pending','uploaded','processing','ready','failed','cancelled')",
            name="ck_document_status",
        ),
        CheckConstraint(
            "source IN ('app_camera','file_upload','email_forward')",
            name="ck_document_source",
        ),
        Index("ix_document_user_uploaded", "user_id", uploaded_at.desc()),
        Index("ix_document_user_type", "user_id", "doc_type"),
    )
