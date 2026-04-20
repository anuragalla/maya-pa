"""Unit tests for the shared trigger helper used by both the create-reminder
tool and the REST endpoint. fire_reminder itself needs a live DB + agent
and is exercised by the integration suite."""

from datetime import datetime, timedelta, timezone

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from live150.reminders.jobs import make_trigger


def test_make_trigger_once():
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    trig = make_trigger("once", future, "UTC")
    assert isinstance(trig, DateTrigger)


def test_make_trigger_cron():
    trig = make_trigger("cron", "0 9 * * 1", "UTC")
    assert isinstance(trig, CronTrigger)


def test_make_trigger_interval():
    trig = make_trigger("interval", "3600", "UTC")
    assert isinstance(trig, IntervalTrigger)


def test_make_trigger_unknown_raises():
    with pytest.raises(ValueError):
        make_trigger("bogus", "whatever", "UTC")
