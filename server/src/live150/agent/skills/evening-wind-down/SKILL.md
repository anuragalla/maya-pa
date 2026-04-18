---
name: evening-wind-down
description: Produce an evening check-in or wind-down nudge. Use when the user messages late in the day, asks "how am I doing today", or when an evening reminder fires. Covers adherence on today's asks, tonight's bedtime target, and one wind-down action. Short.
---

# Evening Wind-Down

## When to use

- User's first message after ~6pm local time, or user asks "how am I doing today"
- An evening reminder fires — typically 60–90 minutes before target bedtime
- User explicitly asks "should I go to bed now" or "what's my bedtime tonight"

## When not to use

- Morning brief context (use `daily-morning-brief`)
- Ad-hoc Q&A (answer the question directly)
- Mid-day check-ins (keep it conversational, don't trigger a wind-down flow)

## Inputs you need

1. Today's activity so far (`get_activity_summary(days=1)`)
2. Today's nutrition if logged (`get_meal_log(days=1)`)
3. This morning's asks from memory — search `"today's morning brief actions"` or the most recent `save_memory` entry of `kind="note"`
4. Tomorrow's first commitment from calendar (only if connected) — dictates bedtime target
5. User's chronotype and typical bedtime from `user_profile_summary`

## Output shape

**Interactive turn** — two to three sentences, then one suggestion:

1. Adherence read on this morning's asks (if you gave any). One sentence. No shame on misses — just note.
2. Tonight's bedtime target, with the reason (tomorrow's first commitment + chronotype).
3. One wind-down nudge. Pick the one that fits tonight. Don't stack three.

**Reminder turn** (push notification) — tighter:

- Line 1: the target time, ≤80 characters. *"Wind down now for a 10:30 target"*
- Line 2: the reason in one sentence.

## Wind-down nudge options

Pick **one** based on what the user actually does. Don't list all four.

- **Caffeine / stimulant cutoff:** *"If you're thinking about one more coffee — skip it. You're within caffeine's half-life window for a 10:30 bedtime."*
- **Screen cutoff:** *"Phone down at 10:00 tonight. Dim the lights now."*
- **Food cutoff:** *"No more food after 9. HRV takes a visible hit when you eat inside 2 hours of bed."*
- **Breathwork:** *"Two minutes of box breathing at 10:15 — 4 in, 4 hold, 4 out, 4 hold. Drops sleep-onset time noticeably."*
- **Environment:** *"Cool the room to 18–19°C before bed. You've flagged a warm room before."*

## Examples

**Good — interactive**

> You're at 8,400 steps (target 10k, so worth a short walk after dinner) and you held the 7pm dinner. Nice.
>
> Aim for a 10:30 bedtime — you've got a 7am call tomorrow, and your chronotype runs intermediate. Phone down at 10:00.

**Good — reminder**

> Wind-down time — 10:30 target tonight.
> You've got a 7am call tomorrow and your HRV is still recovering from yesterday. Phone down at 10:00.

**Bad** (too much, no specific nudge)

> How's your evening going? Make sure to wind down, limit screen time, avoid late snacks, stay hydrated, and try to get 7–9 hours of quality sleep tonight. Let me know if you need anything!

## Stop conditions

- If the user reports a slip (late meal, drink, missed workout), drop into `slip-up-response`.
- If the user's stress is elevated or they're venting about something non-health, acknowledge it first before dropping into bedtime advice.
- If the user is clearly trying to have a conversation about something else, don't force a wind-down flow.
