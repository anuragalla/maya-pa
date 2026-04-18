# Live150 — USER.md (template)

This is a template. At every turn, the runtime populates `session.state["user_profile_summary"]` with a compact version of this shape using the user's real profile. The agent reads it at turn start.

Keep it tight — it lives in every prompt and pays token cost on every turn. Fields are optional; omit what's missing rather than writing "unknown."

---

## Basics
- **Preferred name:** {{preferred_name}}
- **Age:** {{age}}
- **Timezone:** {{timezone}} (e.g., Asia/Kolkata)
- **Locale:** {{locale}}
- **Biological sex:** {{bio_sex}} (matters for some recommendations; omit if not provided)

## Goal
- **Primary:** {{primary_goal}} (e.g., "reduce biological age", "reverse prediabetes", "build strength without losing sleep quality")
- **Secondary:** {{secondary_goal}}
- **Why:** {{motivation}} — the user's own words if captured

## Profile
- **Chronotype:** {{chronotype}} (early / intermediate / late)
- **Diet:** {{diet_type}} (omnivore / vegetarian / vegan / pescatarian / keto / etc.)
- **Dietary restrictions:** {{restrictions}} (allergies, religious, medical — comma-separated, short)
- **Conditions:** {{conditions}} (e.g., "type 2 diabetes, mild hypertension" — present-tense, diagnosed only)
- **Medications (relevant):** {{medications}} (only those that interact with recommendations — e.g., statins, metformin, SSRIs; omit otherwise)

## Devices connected
- {{devices}} (e.g., "Whoop, Oura, Apple Health"). Data source priority is in the tool layer, not here.

## Recent trends (last 7 days, auto-refreshed)
- **Sleep:** {{sleep_summary}} (e.g., "avg 6h 38m, ↓8% WoW; consistency poor, bedtime drift 90 min")
- **Activity:** {{activity_summary}} (e.g., "5 of 7 days hit step target; 2 strength sessions; 0 Zone 2")
- **Nutrition:** {{nutrition_summary}} (e.g., "late dinners 4 of 7 nights; alcohol twice")
- **Recovery / HRV:** {{recovery_summary}}
- **Bio-age delta (if tracked):** {{bio_age_delta}} (e.g., "+0.3y since last review")

## Current plan (active)
- {{active_plan_summary}} (e.g., "7pm dinner cutoff; 2x strength + 3x Zone 2 per week; 10:30pm bedtime target")

## Preferences and constraints
- {{preferences}} (e.g., "hates morning workouts, prefers evening strength; no running due to knee load")

## Adherence notes (rolling, from memory)
- {{adherence_notes}} (e.g., "7pm dinner: adherent 3 of 7 last week; cited work dinners twice")

---

*The runtime is responsible for keeping this summary tight. Target <400 tokens rendered. If any section is empty, drop the heading entirely rather than writing "none." Don't pad.*
