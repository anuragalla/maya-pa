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
from live150.reminders.jobs import fire_reminder, make_trigger
from live150.reminders.parser import parse_schedule, validate_schedule
from live150.reminders.scheduler import get_scheduler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reminders"])


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

    trigger = make_trigger(schedule.kind, schedule.expr, schedule.timezone)
    get_scheduler().add_job(
        fire_reminder,
        trigger=trigger,
        args=[str(reminder_id)],
        id=job_id,
        name=body.title,
        replace_existing=True,
    )

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

    status_change: str | None = None
    reschedule: tuple[str, str, str] | None = None

    if body.title is not None:
        reminder.title = body.title
    if body.status is not None:
        if body.status not in ("active", "paused"):
            raise HTTPException(status_code=400, detail="Status must be 'active' or 'paused'")
        if body.status != reminder.status:
            status_change = body.status
        reminder.status = body.status
    if body.schedule_text is not None:
        profile_stmt = select(UserProfile).where(UserProfile.user_id == user.user_id)
        profile = (await db.execute(profile_stmt)).scalar_one_or_none()
        user_tz = profile.timezone if profile else "UTC"

        try:
            schedule = await parse_schedule(body.schedule_text, user_tz)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not validate_schedule(schedule):
            raise HTTPException(status_code=400, detail="Invalid schedule expression")

        reminder.schedule_kind = schedule.kind
        reminder.schedule_expr = schedule.expr
        reminder.timezone = schedule.timezone
        reschedule = (schedule.kind, schedule.expr, schedule.timezone)

    await db.commit()

    sched = get_scheduler()
    if reschedule is not None:
        trigger = make_trigger(*reschedule)
        try:
            sched.reschedule_job(reminder.job_id, trigger=trigger)
        except Exception:
            # Job may have been removed (e.g. a once that already fired). Recreate it.
            sched.add_job(
                fire_reminder, trigger=trigger, args=[str(reminder.reminder_id)],
                id=reminder.job_id, name=reminder.title, replace_existing=True,
            )
    if status_change == "paused":
        try:
            sched.pause_job(reminder.job_id)
        except Exception:
            logger.warning("pause_job failed for %s", reminder.job_id, exc_info=True)
    elif status_change == "active":
        try:
            sched.resume_job(reminder.job_id)
        except Exception:
            logger.warning("resume_job failed for %s", reminder.job_id, exc_info=True)

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

    try:
        get_scheduler().remove_job(reminder.job_id)
    except Exception:
        # Job may already be gone (once fired, or never scheduled). Ignore.
        pass

    return {"status": "cancelled"}
