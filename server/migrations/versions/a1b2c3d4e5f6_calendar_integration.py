"""calendar integration tables

Revision ID: a1b2c3d4e5f6
Revises: 7a37239fb318
Create Date: 2026-04-18 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7a37239fb318"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_calendar — one row per user + provider
    op.create_table(
        "user_calendar",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("calendar_id", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("preferred", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "provider"),
    )
    op.create_index(
        "ix_user_calendar_preferred",
        "user_calendar",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("preferred"),
    )

    # calendar_snapshot — compact 7-day view
    op.create_table(
        "calendar_snapshot",
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("calendar_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source IN ('user','live150')", name="ck_calendar_snapshot_source"),
        sa.UniqueConstraint("user_id", "provider", "event_id", name="uq_snapshot_user_provider_event"),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index("ix_calendar_snapshot_user_start", "calendar_snapshot", ["user_id", "start_at"])

    # connect_state — short-lived signed state for in-chat connect links
    op.create_table(
        "connect_state",
        sa.Column("state_token", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("origin_session", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("state_token"),
    )
    op.create_index("ix_connect_state_user", "connect_state", ["user_id", "expires_at"])

    # reminder_calendar_event — junction: reminder ↔ provider event
    op.create_table(
        "reminder_calendar_event",
        sa.Column("reminder_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_event_id", sa.String(), nullable=False),
        sa.Column("calendar_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reminder_id"], ["reminder.reminder_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("reminder_id", "provider"),
    )


def downgrade() -> None:
    op.drop_table("reminder_calendar_event")
    op.drop_index("ix_connect_state_user", table_name="connect_state")
    op.drop_table("connect_state")
    op.drop_index("ix_calendar_snapshot_user_start", table_name="calendar_snapshot")
    op.drop_table("calendar_snapshot")
    op.drop_index("ix_user_calendar_preferred", table_name="user_calendar")
    op.drop_table("user_calendar")
