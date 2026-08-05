"""Tests for the few-shot examples loader (v2.1, FPO-style)."""

import json

import pytest

from rw_promptforge.datastore.models import FewShotExample
from rw_promptforge.targets.examples import (
    load_examples,
    summarize_examples,
    ExampleFormatError,
)


class TestLoadExamples:
    def test_target_response_shape(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text(
            json.dumps(
                {"prompt": "p1", "model_response": "m1", "target_response": "t1"}
            )
            + "\n"
            + json.dumps({"prompt": "p2", "model_response": "m2", "target_response": "t2"})
            + "\n"
        )
        examples = load_examples(p)
        assert len(examples) == 2
        assert examples[0].is_target_shape
        assert not examples[0].is_rubrics_shape
        assert examples[0].prompt == "p1"
        assert examples[0].target_response == "t1"

    def test_rubrics_shape(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text(
            json.dumps(
                {
                    "prompt": "p1",
                    "model_response": "m1",
                    "rubrics": ["is English", "under 50 words"],
                    "rubrics_evaluations": [True, False],
                }
            )
            + "\n"
        )
        examples = load_examples(p)
        assert examples[0].is_rubrics_shape
        assert not examples[0].is_target_shape
        assert examples[0].rubric_hit_rate() == 0.5

    def test_both_shapes_rubrics_win(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text(
            json.dumps(
                {
                    "prompt": "p1",
                    "target_response": "t1",
                    "rubrics": ["ok"],
                    "rubrics_evaluations": [True],
                }
            )
            + "\n"
        )
        examples = load_examples(p)
        # Rubrics take precedence → target_response cleared
        assert examples[0].is_rubrics_shape
        assert examples[0].target_response == ""

    def test_blank_lines_skipped(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text('{"prompt": "p1", "target_response": "t1"}\n\n\n')
        assert len(load_examples(p)) == 1

    def test_missing_prompt_raises(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text(json.dumps({"target_response": "t1"}) + "\n")
        with pytest.raises(ExampleFormatError, match="prompt"):
            load_examples(p)

    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text("{not json}\n")
        with pytest.raises(ExampleFormatError, match="invalid JSON"):
            load_examples(p)

    def test_no_shape_raises(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text(json.dumps({"prompt": "p1"}) + "\n")
        with pytest.raises(ExampleFormatError, match="target_response"):
            load_examples(p)

    def test_rubrics_wrong_type_raises(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text(
            json.dumps({"prompt": "p1", "rubrics": "not-a-list", "rubrics_evaluations": [True]})
            + "\n"
        )
        with pytest.raises(ExampleFormatError, match="rubrics"):
            load_examples(p)

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_examples(tmp_path / "nope.jsonl")

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / "ex.jsonl"
        p.write_text("\n\n")
        with pytest.raises(ExampleFormatError, match="No examples"):
            load_examples(p)


class TestSummarize:
    def test_target_summary(self):
        examples = [FewShotExample("p", target_response="t")]
        s = summarize_examples(examples)
        assert "1 examples" in s
        assert "target-response" in s

    def test_rubric_hit_rate(self):
        examples = [
            FewShotExample("p", rubrics=["a", "b"], rubrics_evaluations=[True, False])
        ]
        s = summarize_examples(examples)
        assert "50%" in s

    def test_empty(self):
        assert summarize_examples([]) == "0 examples (0 target-response, 0 rubrics) · rubric hit rate 0%"
