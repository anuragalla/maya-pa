"""Skill search and load tools.

Skills are markdown runbooks in server/src/live150/agent/skills/<name>/SKILL.md.
Each has YAML frontmatter with `name` and `description`. The agent calls
skill_search to find relevant skills, then skill_load to get the full body.

Search uses simple keyword matching over the description field. When pgvector
is available, this can be upgraded to hybrid search — but keyword works fine
for 10 skills.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent.parent / "agent" / "skills"


@dataclass
class SkillEntry:
    name: str
    description: str
    path: Path


# In-memory index built at import time
_index: list[SkillEntry] = []


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML frontmatter from a markdown file."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    frontmatter = {}
    for line in match.group(1).strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()
    return frontmatter


def _build_index() -> list[SkillEntry]:
    """Scan the skills directory and build the index."""
    entries = []
    if not _SKILLS_DIR.exists():
        logger.warning("Skills directory not found", extra={"path": str(_SKILLS_DIR)})
        return entries

    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        text = skill_file.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        name = fm.get("name", skill_dir.name)
        description = fm.get("description", "")
        entries.append(SkillEntry(name=name, description=description, path=skill_file))

    logger.info("Skills indexed", extra={"count": len(entries)})
    return entries


def _ensure_index() -> list[SkillEntry]:
    global _index
    if not _index:
        _index = _build_index()
    return _index


def _score(query: str, description: str) -> float:
    """Simple keyword overlap score."""
    query_words = set(query.lower().split())
    desc_words = set(description.lower().split())
    if not query_words:
        return 0.0
    overlap = query_words & desc_words
    return len(overlap) / len(query_words)


async def skill_search(query: str, limit: int = 3, tool_context=None) -> dict:
    """Search for relevant skill runbooks by keyword.

    Skills are detailed procedures for multi-step tasks: morning briefs,
    weekly reviews, fasting plans, travel days, slip-up handling, etc.
    Use this when the user's question fits a repeatable procedure.

    Args:
        query: What you're looking for (e.g., "morning brief", "fasting window", "travel day").
        limit: Max results (default 3).
    """
    index = _ensure_index()

    scored = [(entry, _score(query, entry.description)) for entry in index]
    # Also boost exact name match
    for i, (entry, score) in enumerate(scored):
        if query.lower().replace(" ", "-") in entry.name or entry.name.replace("-", " ") in query.lower():
            scored[i] = (entry, score + 0.5)

    scored.sort(key=lambda x: x[1], reverse=True)
    top = [(e, s) for e, s in scored[:limit] if s > 0]

    if not top:
        return {"results": [], "message": "No matching skills found."}

    return {
        "results": [
            {"name": e.name, "description": e.description, "score": round(s, 2)}
            for e, s in top
        ]
    }


async def skill_load(skill_name: str, tool_context=None) -> dict:
    """Load the full body of a skill runbook by name.

    Call skill_search first to find the right skill, then load it.
    The body contains the step-by-step procedure, inputs needed,
    output format, stop conditions, and examples.

    Args:
        skill_name: Exact skill name from skill_search results (e.g., "daily-morning-brief").
    """
    index = _ensure_index()

    entry = next((e for e in index if e.name == skill_name), None)
    if entry is None:
        return {"error": True, "message": f"Skill '{skill_name}' not found. Use skill_search to find available skills."}

    text = entry.path.read_text(encoding="utf-8")

    # Strip frontmatter — agent only needs the body
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)

    return {"name": entry.name, "body": body.strip()}
