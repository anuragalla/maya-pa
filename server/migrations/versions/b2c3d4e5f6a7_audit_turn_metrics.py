"""audit turn metrics columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-19 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("cached_tokens", sa.Integer(), nullable=True))
    op.add_column("audit_log", sa.Column("thoughts_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_log", "thoughts_tokens")
    op.drop_column("audit_log", "cached_tokens")
