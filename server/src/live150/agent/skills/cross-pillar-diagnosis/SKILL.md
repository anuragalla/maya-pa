---
name: cross-pillar-diagnosis
description: Diagnose why a health signal is off by reasoning across nutrition, activity, mindfulness, and sleep. Use when the user reports bad sleep, low energy, elevated RHR, low HRV, poor recovery, brain fog, bad mood, or asks "why is X happening". Produces a causal explanation that spans pillars, not a single-pillar answer.
---

# Cross-Pillar Diagnosis

## When to use

- User reports a symptom: bad sleep, low HRV, elevated RHR, low energy, brain fog, bad mood, poor recovery score, trouble concentrating
- User asks "why is X happening" or "why did my Y drop"
- A metric the user tracks moved meaningfully and they want to understand why

## When not to use

- Red-flag medical symptoms (chest pain, fainting, severe anything) — load `red-flag-routing` instead
- Clear single-pillar question like "should I have caffeine now" — answer directly
- User just wants the plan, not the explanation — skip the diagnosis, give the action

## Approach

Health signals are rarely single-cause. The job here is to reason across pillars and give the *most likely* explanation given this user's data, not to hedge with five possibilities.

### Step 1 — Pull the relevant data

For the reported signal, fetch the last 3–7 days across the pillars most likely to be upstream. Defaults:

- **Bad sleep** → late eating, alcohol, caffeine timing, stress events, bedroom environment, workout timing
- **Low HRV** → sleep debt, alcohol, stress, overtraining, illness onset
- **Low energy / fatigue** → sleep consistency, hydration, undereating, Zone 2 volume vs. strength ratio
- **Elevated RHR** → illness, alcohol, dehydration, stress, overtraining
- **Brain fog / bad mood** → sleep, blood sugar stability, social contact, outdoor time, movement

### Step 2 — Look for the thread

Walk through the data and find the **one or two** most plausible upstream causes. Don't list five things that could be true. Commit to the most likely, and name your second-most-likely only if it's meaningfully close.

### Step 3 — Explain the mechanism

One sentence on *why* the cause produces the effect. Keep it plain: *"Alcohol suppresses REM sleep for the second half of the night; that's what you're seeing in your stages."*

### Step 4 — Give one action

What to do differently tonight or tomorrow. Not a lecture — one specific change.

## Output shape

Three short paragraphs:

1. **The signal and the most likely cause.** One to two sentences.
2. **The mechanism.** One sentence.
3. **The action.** One specific change.

Optional fourth paragraph: a secondary candidate cause if it's within striking distance of the primary. Skip otherwise.

## Examples

**Good**

> Your HRV dropped 18% over the last three nights. Best fit for the cause: the 10pm dinners Thursday and Friday plus the mezcal Saturday.
>
> Eating inside two hours of bed keeps your body in digestion mode when it should be in recovery mode; alcohol compounds it by suppressing REM.
>
> Tonight: dinner at 7, water only. HRV should start recovering within 48 hours.

**Good (with secondary cause)**

> Low energy this week lines up with your sleep consistency — bedtime drifted 90 minutes across Tue–Fri. Cortisol didn't get the cue it wanted.
>
> Inconsistent sleep timing shifts your circadian rhythm more than total hours do, which is why "I slept 8 hours" can still feel bad.
>
> Lock tonight's bedtime within 30 minutes of your weeknight target.
>
> One thing I can't rule out: your Zone 2 volume doubled last week. If the fatigue persists after two good nights, we'll drop a session.

**Bad** (too many causes, no commitment)

> Your HRV could be low due to: sleep, alcohol, stress, overtraining, illness, hydration, caffeine, or just normal variance. Try to sleep better and stay hydrated.

## Stop conditions

- If the symptom is red-flag (sharp chest pain, breathing issues, fainting, suicidal ideation): stop, load `red-flag-routing`.
- If the data clearly points to illness onset (RHR up, HRV down, subjective fatigue, maybe temperature), say it: *"This pattern usually means your body is fighting something. Rest today."*
- If you genuinely can't find a cause in the data, say so: *"I don't see an obvious upstream cause in your last week. If this continues, it might be worth a check-in with your doctor."*
