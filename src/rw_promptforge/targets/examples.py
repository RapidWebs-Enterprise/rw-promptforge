"""Few-shot example dataset loader (FPO-style).

Loads labeled examples from JSONL, matching the Gemini few-shot optimizer's
DataFrame shapes:

Target-response shape (one JSON object per line)::

    {"prompt": "...", "model_response": "...", "target_response": "..."}

Rubrics shape::

    {"prompt": "...", "model_response": "...",
     "rubrics": ["is English", "under 50 words"],
     "rubrics_evaluations": [true, false]}

Also supports ``reason`` (optional) — a short note on why the model response
missed expectations, used to enrich the reflector's gap-bridging context.
"""

from __future__ import annotations

import json
from pathlib import Path

from rw_promptforge.datastore.models import FewShotExample


class ExampleFormatError(ValueError):
    """Raised when an example row is malformed."""


def load_examples(path: str | Path) -> list[FewShotExample]:
    """Load few-shot examples from a JSONL file.

    Raises:
        FileNotFoundError: the file does not exist.
        ExampleFormatError: a row is not a valid example (bad JSON, missing
            ``prompt``, or neither a target response nor rubrics).
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Examples file not found: {file_path}")

    examples: list[FewShotExample] = []
    for line_no, raw in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExampleFormatError(f"Line {line_no}: invalid JSON: {exc}") from exc

        if not isinstance(row, dict) or not row.get("prompt"):
            raise ExampleFormatError(f"Line {line_no}: missing required 'prompt' field")

        example = FewShotExample(prompt=str(row["prompt"]))
        example.model_response = str(row.get("model_response", ""))
        example.target_response = str(row.get("target_response", ""))

        rubrics = row.get("rubrics")
        evals = row.get("rubrics_evaluations")
        if rubrics is not None:
            if not isinstance(rubrics, list) or not all(isinstance(r, str) for r in rubrics):
                raise ExampleFormatError(f"Line {line_no}: 'rubrics' must be a list of strings")
            example.rubrics = rubrics
        if evals is not None:
            if not isinstance(evals, list) or not all(isinstance(e, bool) for e in evals):
                raise ExampleFormatError(
                    f"Line {line_no}: 'rubrics_evaluations' must be a list of booleans"
                )
            example.rubrics_evaluations = evals

        if example.is_target_shape and example.rubrics:
            # Both shapes present — rubrics take precedence (they carry more signal)
            example.target_response = ""

        if not (example.is_target_shape or example.is_rubrics_shape):
            raise ExampleFormatError(
                f"Line {line_no}: example must provide 'target_response' "
                "or 'rubrics'/'rubrics_evaluations'"
            )

        examples.append(example)

    if not examples:
        raise ExampleFormatError(f"No examples found in {file_path}")

    return examples


def summarize_examples(examples: list[FewShotExample]) -> str:
    """Human-readable summary for CLI display and audit logging."""
    n_target = sum(1 for e in examples if e.is_target_shape)
    n_rubrics = sum(1 for e in examples if e.is_rubrics_shape)
    hit_rates = [e.rubric_hit_rate() for e in examples if e.is_rubrics_shape]
    avg_hit = sum(hit_rates) / len(hit_rates) if hit_rates else 0.0
    return (
        f"{len(examples)} examples "
        f"({n_target} target-response, {n_rubrics} rubrics) · "
        f"rubric hit rate {avg_hit:.0%}"
    )
