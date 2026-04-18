"""Eval harness runner.

Usage: python -m tests.eval.run_eval

Iterates through golden_dataset.jsonl, runs agent with mocked tools,
scores each example, and writes a summary report.
"""

import json
import logging
import sys
from pathlib import Path

from tests.eval.judges import (
    groundedness_judge,
    safety_judge,
    tone_judge,
    tool_selection_judge,
)

logger = logging.getLogger(__name__)

DATASET_PATH = Path(__file__).parent / "golden_dataset.jsonl"
REPORT_PATH = Path(__file__).parent / "eval_report.json"


def load_dataset() -> list[dict]:
    examples = []
    with open(DATASET_PATH) as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return examples


async def run_single(example: dict) -> dict:
    """Run a single eval example.

    In production, this calls the agent with mocked tools and collects
    the response + tool calls. For now, returns placeholder results.
    """
    # TODO: Wire to actual agent with mocked Vertex responses
    return {
        "id": example["id"],
        "response_text": "(placeholder — agent not wired for eval yet)",
        "tools_called": [],
        "tool_results": [],
    }


async def evaluate() -> dict:
    examples = load_dataset()
    results = []

    for example in examples:
        run_result = await run_single(example)

        # Run judges
        tool_result = await tool_selection_judge(
            example.get("expected_tools", []),
            run_result["tools_called"],
        )
        ground_result = await groundedness_judge(
            run_result["response_text"],
            run_result["tool_results"],
        )
        tone_result = await tone_judge(run_result["response_text"])
        safety_result = await safety_judge(run_result["response_text"])

        results.append({
            "id": example["id"],
            "message": example["message"],
            "tool_selection": {"passed": tool_result.passed, "score": tool_result.score, "reasoning": tool_result.reasoning},
            "groundedness": {"passed": ground_result.passed, "score": ground_result.score, "reasoning": ground_result.reasoning},
            "tone": {"passed": tone_result.passed, "score": tone_result.score, "reasoning": tone_result.reasoning},
            "safety": {"passed": safety_result.passed, "score": safety_result.score, "reasoning": safety_result.reasoning},
        })

    # Summary
    total = len(results)
    tool_pass = sum(1 for r in results if r["tool_selection"]["passed"])
    safety_pass = sum(1 for r in results if r["safety"]["passed"])

    summary = {
        "total_examples": total,
        "tool_selection_pass_rate": tool_pass / total if total else 0,
        "safety_pass_rate": safety_pass / total if total else 0,
        "results": results,
    }

    # Write report
    with open(REPORT_PATH, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nEval complete: {total} examples")
    print(f"  Tool selection: {tool_pass}/{total} ({tool_pass/total*100:.0f}%)")
    print(f"  Safety: {safety_pass}/{total} ({safety_pass/total*100:.0f}%)")
    print(f"\nFull report: {REPORT_PATH}")

    return summary


if __name__ == "__main__":
    import asyncio
    asyncio.run(evaluate())
