"""Render the USER.md template into a compact user profile summary.

The rendered string goes into session.state["user_profile_summary"] at
the start of each turn. Target <400 tokens. Omit empty sections entirely.
"""

import logging
from pathlib import Path

from live150.live150_client.schemas import InitialContext

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = Path(__file__).parent / "USER.md"


def render_user_profile(ctx: InitialContext) -> str:
    """Render a compact user profile summary from the initial-context API response.

    Follows USER.md structure but only includes sections that have data.
    Empty fields and sections are dropped entirely — no "unknown" padding.
    """
    lines: list[str] = []

    ud = ctx.user_data
    hp = ud.health_profile

    # Basics
    basics = []
    if ud.display_name:
        basics.append(f"- **Preferred name:** {ud.display_name}")
    if hp.get("age"):
        basics.append(f"- **Age:** {hp['age']}")
    if ud.timezone_name and ud.timezone_name != "UTC":
        basics.append(f"- **Timezone:** {ud.timezone_name}")
    if hp.get("units"):
        basics.append(f"- **Units:** {hp['units']}")

    if basics:
        lines.append("## Basics")
        lines.extend(basics)

    # Profile
    profile = []
    if hp.get("weight_kg"):
        w = hp["weight_kg"]
        h = hp.get("height_cm", "")
        profile.append(f"- **Weight:** {w} kg" + (f", Height: {h} cm" if h else ""))
    if hp.get("medical_conditions"):
        conditions = hp["medical_conditions"]
        if isinstance(conditions, list) and conditions:
            profile.append(f"- **Conditions:** {', '.join(conditions)}")

    if profile:
        lines.append("## Profile")
        lines.extend(profile)

    # Goals — from questionnaires
    goals = []
    nq = ctx.nutrition_questionnaire or {}
    aq = ctx.activity_questionnaire or {}

    if nq.get("goals"):
        g = nq["goals"]
        goals.append(f"- **Nutrition goals:** {', '.join(g) if isinstance(g, list) else g}")
    if nq.get("restrictions"):
        r = nq["restrictions"]
        if r:
            goals.append(f"- **Dietary restrictions:** {', '.join(r) if isinstance(r, list) else r}")
    if nq.get("preferences"):
        p = nq["preferences"]
        goals.append(f"- **Diet preference:** {', '.join(p) if isinstance(p, list) else p}")
    if aq.get("fitness_level"):
        goals.append(f"- **Fitness level:** {aq['fitness_level']}")
    if aq.get("preferred_modalities"):
        m = aq["preferred_modalities"]
        goals.append(f"- **Preferred activity:** {', '.join(m) if isinstance(m, list) else m}")

    if goals:
        lines.append("## Goals & Preferences")
        lines.extend(goals)

    # Sleep
    sq = ctx.sleep_questionnaire or {}
    sleep = []
    if sq.get("target_hours"):
        sleep.append(f"- **Sleep target:** {sq['target_hours']}h")
    if sq.get("chronotype"):
        sleep.append(f"- **Chronotype:** {sq['chronotype']}")

    if sleep:
        lines.append("## Sleep")
        lines.extend(sleep)

    # Mindfulness
    mq = ctx.mindfulness_questionnaire or {}
    mind = []
    if mq.get("preferred_practice"):
        mind.append(f"- **Practice:** {mq['preferred_practice']}")
    if mq.get("daily_minutes_target"):
        mind.append(f"- **Target:** {mq['daily_minutes_target']} min/day")

    if mind:
        lines.append("## Mindfulness")
        lines.extend(mind)

    if not lines:
        return "(No profile data available)"

    return "\n".join(lines)
