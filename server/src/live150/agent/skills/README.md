# Live150 — skills/

Each skill is a self-contained runbook the agent can load on demand. Structure follows the AgentSkills / OpenClaw convention: a folder named after the skill, containing a `SKILL.md` with YAML frontmatter (`name`, `description`) and a markdown body.

## How the agent finds skills

The agent calls `skill_search(query: str)` when it needs a procedure. The search uses hybrid BM25 + pgvector over the `description` field in the frontmatter — so **the description is everything**. Write it like a search query including the trigger phrases a user would actually say.

The body of the skill loads only after the skill is selected. This keeps token overhead low at the prompt-assembly stage.

## Index

| Skill | Use when |
|---|---|
| `daily-morning-brief` | User asks "how did I do" / "morning brief" / starts the day |
| `evening-wind-down` | User asks "how am I doing today" late in day, or evening reminder fires |
| `weekly-bio-age-review` | User asks for a weekly review / it's review day |
| `cross-pillar-diagnosis` | User reports a symptom (bad sleep, low energy, bad HRV) and wants to know why |
| `slip-up-response` | User reports they skipped, cheated, drank, ate late, missed a workout |
| `travel-day-plan` | User mentions travel, a flight, jet lag, or being out of routine |
| `caffeine-timing` | User asks about coffee, matcha, caffeine, pre-workout, or afternoon energy |
| `fasting-window` | User asks about intermittent fasting, eating windows, or meal timing |
| `alcohol-guidance` | User asks whether/how much they can drink, or reports drinking |
| `red-flag-routing` | User reports something medical/urgent — chest pain, self-harm, severe symptoms |

## Writing new skills

- Keep the body short. Skills are checklists, not essays.
- Lead with *when to use* and *when not to use*.
- Stop conditions matter. Say when the agent should bail.
- Say what the output should look like. If the skill produces a notification vs. a chat response vs. a multi-step plan, be explicit.
- Don't repeat SOUL.md or AGENTS.md — skills are procedural, not personality.
