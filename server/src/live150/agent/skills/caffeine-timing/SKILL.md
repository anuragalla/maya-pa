---
name: caffeine-timing
description: Answer questions about caffeine, coffee, matcha, tea, or pre-workout — including "can I have a coffee now", "why am I still tired after coffee", "should I cut caffeine". Gives a personalized, time-aware answer based on the user's bedtime target and caffeine sensitivity.
---

# Caffeine Timing

## When to use

- User asks about coffee, tea, matcha, caffeine, pre-workout, energy drinks
- User reports afternoon energy crashes and wants advice
- User asks whether to have caffeine at a specific time
- User reports trouble sleeping and caffeine might be upstream

## When not to use

- User is asking about medication-related stimulants (not food/drink caffeine) — defer to clinician
- User reports caffeine-triggered anxiety or arrhythmia — acknowledge and suggest they talk to a doctor

## The core math

- **Caffeine half-life** is roughly 5–6 hours for most adults. Slow metabolizers can be 8+.
- **50% still in system at T+5h, 25% at T+10h** for average metabolizers.
- **Sleep threshold** is where you want blood caffeine near zero by bedtime. Rule: last caffeine ≥8 hours before target bedtime for most users, ≥10 hours for slow metabolizers or people who sleep lightly.
- **Adenosine clearance** is why an afternoon coffee feels like it "works" but can still wreck deep sleep even when you fall asleep fine.

## Inputs you need

1. User's target bedtime (from profile or recent brief)
2. Current local time
3. What they've already had today (meal log or ask)
4. Caffeine sensitivity from memory — search `"caffeine sensitivity"` or `"slow metabolizer"`
5. Today's HRV / sleep debt if this is about "should I have more coffee"

## How to answer

### "Can I have a coffee now?"

- Compute: `(target_bedtime - now).hours`
- **≥10h** → yes, no caveats. "Go ahead."
- **7–10h** → yes, but note it's the last window. Suggest a smaller dose if they're on their second+ coffee.
- **5–7h** → risky. Suggest matcha / green tea or decaf. Explain the half-life reason briefly.
- **<5h** → no. Recommend an alternative: light walk outside, cold water, 10-min nap if feasible.

### "Why am I still tired after coffee?"

Most common causes, in order:
1. **Sleep debt is deeper than caffeine can mask** — check sleep trend.
2. **Dehydration** — ask.
3. **Blood sugar crash** after a carb-heavy meal — check nutrition if logged.
4. **Adenosine buildup from poor sleep** — caffeine blocks but doesn't clear.
5. **Caffeine tolerance** — if >3 cups/day regularly, yes this is a thing.

Give the top one or two based on their actual data.

### "Should I cut caffeine?"

Relative, not absolute. Not for everyone. Ask:

- Is sleep consistently disrupted?
- Afternoon anxiety or jitters?
- HRV suppressed on coffee days vs. non-coffee days (check trend)?

If yes to multiple → suggest a gradual taper (half-caf for a week, then matcha, then assess). Don't suggest cold turkey — the withdrawal is real and counterproductive.

## Output shape

Two to four sentences. Commit to an answer. Don't hedge.

## Examples

**Good — "can I have a coffee at 3pm"**

> You're at ~7.5 hours to your 10:30 target. It's the edge of the window. Fine if this is your first or second cup — I'd skip it if it's your third. Matcha's a cleaner option here if you want the nudge without the hit to deep sleep.

**Good — "why am I still tired after coffee"**

> Two reasons likely. You're at 6h 12m average this week, which is deep enough sleep debt that caffeine can't paper over it. And your HRV trend suggests you're under-recovered from the two strength sessions back-to-back. Drink water; if you're not better by 3pm, take a 20-min walk outside.

**Good — "should I cut caffeine"**

> Relative to your current pattern, I don't think full removal helps you. Half-caf for two weeks and see what HRV does. If sleep consistency improves materially, we go further. If not, caffeine isn't your lever.

**Bad** (vague, hedged, generic)

> Caffeine affects everyone differently. Try to have it earlier in the day. Listen to your body. Maybe try decaf sometimes!

## Stop conditions

- If user reports heart symptoms after caffeine (palpitations, chest discomfort), pause: *"That's a real signal — worth checking with your doctor. In the meantime, hold off on caffeine."*
- If user is pregnant or nursing, default to the conservative range and defer to clinician.
