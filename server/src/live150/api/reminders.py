"""Reminders CRUD endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.auth.middleware import AuthedUser, require_user
from live150.db.models.reminder import Reminder
from live150.db.models.user_profile import UserProfile
from live150.db.session import get_db
from live150.reminders.parser import parse_schedule, validate_schedule

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderCreate(BaseModel):
    title: str
    schedule_text: str
    prompt: str


class ReminderUpdate(BaseModel):
    title: str | None = None
    schedule_text: str | None = None
    status: str | None = None  # 'active' | 'paused'


@router.get("")
async def list_reminders(
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """List active reminders for the user."""
    stmt = (
        select(Reminder)
        .where(Reminder.user_id == user.user_id, Reminder.status.in_(["active", "paused"]))
        .order_by(Reminder.created_at.desc())
    )
    result = await db.execute(stmt)
    reminders = result.scalars().all()

    return {
        "reminders": [
            {
                "reminder_id": str(r.reminder_id),
                "title": r.title,
                "schedule_kind": r.schedule_kind,
                "schedule_expr": r.schedule_expr,
                "timezone": r.timezone,
                "status": r.status,
                "last_fired_at": r.last_fired_at.isoformat() if r.last_fired_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in reminders
        ]
    }


@router.post("")
async def create_reminder(
    body: ReminderCreate,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new reminder."""
    # Get user timezone
    profile_stmt = select(UserProfile).where(UserProfile.user_id == user.user_id)
    profile = (await db.execute(profile_stmt)).scalar_one_or_none()
    user_tz = profile.timezone if profile else "UTC"

    try:
        schedule = await parse_schedule(body.schedule_text, user_tz)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not validate_schedule(schedule):
        raise HTTPException(status_code=400, detail="Invalid schedule expression")

    reminder_id = uuid7()
    job_id = f"reminder:{reminder_id}"

    reminder = Reminder(
        reminder_id=reminder_id,
        user_id=user.user_id,
        created_by="user",
        title=body.title,
        prompt_template=body.prompt,
        schedule_kind=schedule.kind,
        schedule_expr=schedule.expr,
        timezone=schedule.timezone,
        job_id=job_id,
        status="active",
    )
    db.add(reminder)
    await db.commit()

    # TODO: Register with APScheduler via the scheduler service
    # For now, the job is persisted in DB but not yet scheduled

    return {
        "reminder_id": str(reminder_id),
        "schedule_kind": schedule.kind,
        "schedule_expr": schedule.expr,
        "timezone": schedule.timezone,
    }


@router.patch("/{reminder_id}")
async def update_reminder(
    reminder_id: uuid.UUID,
    body: ReminderUpdate,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a reminder (title, schedule, or status)."""
    stmt = select(Reminder).where(
        Reminder.reminder_id == reminder_id,
        Reminder.user_id == user.user_id,
    )
    reminder = (await db.execute(stmt)).scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if body.title is not None:
        reminder.title = body.title
    if body.status is not None:
        if body.status not in ("active", "paused"):
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'paused'")
        reminder.status = body.status
    if body.schedule_text is not None:
        profile_stmt = select(UserProfile).where(UserProfile.user_id == user.user_id)
        profile = (await db.execute(profile_stmt)).scalar_one_or_none()
        user_tz = profile.timezone if profile else "UTC"

        try:
            schedule = await parse_schedule(body.schedule_text, user_tz)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        reminder.schedule_kind = schedule.kind
        reminder.schedule_expr = schedule.expr
        reminder.timezone = schedule.timezone

    await db.commit()
    return {"status": "updated"}


@router.delete("/{reminder_id}")
async def delete_reminder(
    reminder_id: uuid.UUID,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a reminder."""
    stmt = select(Reminder).where(
        Reminder.reminder_id == reminder_id,
        Reminder.user_id == user.user_id,
    )
    reminder = (await db.execute(stmt)).scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    reminder.status = "cancelled"
    await db.commit()

    # TODO: Remove APScheduler job

    return {"status": "cancelled"}
