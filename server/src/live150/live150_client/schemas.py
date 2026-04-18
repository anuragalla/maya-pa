"""Pydantic schemas for the Live150 dev-route responses.

Field naming matches the wire format described in the dev handoff:
- Route 1 (holistic-analysis) returns snake_case straight from the SQLAlchemy model.
- Routes 2-4 return a JSON wrapper with a `response` plaintext string.
- Route 5 (initial-context) returns a nested snake_case dict.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImpersonateRequest(BaseModel):
    phone_number: str = Field(..., alias="phoneNumber")

    model_config = ConfigDict(populate_by_name=True)


class ImpersonateResponse(BaseModel):
    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field("bearer", alias="tokenType")

    model_config = ConfigDict(populate_by_name=True)


class HolisticAnalysis(BaseModel):
    """Route 1 — GET /api/v1/internal/holistic-analysis.

    Snake_case straight from the DB model. Nulls allowed throughout because
    the FLP pipeline may not have populated every pillar for the current day.
    A null top-level response means no analysis has been generated yet today.
    """

    nutrition: str | None = None
    activity: str | None = None
    mindfulness: str | None = None
    sleep: str | None = None
    glucose: str | None = None
    weight: str | None = None

    maya_says_nutrition: str | None = None
    maya_says_activity: str | None = None
    maya_says_mindfulness: str | None = None
    maya_says_sleep: str | None = None
    maya_says_glucose: str | None = None
    maya_says_weight: str | None = None

    tool_tip_nutrition: str | None = None
    tool_tip_activity: str | None = None
    tool_tip_mindfulness: str | None = None
    tool_tip_sleep: str | None = None
    tool_tip_glucose: str | None = None
    tool_tip_weight: str | None = None

    is_active: bool | None = None
    owner_id: str | None = None
    record_created_at: datetime | None = None
    record_updated_at: datetime | None = None


class MayaWrappedResponse(BaseModel):
    """Routes 3 and 4 share this envelope: plaintext in `response`, plus
    chat-history housekeeping fields from the side-effect insert into
    `maya_chat_history`. Route 2 returns a bare string — don't use this
    schema for it."""

    response: str
    session_id: str | None = None
    user_id: str | None = None
    query: str | None = None
    id: str | None = None
    record_created_at: datetime | None = None
    record_updated_at: datetime | None = None


class UserData(BaseModel):
    full_name: str = ""
    display_name: str = ""
    location: str = ""
    timezone_name: str = "UTC"
    health_profile: dict[str, Any] = Field(default_factory=dict)


class InitialContext(BaseModel):
    """Route 5 — GET /api/v1/maya/maya/initial-context.

    Questionnaire fetches are independent — if a fetch fails the key is
    absent rather than null. Consumers must check for membership before
    dereferencing."""

    time_offset: int = 0
    user_data: UserData = Field(default_factory=UserData)
    nutrition_questionnaire: dict[str, Any] | None = None
    activity_questionnaire: dict[str, Any] | None = None
    sleep_questionnaire: dict[str, Any] | None = None
    mindfulness_questionnaire: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")
