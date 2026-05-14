"""Onboarding voice tool declarations and handlers.

Three tools for the onboarding voice agent:
- set_onboarding_field: Set a profile field value
- advance_step: Move to the next onboarding step
- go_back: Return to the previous step
"""

import logging

logger = logging.getLogger(__name__)

VALID_STEPS = ["age", "gender", "height", "weight", "conditions", "goals", "diet"]

GENDER_OPTIONS = ["female", "male", "nonbinary", "prefer_not_to_say"]
CONDITION_OPTIONS = ["stress", "heart", "bp", "diabetes", "sleep", "thyroid", "pcos", "none"]
GOAL_OPTIONS = ["fatloss", "glucose", "sleep", "strength", "stress", "longevity"]
DIET_OPTIONS = ["vegetarian", "non_veg", "vegan", "pescatarian", "flexible"]

TOOL_DECLARATIONS: list[dict] = [
    {
        "name": "set_onboarding_field",
        "description": (
            "Set a value for a specific onboarding profile field. "
            "Call this when the user provides information for any onboarding step. "
            "The frontend will update the UI to reflect the selection."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "step": {
                    "type": "string",
                    "enum": VALID_STEPS,
                    "description": "Which onboarding field to set.",
                },
                "value": {
                    "description": (
                        "The value to set. Type depends on step:\n"
                        "- age: integer (e.g. 28)\n"
                        "- gender: one of 'female', 'male', 'nonbinary', 'prefer_not_to_say'\n"
                        "- height: integer in centimeters (convert from feet/inches if needed, e.g. 5'10\" = 178)\n"
                        "- weight: integer in kilograms (convert from pounds if needed, e.g. 165 lb = 75)\n"
                        "- conditions: array of strings from ['stress', 'heart', 'bp', 'diabetes', 'sleep', 'thyroid', 'pcos', 'none']\n"
                        "- goals: array of strings from ['fatloss', 'glucose', 'sleep', 'strength', 'stress', 'longevity']\n"
                        "- diet: one of 'vegetarian', 'non_veg', 'vegan', 'pescatarian', 'flexible'"
                    ),
                },
            },
            "required": ["step", "value"],
        },
    },
    {
        "name": "advance_step",
        "description": (
            "Move to the next onboarding step. Call this when the user confirms "
            "their current selection or says something like 'next', 'continue', 'that's it', 'done'. "
            "Do NOT call this immediately after set_onboarding_field — wait for user confirmation."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "go_back",
        "description": (
            "Go back to the previous onboarding step. Call when the user says "
            "'go back', 'previous', 'wait let me change that', etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def _validate_field(step: str, value) -> tuple[bool, str]:
    """Validate a field value. Returns (is_valid, error_message)."""
    if step == "age":
        if not isinstance(value, (int, float)) or value < 13 or value > 120:
            return False, "Age must be a number between 13 and 120."
        return True, ""

    if step == "gender":
        if value not in GENDER_OPTIONS:
            return False, f"Gender must be one of: {', '.join(GENDER_OPTIONS)}"
        return True, ""

    if step == "height":
        if not isinstance(value, (int, float)) or value < 120 or value > 240:
            return False, "Height must be between 120 and 240 cm."
        return True, ""

    if step == "weight":
        if not isinstance(value, (int, float)) or value < 30 or value > 200:
            return False, "Weight must be between 30 and 200 kg."
        return True, ""

    if step == "conditions":
        if not isinstance(value, list):
            return False, "Conditions must be a list."
        invalid = [v for v in value if v not in CONDITION_OPTIONS]
        if invalid:
            return False, f"Invalid conditions: {', '.join(invalid)}"
        return True, ""

    if step == "goals":
        if not isinstance(value, list):
            return False, "Goals must be a list."
        invalid = [v for v in value if v not in GOAL_OPTIONS]
        if invalid:
            return False, f"Invalid goals: {', '.join(invalid)}"
        return True, ""

    if step == "diet":
        if value not in DIET_OPTIONS:
            return False, f"Diet must be one of: {', '.join(DIET_OPTIONS)}"
        return True, ""

    return False, f"Unknown step: {step}"


async def handle_set_onboarding_field(args: dict, **_ctx) -> dict:
    step = args.get("step", "")
    value = args.get("value")

    if step not in VALID_STEPS:
        return {"success": False, "error": f"Unknown step: {step}"}

    if value is None:
        return {"success": False, "error": "No value provided."}

    if step in ("height", "weight", "age") and isinstance(value, (int, float)):
        value = int(round(value))

    valid, error = _validate_field(step, value)
    if not valid:
        return {"success": False, "error": error}

    return {"success": True, "step": step, "value": value}


async def handle_advance_step(**_ctx) -> dict:
    return {"success": True, "action": "advance"}


async def handle_go_back(**_ctx) -> dict:
    return {"success": True, "action": "go_back"}


ONBOARDING_TOOL_HANDLERS: dict = {
    "set_onboarding_field": handle_set_onboarding_field,
    "advance_step": handle_advance_step,
    "go_back": handle_go_back,
}


def get_onboarding_tool_config() -> list[dict]:
    """Return the tools config for the onboarding Gemini Live session."""
    return [{"function_declarations": TOOL_DECLARATIONS}]
