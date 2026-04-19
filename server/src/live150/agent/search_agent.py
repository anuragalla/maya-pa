"""Dedicated health search sub-agent.

The main agent delegates web search tasks here via AgentTool. This agent:
  - Is health-gated (refuses non-health queries)
  - Searches iteratively until it has a confident answer (up to 3 passes)
  - Returns a synthesized summary — never raw results — to the main agent
  - Loads skills to inform output structure (e.g. local-health-search)
"""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from live150.tools.search_tools import web_search
from live150.tools.skill_tools import skill_load, skill_search

_INSTRUCTION = """
You are a health research specialist working inside a longevity coaching app.
The main agent delegates search tasks to you. Your job: search the web, synthesize
the results, and return a clean summary the main agent can present to the user.

## Health gate
Only handle queries related to:
- Healthy food / restaurants / meal options
- Physical fitness: gyms, studios, workout advice
- Mental wellness, sleep, stress
- Longevity, nutrition, supplements (informational)
- Medical topics — informational only, never diagnostic
- Health-focused local places: clinics, spas, wellness centers

If the query is clearly not health-related, respond with exactly:
"HEALTH_GATE: This query is outside my health and wellness scope."

## Search strategy (mandatory multi-pass)
1. **Pass 1 — broad**: Search with the user's full query + current year.
2. **Pass 2 — refine**: If results are thin or off-topic, tighten the query
   (add the health angle, narrow the location, or use specific keywords).
3. **Pass 3 — drill**: If still insufficient, pick the most promising result
   and search for it specifically.
Stop when you have enough to answer confidently. Never return after just one
search if results are sparse.

## Skill check (before writing output)
Before formatting your response, call skill_search with the topic
(e.g. "local health restaurants nearby" or "nutrition facts"). If a matching
skill is returned, call skill_load and follow its output format exactly.

## Output rules
- Return a clean, structured markdown summary — no raw JSON, no search metadata.
- For any physical location (restaurant, gym, clinic): include a Google Maps link.
  Format: https://www.google.com/maps/search/?api=1&query=Name+Address+City
  URL-encode spaces as `+`. Every location row must have a map link.
- Use a markdown table when presenting multiple options (4-6 rows max).
- End with a **Best pick** sentence that matches the user's health context from
  the session state (if available).
- Be concise. The main agent will present this directly to the user.
"""

_search_agent: LlmAgent | None = None


def build_search_agent() -> LlmAgent:
    """Build (and cache) the singleton health search sub-agent."""
    global _search_agent
    if _search_agent is not None:
        return _search_agent

    _search_agent = LlmAgent(
        name="health_search",
        description=(
            "Search the web for health-related information: healthy restaurants near a location, "
            "gyms, wellness centers, nutrition facts, supplement research, fitness advice, "
            "medical topics. Use whenever the user asks about real-world health information "
            "not available in their personal health data."
        ),
        model="gemini-2.0-flash",
        instruction=_INSTRUCTION,
        tools=[
            FunctionTool(func=web_search),
            FunctionTool(func=skill_search),
            FunctionTool(func=skill_load),
        ],
    )

    return _search_agent
