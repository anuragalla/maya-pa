# Eval Harness

LLM evaluation suite for the Live150 agent.

## Running

```bash
python -m tests.eval.run_eval
```

Not run in CI by default (costs tokens).

## Dataset

`golden_dataset.jsonl` contains test examples with:
- `message`: User input
- `expected_tools`: Tools the agent should call
- `expected_properties`: Properties the response should have

## Judges

- **tool_selection_judge**: Did the agent call the expected tools?
- **groundedness_judge**: Does the response reference real tool data?
- **tone_judge**: Does the response match Live150 tone guidelines?
- **safety_judge**: No unprompted medical claims?
