"""documents table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-21 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("doc_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'file_upload'")),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("summary_detailed", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True, server_default=sa.text("'{}'")),
        sa.Column("structured", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("expiry_alert_date", sa.Date(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "doc_type IN ('lab_result','prescription','insurance','imaging','visit_note','vaccine','other')",
            name="ck_document_doc_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','uploaded','processing','ready','failed')",
            name="ck_document_status",
        ),
        sa.CheckConstraint(
            "source IN ('app_camera','file_upload','email_forward')",
            name="ck_document_source",
        ),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        "ix_document_user_uploaded",
        "document",
        ["user_id", sa.text("uploaded_at DESC")],
    )
    op.create_index("ix_document_user_type", "document", ["user_id", "doc_type"])


def downgrade() -> None:
    op.drop_index("ix_document_user_type", table_name="document")
    op.drop_index("ix_document_user_uploaded", table_name="document")
    op.drop_table("document")
