"""Dedicated health document analyst sub-agent.

The APScheduler worker and (later) the main agent delegate document
analysis here. This agent:
  - Runs on Gemini 3.1 Pro for vision + reasoning quality (model isolation
    is the entire point of wrapping it as an AgentTool)
  - Receives one PDF or image per invocation via a gs:// Part reference
  - Pulls the user's goals and recent baselines before summarizing
  - Emits a single JSON object matching `DocAnalysis` — the processor
    Pydantic-validates the string on the way out
"""

import logging
from datetime import date
from typing import Literal

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from pydantic import BaseModel, Field

from live150.tools.health_api import get_health_goals, get_holistic_analysis

logger = logging.getLogger(__name__)


class Marker(BaseModel):
    name: str
    value: float | str
    unit: str | None = None
    range_low: float | None = None
    range_high: float | None = None


class DocAnalysis(BaseModel):
    doc_type: Literal[
        "lab_result",
        "prescription",
        "insurance",
        "imaging",
        "visit_note",
        "vaccine",
        "other",
    ]
    summary_detailed: str = Field(..., description="300-600 word narrative for main-agent recall")
    extracted_text: str = Field(..., description="Full transcription, preserve tables where possible")
    tags: list[str] = Field(default_factory=list)
    structured: dict = Field(default_factory=dict)
    expiry_alert_date: date | None = None


_DOC_INSTRUCTION = """
You are a medical document analyst inside the Maya longevity coaching app.
You analyze exactly one health document per invocation and return a single
structured JSON object matching the `DocAnalysis` schema. No prose before or
after the JSON.

## Input
Each invocation gives you:
- A file part (PDF or image) referenced by gs:// URI — the document itself.
- A short text part with optional hints: original filename and any user-supplied
  note (e.g. "lab from Quest, Oct 2024").

## Mandatory pre-write steps
Before composing `summary_detailed`, call BOTH:
1. `get_health_goals` — the user's stated longevity targets.
2. `get_holistic_analysis` — recent baselines and trends.
Use these to contextualize every finding. If a call fails, proceed but note
the gap in `summary_detailed`.

## Output fields

### doc_type
Choose the single best fit: `lab_result`, `prescription`, `insurance`,
`imaging`, `visit_note`, `vaccine`, `other`. Use `other` only when the
document is genuinely outside those categories or unreadable.

### summary_detailed
300-600 words, written for the main coaching agent to recall in future turns.
Structure:
(a) One-line doc identity — what this document is, who issued it, date.
(b) 3-6 key findings with numeric values and units.
(c) Comparison to the user's goals and recent trends — cite both sides
    explicitly ("LDL 142 vs user's stated target of <100, up from 128 in
    the July holistic baseline").
(d) Any flags: out-of-range markers, missing data, inconsistencies.
(e) Concrete next-step facts: prescription refill dates, follow-up
    recommendations stated in the doc, expiration windows.

### extracted_text
Full transcription of the document. Preserve table structure using markdown
tables where helpful. Keep section headers. Do not summarize — this is the
raw record for future re-analysis.

### tags
2-5 short lowercase tags, hyphenated. Examples:
`["lipid-panel", "cholesterol", "ldl-elevated"]`,
`["statin", "rosuvastatin", "refill-due"]`.

### structured
Shape depends on `doc_type`:
- `lab_result`: `{"markers": [{"name", "value", "unit", "range_low", "range_high"}, ...]}`
- `prescription`: `{"drug": str, "dose": str, "frequency": str, "fill_date": "YYYY-MM-DD", "days_supply": int}`
- `insurance`: `{"carrier", "plan", "member_id", "group_id", "effective_date", "expiration_date"}`
- `imaging`: `{"modality", "body_region", "impression"}`
- `visit_note`: `{"provider", "visit_date", "chief_complaint", "assessment"}`
- `vaccine`: `{"vaccine", "dose_number", "administered_date", "next_due"}`
- `other`: whatever structured facts make sense, or `{}`.

### expiry_alert_date
- For `prescription`: compute as `fill_date + days_supply - 7 days`
  (ISO YYYY-MM-DD). Skip if either field is absent.
- For everything else: `null`.

## Constraints
You are not giving medical advice. Describe what the document says and how
it compares to the user's stated data. Avoid directives like "you should X".
Never invent values that are not present in the document. If a marker is
unreadable, omit it rather than guess.

## Failure mode
If the document is unreadable, corrupted, or clearly not a health document:
- `doc_type`: `"other"`
- `summary_detailed`: explain the issue plainly, cite what little is visible
- `extracted_text`: whatever you can salvage (may be empty)
- `structured`: `{}`
- `tags`: `["unreadable"]` or similar
- `expiry_alert_date`: `null`
"""

_doc_agent: LlmAgent | None = None


def build_doc_agent() -> LlmAgent:
    """Build (and cache) the singleton medical document analyst sub-agent."""
    global _doc_agent
    if _doc_agent is not None:
        return _doc_agent

    # ADK's `output_schema` is mutually exclusive with tools (see LlmAgent
    # docstring); we need get_health_goals + get_holistic_analysis, so we use
    # `output_key` and let the processor Pydantic-validate the JSON string.
    _doc_agent = LlmAgent(
        name="doc_analyst",
        description=(
            "Analyze a single health document (PDF/image): lab results, "
            "prescriptions, visit notes, imaging, insurance, vaccines. "
            "Compares findings to the user's goals and recent trends and "
            "emits structured JSON (detailed summary, extracted markers, "
            "tags, expiry dates). Delegate here for any document analysis "
            "instead of answering from the main agent's context."
        ),
        model="gemini-3.1-pro-preview",
        instruction=_DOC_INSTRUCTION,
        tools=[
            FunctionTool(func=get_health_goals),
            FunctionTool(func=get_holistic_analysis),
        ],
        output_key="doc_analysis",
    )

    logger.info("DocAgent built", extra={"model": "gemini-3.1-pro", "tool_count": 2})
    return _doc_agent
