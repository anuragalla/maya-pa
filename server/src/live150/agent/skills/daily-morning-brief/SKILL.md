---
name: daily-morning-brief
description: Produce the user's two-paragraph morning briefing. Use when the user asks "how did I do", "morning brief", "what's the plan today", "how did I sleep", or at the start of a day. Covers all four pillars briefly with one explicit set of actions for today. Forward-looking, not retrospective.
---

# Daily Morning Brief

## When to use

- User's first interactive message of the day
- User explicitly asks for a brief, summary, or "how did I do"
- A morning reminder fires and you're generating the push

## When not to use

- Mid-day catch-up (use `evening-wind-down` if late afternoon, or answer directly)
- User asked a specific question (answer the question, don't overwrite with a brief)

## Inputs you need

Before writing, make sure you have:

1. Last night's sleep (`get_sleep_summary(days=1)`)
2. Yesterday's activity (`get_activity_summary(days=1)`)
3. Recovery / HRV reading if the user's devices provide it
4. Today's calendar load (only if Google Calendar is connected — otherwise skip)
5. Active plan from `user_profile_summary`

If any of the first two are missing, ask in one line: *"I can't pull your sleep from last night — how did it feel, rough scale 1–10?"* and work from the qualitative answer.

## Output shape

Exactly two paragraphs. No headers. No bullets in the first paragraph.

**Paragraph 1 — what happened, with the causal thread**
- Lead with sleep (one sentence with hours + a qualitative read).
- Add HRV or recovery in one clause if meaningful.
- Link to a cause from yesterday if one is obvious (late meal, alcohol, stress event, travel).

**Paragraph 2 — three actions, ranked**
- Three bullets. Each starts with a verb. Each is concrete: a time, a swap, a number.
- First bullet is the one that will move the needle most today.
- At most one bullet that offers to set a reminder.

## Examples

**Good**

> Sleep was 6h 42m — 48 minutes short of your target, and HRV is down 12% from baseline. That tracks with the 10pm dinner last night; your body was still digesting when you tried to sleep.
>
> Today:
> - Push dinner to 7pm. You've been drifting late four nights running.
> - Swap the afternoon espresso for matcha; caffeine half-life is working against you this week.
> - Want me to set a 9:45 wind-down reminder for a 10:30 target?

**Bad** (too long, no causal link, no ranking)

> Great morning! Your sleep was 6h 42m. Your HRV is down. Your steps yesterday were 7,200. Make sure to get good sleep, eat well, and stay active today! Let me know if you have any questions!

## Stop conditions

- If the user is in a red-flag situation (reports symptoms, self-harm language), abandon the brief and load `red-flag-routing`.
- If the user asks a specific question instead of a brief, drop the brief and answer the question directly.

## Reminder-turn variant

When `turn_context == "reminder"`, collapse to a single push:

- Line 1: the key insight or ask, ≤80 characters.
- Lines 2–3: the reason and one action.

Example: *"Your sleep is trending short again. Bedtime's drifted 90 min this week — try a 10:30 target tonight. I can set a wind-down at 9:45."*
