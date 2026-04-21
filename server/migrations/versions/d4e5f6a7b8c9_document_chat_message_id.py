"""document.chat_message_id + cancelled status

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-21 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document",
        sa.Column("chat_message_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_document_chat_message_id",
        "document",
        ["chat_message_id"],
    )

    op.drop_constraint("ck_document_status", "document", type_="check")
    op.create_check_constraint(
        "ck_document_status",
        "document",
        "status IN ('pending','uploaded','processing','ready','failed','cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_document_status", "document", type_="check")
    op.create_check_constraint(
        "ck_document_status",
        "document",
        "status IN ('pending','uploaded','processing','ready','failed')",
    )

    op.drop_index("ix_document_chat_message_id", table_name="document")
    op.drop_column("document", "chat_message_id")
