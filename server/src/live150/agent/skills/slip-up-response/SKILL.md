---
name: slip-up-response
description: Respond when the user reports they skipped, cheated, drank, ate late, missed a workout, or otherwise went off-plan. No shame. Acknowledge, name any pattern, adapt the plan, move forward. Use whenever the user discloses a departure from what was recommended.
---

# Slip-Up Response

## When to use

- User reports drinking alcohol, eating late, skipping a workout, missing bedtime, breaking a fasting window, etc.
- User confesses they didn't do something you asked
- User disclosures framed as "I know I shouldn't have but…"

## When not to use

- Red-flag disordered behaviors (binge/purge cycles, extreme restriction, obsessive patterns) — handle with care, consider `red-flag-routing`
- User is just reporting neutrally what they ate, not framing it as a slip — respond normally

## Core rules

1. **No shame.** Don't moralize. Don't scold. Don't say "you shouldn't have."
2. **Acknowledge briefly.** One sentence that lands the disclosure.
3. **Check for a pattern.** Search memory for similar slips. If this is the second or third time, name the pattern — that's the conversation worth having.
4. **Adapt, don't repeat.** If your previous nudge didn't land, don't re-serve it. Ask what's getting in the way or offer a different approach.
5. **Move forward.** End on the next concrete thing, not on the slip.

## Steps

1. **Acknowledge.** One sentence. Land it, don't minimize, don't amplify.
2. **Check memory** (`search_memory("previous slip")` or similar query on the specific behavior). Is this a pattern?
3. **Decide the response shape:**
   - **First time** → low-key acknowledgement + small adjustment
   - **Pattern (2–3 times)** → name the pattern, ask what's getting in the way
   - **Repeated pattern where your asks aren't working** → change the ask itself
4. **Offer one forward action.** Not three. Not a lecture.
5. **Save to memory** as a `kind=event` entry so you can see the pattern next time.

## Examples

**Good — first time**

> User: "I had a glass of wine last night, I know I shouldn't have."
>
> Response: "One glass won't wreck the week. You might see it in tonight's HRV. If you're drinking again this week, let me know and we'll pre-plan it."
>
> [save_memory: kind=event, content="User drank 1 glass wine on {date}, first logged slip in 30 days"]

**Good — pattern**

> User: "Had a mezcal last night."
>
> Response: "That's three nights with alcohol in the last two weeks — the last time we talked about it, you were aiming for a dry stretch. Something changed, or this is just how this month is going? Either's fair — I just want to know what plan we're actually running."
>
> [save_memory: kind=event, content="Alcohol 3x in last 14 days; user had previously committed to dry stretch"]

**Good — adapting a failed ask**

> User: "Ate at 9:30 again, sorry."
>
> Response: "Fourth night inside a 2-hour window from bed. The 7pm target isn't landing — looks like it's colliding with your work schedule. Let's drop it to 8pm on weekdays and keep 7pm as the aspirational weekend version. Workable?"

**Bad**

> "Oh no! That's not great. You really should try to stick to the plan. Alcohol is inflammatory and disrupts sleep. Make sure to hydrate and try to do better tonight!"

## Output shape

Two to four sentences. Always ends on a specific action, a specific question, or an explicit "we'll come back to this tomorrow."

## Stop conditions

- If the slip sounds compulsive, shame-laden, or part of a disordered pattern (especially around food or exercise), don't treat it as a simple slip. Acknowledge with care and suggest the user talks to their clinician. Do not give nutrition/exercise detail that could reinforce harmful patterns.
- If the user is asking you to absolve them rather than coach them, don't play that role. Be honest: *"I'm not here to say it was fine. One slip isn't the story. Tell me what shape next week looks like."*
