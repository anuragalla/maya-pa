"""In-memory mock of the Live150 dev-route client.

Mirrors the five GET routes plus the impersonation exchange with canned data
for the three test users named in the dev handoff:

    Nigel   +19084329987
    Murthy  +19083612019
    Pragya  +12243347204

Also handles a catch-all "new paid user" (no meal plan generated yet) and an
unknown-phone-number case (raises Live150NotFound). Use this in tests and
when `LIVE150_USE_MOCK=true` in local dev.
"""

from datetime import UTC, datetime

from live150.live150_client.base import Live150NotFound, Live150Unauthorized
from live150.live150_client.schemas import (
    HolisticAnalysis,
    ImpersonateResponse,
    InitialContext,
    MayaWrappedResponse,
    UserData,
)

# Token prefix used to derive which fixture a mock access token maps to.
_TOKEN_PREFIX = "mock-access-token::"


def _mock_token(phone_number: str) -> str:
    return f"{_TOKEN_PREFIX}{phone_number}"


def _phone_for_token(access_token: str) -> str:
    if not access_token.startswith(_TOKEN_PREFIX):
        raise Live150Unauthorized(f"mock client does not recognize token: {access_token!r}")
    return access_token[len(_TOKEN_PREFIX):]


# Shared questionnaire fixtures — same shape for every user today. Hoisted
# out of the per-call path so we're not rebuilding identical dicts on every
# `get_initial_context` call.
_NUTRITION_QUESTIONNAIRE = {
    "goals": ["balanced_macros"],
    "restrictions": [],
    "preferences": ["mediterranean"],
}
_ACTIVITY_QUESTIONNAIRE = {
    "fitness_level": "intermediate",
    "preferred_modalities": ["strength", "walking"],
}
_SLEEP_QUESTIONNAIRE = {
    "target_hours": 7.5,
    "chronotype": "neutral",
}
_MINDFULNESS_QUESTIONNAIRE = {
    "preferred_practice": "breath_work",
    "daily_minutes_target": 10,
}


# Fixture payloads keyed by phone number.
_FIXTURES: dict[str, dict] = {
    # Nigel — full plan, all six pillars populated, paid tier with meal plan.
    "+19084329987": {
        "display_name": "Nigel",
        "full_name": "Nigel Fernandes",
        "timezone_name": "America/Los_Angeles",
        "time_offset": -420,
        "location": "San Francisco, CA",
        "health_profile": {
            "age": 41,
            "weight_kg": 82.3,
            "height_cm": 178,
            "units": "metric",
            "medical_conditions": ["prediabetes"],
        },
        "holistic": {
            "nutrition": (
                "Protein intake is trending 20g below target for the week — "
                "keep prioritizing protein at breakfast."
            ),
            "activity": (
                "Logged three strength sessions; cardio frequency is down. "
                "Add a 30-min zone-2 walk on rest days."
            ),
            "mindfulness": (
                "Evening journaling streak is strong. "
                "Consider a 5-min morning breath practice before standups."
            ),
            "sleep": "Total sleep averaged 6h42m — short of your 7h30m target. Shift lights-out 30 min earlier.",
            "glucose": "Fasting readings stable at 95-102 mg/dL. Post-lunch spikes moderate; pair carbs with protein.",
            "weight": "Down 0.4kg week-over-week — tracking on target for moderate-pace goal.",
            "maya_says": "You're building momentum — let's tighten sleep this week.",
        },
        "health_goals": (
            "Holistic Goals: weight_loss, diabetes_management.\n"
            "Daily Nutritional Goals:\n"
            "Calories- 2000\n"
            "Protein- 120\n"
            "Carbs- 250\n"
            "Fats- 70\n"
            "Sugar- 50\n"
            "Weight Goal:\n"
            "Target: 75\n"
            "Current Weight: 82.3 kg\n"
            "Pace: moderate\n"
            "Health Concerns: Prediabetes"
        ),
        "meal_plan": (
            "**Breakfast** — Greek yogurt parfait with berries and walnuts\n"
            "  Portion: 1 bowl | Calories: 380 | P 28g | C 32g | F 14g\n"
            "**Lunch** — Grilled chicken, quinoa, roasted vegetables\n"
            "  Portion: 1 plate | Calories: 540 | P 42g | C 48g | F 18g\n"
            "**Snack** — Cottage cheese with sliced apple\n"
            "  Portion: 1 cup | Calories: 210 | P 22g | C 18g | F 5g\n"
            "**Dinner** — Baked salmon, sweet potato, sautéed spinach\n"
            "  Portion: 1 plate | Calories: 620 | P 44g | C 52g | F 22g\n"
            "Day totals: 1750 kcal | P 136g | C 150g | F 59g"
        ),
        "tier": "paid",
    },
    # Murthy — free-tier, meal plan blocked, sparse health goals.
    "+19083612019": {
        "display_name": "Murthy",
        "full_name": "Murthy Rao",
        "timezone_name": "America/Los_Angeles",
        "time_offset": -420,
        "location": "Palo Alto, CA",
        "health_profile": {
            "age": 52,
            "weight_kg": 91.0,
            "height_cm": 182,
            "units": "metric",
            "medical_conditions": ["type_2_diabetes"],
        },
        "holistic": {
            "nutrition": "Carb timing still inconsistent on weekdays — shift the biggest meal to earlier in the day.",
            "activity": "Step count rising steadily — good trajectory. Add one resistance session this week.",
            "mindfulness": None,
            "sleep": "Sleep onset latency high (~35 min). Try no screens after 9:30pm for three nights.",
            "glucose": "Post-dinner spikes elevated (180+). Reduce evening refined carbs or walk 15 min after dinner.",
            "weight": "Flat week-over-week — revisit calorie target if flat for another 10 days.",
            "maya_says": "Let's focus on evening glucose this week — small change, big payoff.",
        },
        "health_goals": (
            "Holistic Goals: diabetes_management.\n"
            "Health Concerns: Type 2 Diabetes"
        ),
        "meal_plan": (
            "Personalized meal plans are part of Live150 Premium. "
            "Upgrade to unlock daily plans tailored to your goals and health profile."
        ),
        "tier": "free",
    },
    # Pragya — paid tier but no meal plan generated for today yet.
    "+12243347204": {
        "display_name": "Pragya",
        "full_name": "Pragya Sharma",
        "timezone_name": "America/Chicago",
        "time_offset": -300,
        "location": "Chicago, IL",
        "health_profile": {
            "age": 34,
            "weight_kg": 64.5,
            "height_cm": 165,
            "units": "metric",
            "medical_conditions": [],
        },
        "holistic": {
            "nutrition": "Fiber intake ahead of target — keep it up. Hydration lagging; aim for 2.5L.",
            "activity": "Yoga 4x this week plus two runs — nice balance. Consider a long run on Sunday.",
            "mindfulness": "Meditation streak at 12 days. Try extending sessions from 10 to 15 min.",
            "sleep": "Consistent 7h20m — right on target.",
            "glucose": None,
            "weight": "Stable — maintenance phase looks solid.",
            "maya_says": "You're in a great rhythm — just nudge hydration up.",
        },
        "health_goals": (
            "Holistic Goals: general_wellness.\n"
            "Daily Nutritional Goals:\n"
            "Calories- 1800\n"
            "Protein- 90\n"
            "Carbs- 220\n"
            "Fats- 60\n"
            "Sugar- 40"
        ),
        "meal_plan": (
            "No meal plan generated for today. Please generate a meal plan first."
        ),
        "tier": "paid",
    },
}


def _progress_summary(fixture: dict, date_lookup: str) -> str:
    """Render the plaintext summary the app would show for route 2."""
    name = fixture["display_name"]
    return (
        f"**Date**: {date_lookup} ({name})\n"
        "**Nutrition**:\n"
        "- Breakfast: Greek yogurt with berries\n"
        "- Lunch: Grilled chicken salad\n"
        "- Snack: No Data Recorded\n"
        "- Dinner: No Data Recorded\n"
        "**Activity**:\n"
        "- Morning walk, 32 min\n"
        "**Mindfulness**:\n"
        "- No Data Recorded\n"
        "\n"
        "Goal Progress:\n"
        "- Calories Consumed: [920.5 / 2000.0] kcal\n"
        "- Macros: Protein [70.2 / 120.0] g, Carbs [95.4 / 250.0] g, "
        "Sugar [18.1 / 50.0] g, Fat [28.9 / 70.0] g\n"
        "- Calories Burned: [142.7 / 400.0] kcal\n"
        "- Blood Glucose Readings Recorded: 1"
    )


def _holistic(fixture: dict) -> HolisticAnalysis:
    h = fixture["holistic"]
    maya = h["maya_says"]
    now = datetime.now(UTC)
    return HolisticAnalysis(
        nutrition=h["nutrition"],
        activity=h["activity"],
        mindfulness=h["mindfulness"],
        sleep=h["sleep"],
        glucose=h["glucose"],
        weight=h["weight"],
        maya_says_nutrition=maya,
        maya_says_activity=maya,
        maya_says_mindfulness=maya,
        maya_says_sleep=maya,
        maya_says_glucose=maya,
        maya_says_weight=maya,
        tool_tip_nutrition="Tap to see full nutrition breakdown",
        tool_tip_activity="Tap to see activity details",
        tool_tip_mindfulness="Tap to see mindfulness log",
        tool_tip_sleep="Tap to see sleep stages",
        tool_tip_glucose="Tap to see CGM trace",
        tool_tip_weight="Tap to see weight history",
        is_active=True,
        owner_id=f"user::{fixture['display_name'].lower()}",
        record_created_at=now,
        record_updated_at=now,
    )


def _initial_context(
    fixture: dict,
    latitude: float | None,
    longitude: float | None,
) -> InitialContext:
    if latitude is not None and longitude is not None:
        location = f"lat={latitude:.4f},lon={longitude:.4f}"
    else:
        location = fixture["location"]

    return InitialContext(
        time_offset=fixture["time_offset"],
        user_data=UserData(
            full_name=fixture["full_name"],
            display_name=fixture["display_name"],
            location=location,
            timezone_name=fixture["timezone_name"],
            health_profile=fixture["health_profile"],
        ),
        nutrition_questionnaire=_NUTRITION_QUESTIONNAIRE,
        activity_questionnaire=_ACTIVITY_QUESTIONNAIRE,
        sleep_questionnaire=_SLEEP_QUESTIONNAIRE,
        mindfulness_questionnaire=_MINDFULNESS_QUESTIONNAIRE,
    )


class Live150MockClient:
    """In-memory implementation of `Live150Client`. Deterministic, no I/O."""

    DEV_TOKEN_ACCEPTED = "mock-dev-token"

    def __init__(self, dev_token: str | None = None) -> None:
        # In mock mode any non-empty dev token is accepted — the goal is to
        # exercise the two-step flow in dev without a real backend.
        self._dev_token = dev_token or self.DEV_TOKEN_ACCEPTED

    async def impersonate(self, phone_number: str) -> ImpersonateResponse:
        if phone_number not in _FIXTURES:
            raise Live150NotFound(f"no user with phone number {phone_number}")
        return ImpersonateResponse(
            access_token=_mock_token(phone_number),
            token_type="bearer",
        )

    def _fixture_for(self, access_token: str) -> dict:
        phone = _phone_for_token(access_token)
        if phone not in _FIXTURES:
            raise Live150Unauthorized(f"no fixture for phone {phone}")
        return _FIXTURES[phone]

    async def get_holistic_analysis(self, access_token: str) -> HolisticAnalysis | None:
        fixture = self._fixture_for(access_token)
        return _holistic(fixture)

    async def get_progress_by_date(self, access_token: str, date_lookup: str) -> str:
        fixture = self._fixture_for(access_token)
        return _progress_summary(fixture, date_lookup)

    async def get_my_health_goals(self, access_token: str) -> MayaWrappedResponse:
        fixture = self._fixture_for(access_token)
        now = datetime.now(UTC)
        return MayaWrappedResponse(
            response=fixture["health_goals"],
            session_id="mock-session",
            user_id=f"user::{fixture['display_name'].lower()}",
            query="My Health Goals",
            id="mock-chat-history-row",
            record_created_at=now,
            record_updated_at=now,
        )

    async def get_meal_plan(self, access_token: str) -> MayaWrappedResponse:
        fixture = self._fixture_for(access_token)
        now = datetime.now(UTC)
        return MayaWrappedResponse(
            response=fixture["meal_plan"],
            session_id="mock-session",
            user_id=f"user::{fixture['display_name'].lower()}",
            query="My diet plan for today",
            id="mock-chat-history-row",
            record_created_at=now,
            record_updated_at=now,
        )

    async def get_initial_context(
        self,
        access_token: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> InitialContext:
        fixture = self._fixture_for(access_token)
        return _initial_context(fixture, latitude, longitude)
