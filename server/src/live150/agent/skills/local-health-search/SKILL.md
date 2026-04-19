---
name: local-health-search
description: Find healthy restaurants, gyms, wellness spots, or health services near a location. Use when the user asks "healthy restaurants near X", "best salad place near Y", "gym near Z", "where can I eat healthy around [station/area/city]", or any query combining a location with a health/food/fitness topic.
---

# Local Health Search

## When to use

- User asks for healthy food options near a location ("healthy restaurants near Grand Central", "good salad spot in Midtown")
- User wants to find a gym, yoga studio, or wellness center near them
- User is traveling and needs health-conscious options nearby
- User asks "what can I eat around here that won't wreck my progress"

## When not to use

- User is asking about their own health data — use `get_holistic_analysis` or `get_progress_by_date` instead
- User wants meal planning or recipes — that's a different skill
- Location is vague ("somewhere in the US") — ask for a specific neighborhood or landmark first

## Inputs you need

1. **Location** — a landmark, neighborhood, zip code, or address. Prompt if missing.
2. **Health goal context** — pull from user profile (weight loss, longevity, plant-based, etc.). Tailor the search to it.
3. **Meal type / timing** — breakfast, lunch, dinner, or snack (affects what's open and relevant)

## Search strategy — two-pass

This skill requires **two searches** to produce a good answer. Do not respond after only one.

### Pass 1 — Broad discovery
Query pattern: `healthy restaurants near [landmark or neighborhood] [city] [current year]`

Goal: Get a list of candidate places from authoritative sources (TripAdvisor, Infatuation, Eater, Yelp, OpenTable).

### Pass 2 — Refinement
Take the top 3–5 names from Pass 1 and search for specifics:
Query pattern: `[name1] [name2] [name3] healthy menu [city]`

Goal: Confirm the spots are actually healthy (not just marketed as such), get hours, distance, and menu highlights relevant to the user's goals.

If Pass 2 results are thin or contradictory, run a third targeted search on the most promising single option.

## Output shape

A short table (4–6 rows max) followed by one **Best pick** sentence that accounts for the user's health profile.

| Restaurant | Type | Why it fits your goals | Map |
|---|---|---|---|
| **Name** (address) | Cuisine/style | Specific healthy items + hours | [Open in Maps](https://www.google.com/maps/search/?api=1&query=Name+Address+City) |

**Google Maps link format** — always use this URL pattern, URL-encoding spaces as `+`:
```
https://www.google.com/maps/search/?api=1&query=Restaurant+Name+Full+Address
```
If you only have the restaurant name and neighborhood (no street address), use:
```
https://www.google.com/maps/search/?api=1&query=Restaurant+Name+Neighborhood+City
```
Never omit the map link. Every row in the table must have one.

Then the Best pick: one sentence naming the winner and why it's the right call for this user specifically.

## Tailoring to user profile

Read `user_profile_summary` from session state before forming the query. Adjust search terms:
- Longevity / anti-inflammatory → add "anti-inflammatory", "whole food", "plant-forward"
- Weight loss → add "low-calorie", "high-protein", "macro-friendly"
- Plant-based → add "vegan", "plant-based"
- High HRV / athlete → add "high-protein", "recovery meals"

## Stop conditions

- If the location is outside a major metro and search results are thin after two passes, say so and offer to search for meal-prep delivery instead.
- If the user's goal conflicts with what's available ("I only eat raw vegan but I'm in a highway rest stop"), be honest: acknowledge the constraint, give the closest option, suggest a backup (grocery store, delivery).
- Never fabricate hours or addresses. If the result doesn't clearly state them, omit rather than guess.

## Follow-up

After delivering results, offer to:
- Save the top pick to memory: `kind=preference content="Healthy go-to near [location]: [restaurant name]"`
- Set a reminder if the user says they'll go today
