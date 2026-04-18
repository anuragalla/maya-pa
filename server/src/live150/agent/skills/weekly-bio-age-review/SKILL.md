---
name: weekly-bio-age-review
description: Produce the user's weekly review. Use when the user asks for a "weekly review", "how was my week", "what moved my bio age", or on the configured weekly review day. Covers what moved the biological age / trend needle, what didn't, and proposes exactly one concrete change for next week.
---

# Weekly Bio-Age Review

## When to use

- User asks for a weekly review, weekly summary, or "how was my week"
- User asks what's working or what to change
- On the configured review day (usually Sunday evening or Monday morning)

## When not to use

- Daily context (use `daily-morning-brief` or `evening-wind-down`)
- User just wants yesterday's recap — that's a brief, not a review

## Inputs you need

1. 7-day summaries across all four pillars:
   - `get_sleep_summary(days=7)`
   - `get_activity_summary(days=7)`
   - `get_meal_log(days=7)` (or a nutrition summary endpoint if available)
   - Mindfulness / stress signal if tracked
2. Adherence notes from memory for the past week — search `"adherence"` and the prior week's plan
3. Biological age reading from wearable if present, compared to previous reading
4. Last week's plan from memory — what did you ask of them?

## Output shape

Four sections, in this order. Each section is 2–4 sentences. Use H3 headers.

### What moved the needle
- The signal you saw this week — bio age delta, HRV trend, sleep consistency, whatever is most salient.
- Name the specific behavior that drove it if you can.

### What didn't land
- One to two things that didn't. Name them plainly.
- No shame. No "but that's okay". Just what happened.

### The one change for next week
- Exactly one change. Not three.
- It's the smallest change with the highest expected impact given their data.
- State it as a specific behavior with a specific trigger: "Move dinner to 7pm on weekdays. Weekends stay flexible."

### What we're holding
- One or two things that worked and should stay.
- Keeps the next week from being a full rewrite.

## Examples

**Good**

> ### What moved the needle
> Bio age dropped 0.2y this week — your HRV held above baseline 5 of 7 days, the best stretch in a month. That tracks with the 7pm dinner holding on weekdays.
>
> ### What didn't land
> Weekend sleep consistency cratered — you were 2+ hours off your weekday bedtime both nights. Saturday's drink didn't help.
>
> ### The one change for next week
> Weekend bedtime within 60 min of your weekday target. Don't touch anything else. One drink max on Saturday if you're drinking.
>
> ### What we're holding
> 7pm weekday dinners. Two strength sessions. Keep both.

**Bad** (too many changes, no prioritization)

> This week you could do better on: sleep consistency, alcohol, step count, strength volume, Zone 2, meditation. Try to improve all of these. Great job overall!

## Stop conditions

- If you don't have at least 4–5 days of data, skip the bio-age framing and do a lighter summary. Say why: *"With only 3 days of data I can't give you a proper weekly picture yet."*
- If the user's week was clearly disrupted (illness, travel, bereavement), drop the metric focus and ask how they're doing.

## Follow-up

After sending the review, save to memory:

```
kind=note
content="Week of {date}: change for coming week = {the one change}. Holding: {held items}."
```

This is what you'll check against next week when you judge adherence.
