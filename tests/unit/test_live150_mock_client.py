"""Tests for the Live150 dev-route mock client.

The mock is the primary way to exercise the five-route handoff without a
running backend. These tests verify:
- the two-step impersonate → access token flow
- each route's response shape for all three documented test users
- the 404 path on unknown phone numbers
- that Pragya's "no plan yet" paid-tier case and Murthy's free-tier case
  both use the literal strings the real endpoint returns
"""

import pytest

from live150.live150_client import Live150MockClient
from live150.live150_client.base import Live150Conflict, Live150NotFound, Live150Unauthorized
from live150.live150_client.mock_client import _FIXTURES, _mock_token
from live150.live150_client.schemas import HolisticAnalysis, InitialContext, MayaWrappedResponse

NIGEL = "+19084329987"
MURTHY = "+19083612019"
PRAGYA = "+12243347204"


@pytest.fixture
def client() -> Live150MockClient:
    return Live150MockClient()


@pytest.mark.asyncio
async def test_impersonate_known_users_returns_bearer_token(client):
    for phone in (NIGEL, MURTHY, PRAGYA):
        resp = await client.impersonate(phone)
        assert resp.token_type == "bearer"
        assert resp.access_token == _mock_token(phone)


@pytest.mark.asyncio
async def test_impersonate_unknown_phone_raises_not_found(client):
    with pytest.raises(Live150NotFound):
        await client.impersonate("+10000000000")


def test_live150_conflict_is_a_dedicated_exception():
    """The mock's fixture table does not model refresh-token state, so 409
    is not reachable via `impersonate()`. This test only asserts that the
    typed exception exists so HTTP-client code can depend on it."""
    with pytest.raises(Live150Conflict):
        raise Live150Conflict(f"user {NIGEL} exists but has no active refresh tokens")


@pytest.mark.asyncio
async def test_holistic_analysis_populates_all_pillars_for_nigel(client):
    token = (await client.impersonate(NIGEL)).access_token
    result = await client.get_holistic_analysis(token)

    assert isinstance(result, HolisticAnalysis)
    for pillar in ("nutrition", "activity", "mindfulness", "sleep", "glucose", "weight"):
        assert getattr(result, pillar), f"pillar {pillar} should be populated for Nigel"
    assert result.maya_says_nutrition
    assert result.tool_tip_nutrition
    assert result.is_active is True


@pytest.mark.asyncio
async def test_holistic_analysis_allows_null_pillars(client):
    """Murthy has a null mindfulness pillar; Pragya has a null glucose pillar.
    The API contract allows any pillar to be null."""
    murthy_token = (await client.impersonate(MURTHY)).access_token
    murthy = await client.get_holistic_analysis(murthy_token)
    assert murthy.mindfulness is None
    assert murthy.nutrition is not None

    pragya_token = (await client.impersonate(PRAGYA)).access_token
    pragya = await client.get_holistic_analysis(pragya_token)
    assert pragya.glucose is None


@pytest.mark.asyncio
async def test_progress_by_date_returns_plaintext_string(client):
    token = (await client.impersonate(NIGEL)).access_token
    result = await client.get_progress_by_date(token, "2026-04-17")

    assert isinstance(result, str)
    assert "Goal Progress:" in result
    assert "Calories Consumed:" in result
    assert "2026-04-17" in result
    # "No Data Recorded" should appear for unlogged sections.
    assert "No Data Recorded" in result


@pytest.mark.asyncio
async def test_health_goals_wraps_plaintext_response(client):
    token = (await client.impersonate(NIGEL)).access_token
    result = await client.get_my_health_goals(token)

    assert isinstance(result, MayaWrappedResponse)
    assert "Holistic Goals:" in result.response
    assert "Daily Nutritional Goals:" in result.response
    assert result.query == "My Health Goals"


@pytest.mark.asyncio
async def test_health_goals_can_be_sparse(client):
    """Murthy's onboarding is sparse — the response should still be valid but short."""
    token = (await client.impersonate(MURTHY)).access_token
    result = await client.get_my_health_goals(token)
    assert "Daily Nutritional Goals:" not in result.response
    assert "Holistic Goals:" in result.response


@pytest.mark.asyncio
async def test_meal_plan_paid_with_plan(client):
    token = (await client.impersonate(NIGEL)).access_token
    result = await client.get_meal_plan(token)

    assert isinstance(result, MayaWrappedResponse)
    assert "Breakfast" in result.response
    assert "Dinner" in result.response
    assert result.query == "My diet plan for today"


@pytest.mark.asyncio
async def test_meal_plan_paid_without_plan_uses_literal_string(client):
    """Pragya is paid-tier but has no plan for today — contract says the
    response must be this exact string so the app can show a generate-plan CTA."""
    token = (await client.impersonate(PRAGYA)).access_token
    result = await client.get_meal_plan(token)
    assert result.response == (
        "No meal plan generated for today. Please generate a meal plan first."
    )


@pytest.mark.asyncio
async def test_meal_plan_free_tier_prompts_upgrade(client):
    token = (await client.impersonate(MURTHY)).access_token
    result = await client.get_meal_plan(token)
    assert "Premium" in result.response or "upgrade" in result.response.lower()


@pytest.mark.asyncio
async def test_initial_context_defaults_to_profile_location(client):
    token = (await client.impersonate(NIGEL)).access_token
    result = await client.get_initial_context(token)

    assert isinstance(result, InitialContext)
    assert result.user_data.full_name == "Nigel Fernandes"
    assert result.user_data.timezone_name == "America/Los_Angeles"
    assert result.user_data.location == _FIXTURES[NIGEL]["location"]
    assert result.time_offset == -420
    # Questionnaires should be present (none of the fetches fail in the mock).
    assert result.nutrition_questionnaire is not None
    assert result.activity_questionnaire is not None


@pytest.mark.asyncio
async def test_initial_context_uses_lat_long_when_both_supplied(client):
    token = (await client.impersonate(NIGEL)).access_token
    result = await client.get_initial_context(token, latitude=40.7128, longitude=-74.0060)
    assert "lat=40.7128" in result.user_data.location
    assert "lon=-74.0060" in result.user_data.location


@pytest.mark.asyncio
async def test_initial_context_lat_only_falls_back_to_profile(client):
    """Contract: if either lat or long is missing, fall back to profile location."""
    token = (await client.impersonate(NIGEL)).access_token
    result = await client.get_initial_context(token, latitude=40.7128, longitude=None)
    assert result.user_data.location == _FIXTURES[NIGEL]["location"]


@pytest.mark.asyncio
async def test_routes_reject_unknown_access_token(client):
    with pytest.raises(Live150Unauthorized):
        await client.get_holistic_analysis("not-a-mock-token")
    with pytest.raises(Live150Unauthorized):
        await client.get_progress_by_date("not-a-mock-token", "2026-04-17")
    with pytest.raises(Live150Unauthorized):
        await client.get_my_health_goals("not-a-mock-token")
    with pytest.raises(Live150Unauthorized):
        await client.get_meal_plan("not-a-mock-token")
    with pytest.raises(Live150Unauthorized):
        await client.get_initial_context("not-a-mock-token")
