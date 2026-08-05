"""Tests for the pluggable programmatic metrics (v2.1)."""

import pytest

from rw_promptforge.evaluator.metrics import (
    exact_match,
    rouge_l,
    rouge_2,
    bleu,
    tool_call_valid,
    score_prediction,
    batch_score,
)
from rw_promptforge.datastore.models import MetricType


class TestExactMatch:
    def test_identical(self):
        assert exact_match("The quick brown fox", "the quick brown fox") == 1.0

    def test_case_insensitive(self):
        assert exact_match("HELLO WORLD", "hello world") == 1.0

    def test_punctuation_normalized(self):
        assert exact_match("Hello, world!", "hello world") == 1.0

    def test_different(self):
        assert exact_match("one thing", "another thing") == 0.0


class TestRougeL:
    def test_identical(self):
        assert rouge_l("a b c d", "a b c d") == 1.0

    def test_subsequence(self):
        # LCS = "a b c d" (4 tokens) → precision 4/5, recall 4/4
        score = rouge_l("a b c d extra", "a b c d")
        assert 0.8 <= score <= 1.0

    def test_no_overlap(self):
        assert rouge_l("x y z", "a b c") == 0.0

    def test_empty(self):
        assert rouge_l("", "a b c") == 0.0
        assert rouge_l("a b c", "") == 0.0


class TestRouge2:
    def test_identical(self):
        assert rouge_2("a b c d", "a b c d") == 1.0

    def test_short_input(self):
        assert rouge_2("a", "a b c") == 0.0

    def test_partial_bigram_overlap(self):
        # bigrams: pred {a b, b c, c d} vs ref {b c, c d, d e} → overlap 2/3
        score = rouge_2("a b c d", "b c d e")
        assert 0.5 <= score <= 0.8


class TestBleu:
    def test_identical(self):
        assert bleu("the cat sat", "the cat sat") == pytest.approx(1.0, abs=1e-6)

    def test_brevity_penalty(self):
        # Short prediction penalized
        assert bleu("the cat", "the cat sat on the mat") < 0.5

    def test_empty(self):
        assert bleu("", "something") == 0.0

    def test_no_overlap(self):
        assert bleu("xyzzy", "completely different") == 0.0


class TestToolCallValid:
    def test_valid_json_object(self):
        assert tool_call_valid('{"name": "search", "arguments": {"q": "x"}}') == 1.0

    def test_valid_fenced(self):
        assert (
            tool_call_valid('```json\n{"function": "f", "parameters": {}}\n```')
            == 1.0
        )

    def test_invalid_json(self):
        assert tool_call_valid("not json at all") == 0.0

    def test_missing_args(self):
        assert tool_call_valid('{"name": "search"}') == 0.0

    def test_list_not_dict(self):
        assert tool_call_valid("[1, 2, 3]") == 0.0


class TestDispatch:
    def test_llm_raises(self):
        with pytest.raises(ValueError):
            score_prediction("x", MetricType.LLM, "ref")

    def test_unknown_metric_raises(self):
        with pytest.raises(ValueError):
            score_prediction("x", "bogus_metric", "ref")

    def test_exact_match_dispatch(self):
        assert score_prediction("same", MetricType.EXACT_MATCH, "same") == 1.0

    def test_rouge_l_dispatch(self):
        assert score_prediction("a b c", "rouge_l", "a b c") == 1.0

    def test_tool_call_ignores_reference(self):
        assert score_prediction('{"name": "x", "arguments": {}}', "tool_call_valid") == 1.0


class TestBatchScore:
    def test_mean(self):
        preds = ["a b c", "completely different"]
        refs = ["a b c", "a b c"]
        # rouge_l: 1.0 for first, 0.0 for second → mean 0.5
        assert batch_score(preds, "rouge_l", refs) == pytest.approx(0.5)

    def test_empty(self):
        assert batch_score([], "exact_match", []) == 0.0
