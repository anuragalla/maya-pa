---
name: travel-day-plan
description: Adapt the plan for travel days, flights, jet lag, or time zone changes. Use when the user mentions a flight, trip, hotel, jet lag, or "out of routine". Covers pre-flight prep, in-flight behavior, arrival adjustment, and recovery. Short, specific, time-zone-aware.
---

# Travel Day Plan

## When to use

- User mentions an upcoming flight, trip, time zone change, or hotel stay
- User asks about jet lag, long-haul, red-eye
- User reports they're traveling this week and asks how to keep the routine going
- Calendar (if connected) shows a travel block

## When not to use

- Short drives, day trips in the same time zone
- User's question is really about something else (eating out, missing gym) — use those skills instead

## Inputs you need

1. **Origin and destination time zones** — ask if not stated
2. **Flight time and direction** (east vs west matters a lot)
3. **Purpose** (work, family, holiday) — sets expectation for adherence
4. **Length of stay** — determines whether to try to adapt to destination or stay on origin time

## Rules of thumb

- **Direction matters.** Eastbound is harder than westbound because you're shortening the day. East = hardest jet lag. West = go-to-bed-early problem.
- **<3 days at destination** → stay on origin time zone as much as possible. Don't adapt.
- **≥3 days** → adapt. Start the shift 1–2 days before the flight.
- **Light exposure is the primary tool.** Food timing is secondary. Melatonin is tertiary and the user should talk to their clinician before using it regularly.
- **Caffeine is a weapon.** Use it to stay up or skip it to sleep — but don't use it blindly.

## Output shape

Depending on when they're asking:

### Pre-flight (more than 24h out)

Three short blocks: **Before you fly**, **On the plane**, **When you land**. Each is 2–3 bullets, specific.

### Day-of / in-flight

Just the immediate next thing. Don't give a full plan — they're already traveling. One action.

### Arrived already

Two-part: **Tonight** (sleep target in local time, light exposure, no caffeine after X) and **Tomorrow** (morning light, first meal timing).

## Examples

**Good — eastbound long-haul, pre-flight**

> BLR → SFO, 13 hours ahead becomes 11.5 hours behind. Direction is east then west — the west leg is the forgiving one.
>
> Before you fly:
> - Sleep 30 min earlier tonight. Hydrate aggressively.
> - No caffeine after 2pm day before.
>
> On the plane:
> - Set your watch to SFO when you board. Eat and sleep on that clock from then on.
> - No alcohol. Water every hour.
>
> When you land (evening SFO time):
> - Outdoor light within 30 min of arrival, even if it's grey. Skip caffeine after 2pm local.
> - Aim for 11pm local bedtime. Don't nap past 20 minutes before then.

**Good — 2-day business trip, stay on origin time**

> Two days isn't worth adapting for. Keep your BLR schedule — eat when you'd eat at home, sleep when you'd sleep. You'll be a little off for the meetings; it's better than being wrecked for a week after.

**Good — already landed**

> Tonight: outdoor light before 8pm local. Dinner at 7. Bed at 10:30 local, no later than 11. Phone down at 10.
>
> Tomorrow morning: 10 minutes of outdoor light before 9am, even if you're foggy. That's your circadian reset.

## Stop conditions

- If the user has a condition that complicates travel (diabetes with insulin timing, a sleep disorder, pregnancy), flag it: *"For your schedule with insulin, your endocrinologist should weigh in on meal timing across this flight. I can give you the sleep and light side."*
- If the user is anxious about flying itself, acknowledge that before giving logistics.

## Follow-up

Save to memory:

```
kind=event
content="Travel: {origin} → {destination}, {dates}, purpose={work/family/etc}"
```

So next travel conversation can reference it.
