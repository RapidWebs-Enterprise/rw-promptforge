"""Pluggable programmatic evaluation metrics (data-driven optimizer style).

Mirrors the Gemini data-driven optimizer's selectable metric palette. All
metrics return scores in [0, 1] where higher is better.

Metrics provided:
- ``exact_match``      — exact string match vs gold target (normalized)
- ``rouge_l``          — ROUGE-L F-measure (longest common subsequence)
- ``rouge_2``          — ROUGE-2 F-measure (bigram overlap)
- ``bleu``             — BLEU-1/2 geometric mean with brevity penalty
- ``tool_call_valid``  — fraction of outputs that parse as valid tool calls

The generic LLM judge (``MetricType.LLM``) is handled by the existing
evaluator; this module covers only the programmatic palette.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter

from rw_promptforge.datastore.models import MetricType


# ── Helpers ────────────────────────────────────────────────────────────


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _tokenize(text: str) -> list[str]:
    return _normalize(text).split()


def _lcs_length(a: list[str], b: list[str]) -> int:
    """Longest common subsequence length via DP (iterative, O(n*m) memory-light)."""
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        curr = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    return prev[-1]


def _ngrams(tokens: list[str], n: int) -> Counter:
    return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


# ── Metric implementations ─────────────────────────────────────────────


def exact_match(prediction: str, reference: str) -> float:
    """1.0 if normalized strings are identical, else 0.0."""
    return 1.0 if _normalize(prediction) == _normalize(reference) else 0.0


def rouge_l(prediction: str, reference: str) -> float:
    """ROUGE-L F-measure over token sequences."""
    pred = _tokenize(prediction)
    ref = _tokenize(reference)
    if not pred or not ref:
        return 0.0
    lcs = _lcs_length(pred, ref)
    precision = lcs / len(pred)
    recall = lcs / len(ref)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def rouge_2(prediction: str, reference: str) -> float:
    """ROUGE-2 F-measure over bigram overlap."""
    pred = _tokenize(prediction)
    ref = _tokenize(reference)
    if len(pred) < 2 or len(ref) < 2:
        return 0.0
    pred_bigrams = _ngrams(pred, 2)
    ref_bigrams = _ngrams(ref, 2)
    overlap = sum((pred_bigrams & ref_bigrams).values())
    if overlap == 0:
        return 0.0
    precision = overlap / sum(pred_bigrams.values())
    recall = overlap / sum(ref_bigrams.values())
    return 2 * precision * recall / (precision + recall)


def bleu(prediction: str, reference: str, max_n: int = 2) -> float:
    """BLEU with 1-gram and 2-gram precision, geometric mean, brevity penalty."""
    pred = _tokenize(prediction)
    ref = _tokenize(reference)
    if not pred or not ref:
        return 0.0

    precisions: list[float] = []
    for n in range(1, max_n + 1):
        pred_ngrams = _ngrams(pred, n)
        ref_ngrams = _ngrams(ref, n)
        total = sum(pred_ngrams.values())
        if total == 0:
            precisions.append(0.0)
            continue
        matched = sum((pred_ngrams & ref_ngrams).values())
        precisions.append(matched / total)

    # No overlap at all → score 0 (avoid log(1e-9) smoothing residue)
    if max(precisions) == 0.0:
        return 0.0

    # Geometric mean in log domain with smoothing (avoid log(0))
    log_sum = sum(math.log(p) if p > 0 else math.log(1e-9) for p in precisions)
    geo_mean = math.exp(log_sum / len(precisions))

    # Brevity penalty
    bp = 1.0
    if len(pred) < len(ref):
        bp = len(pred) / len(ref) if len(ref) > 0 else 0.0

    return bp * geo_mean


_TOOL_CALL_RE = re.compile(r"^\{.*\}$", re.DOTALL)


def tool_call_valid(prediction: str) -> float:
    """1.0 if the output parses as a JSON tool-call object, else 0.0.

    Accepts bare JSON or JSON wrapped in ```json ... ``` fences. A valid tool
    call must contain at least one of ``name``/``function`` and ``arguments``.
    """
    text = prediction.strip()
    if text.startswith("```"):
        # Strip code fences
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    has_name = "name" in data or "function" in data
    has_args = "arguments" in data or "parameters" in data or "input" in data
    return 1.0 if (has_name and has_args) else 0.0


# ── Dispatch ───────────────────────────────────────────────────────────


def score_prediction(
    prediction: str,
    metric: MetricType | str,
    reference: str = "",
) -> float:
    """Score a single prediction with the chosen metric.

    ``metric`` may be a ``MetricType`` or its string value. ``reference`` is
    required for all metrics except ``tool_call_valid``.
    """
    metric_name = metric.value if isinstance(metric, MetricType) else str(metric)
    m = MetricType(metric_name)

    if m is MetricType.EXACT_MATCH:
        return exact_match(prediction, reference)
    if m is MetricType.ROUGE_L:
        return rouge_l(prediction, reference)
    if m is MetricType.ROUGE_2:
        return rouge_2(prediction, reference)
    if m is MetricType.BLEU:
        return bleu(prediction, reference)
    if m is MetricType.TOOL_CALL_VALID:
        return tool_call_valid(prediction)
    # MetricType.LLM is handled by the LLM evaluator, not here
    raise ValueError(f"Metric {metric_name!r} has no programmatic implementation")


def batch_score(
    predictions: list[str],
    metric: MetricType | str,
    references: list[str] | None = None,
) -> float:
    """Mean score across a batch of predictions (data-driven optimizer style).

    When ``references`` is omitted, only self-scoring metrics
    (``tool_call_valid``) are meaningful.
    """
    scores: list[float] = []
    for i, pred in enumerate(predictions):
        ref = references[i] if references and i < len(references) else ""
        scores.append(score_prediction(pred, metric, ref))
    return sum(scores) / len(scores) if scores else 0.0
