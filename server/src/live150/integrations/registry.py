"""Integrations registry — single source of truth for available integrations.

The agent calls list_available_integrations / request_integration_connect
to discover and offer integrations to the user in-chat.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Integration:
    name: str  # "google_calendar"
    display_name: str  # "Google Calendar"
    provider: str  # "google" — maps to oauth_token.provider
    category: str  # "calendar" | "email" | "health_devices" | ...
    scopes_required: list[str] = field(default_factory=list)
    description: str = ""
    available: bool = True  # feature flag


INTEGRATIONS: list[Integration] = [
    Integration(
        name="google_calendar",
        display_name="Google Calendar",
        provider="google",
        category="calendar",
        scopes_required=[
            "https://www.googleapis.com/auth/calendar",
        ],
        description="Sync Live150 reminders and routines to your calendar, and let me see your schedule to plan around it.",
    ),
    # Future:
    # Integration(name="microsoft_calendar", provider="microsoft", category="calendar", ...)
]


def get_integration(name: str) -> Integration | None:
    return next((i for i in INTEGRATIONS if i.name == name), None)


def list_integrations(category: str | None = None) -> list[Integration]:
    result = [i for i in INTEGRATIONS if i.available]
    if category:
        result = [i for i in result if i.category == category]
    return result
