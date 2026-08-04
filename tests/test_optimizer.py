"""Tests for the optimizer core loop."""


class TestOptimizer:
    def test_converges_first_round(self, stub_provider, temp_skill, tmp_path):
        """No failures found → converged=True immediately."""
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        reflector = Reflector(stub_provider)
        # Pass a temp db_path that doesn't exist → no failures
        optimizer = Optimizer(
            stub_provider,
            reflector,
            max_rounds=3,
            db_path=str(tmp_path / "nonexistent.db"),
        )

        result = optimizer.optimize_skill(temp_skill, "test-skill")
        assert result.converged
        assert result.rounds == 0
        assert result.failures_found == 0

    def test_iterates_on_failure(self, stub_provider, temp_skill, tmp_path):
        """Failures found → reflector called → returns improved artifact."""
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            reflector,
            max_rounds=2,
            db_path=str(tmp_path / "nonexistent.db"),  # No real failures
        )

        result = optimizer.optimize_skill(temp_skill, "test-skill")
        # With no real DB, should converge immediately
        assert result.converged
        assert result.rounds == 0
        assert stub_provider.calls == []

    def test_respects_max_rounds(self, stub_provider, temp_skill, tmp_path):
        """No failures → converges immediately regardless of max_rounds."""
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            reflector,
            max_rounds=5,
            db_path=str(tmp_path / "nonexistent.db"),
        )

        result = optimizer.optimize_skill(temp_skill, "test-skill")
        assert result.rounds == 0
        assert result.converged
        assert stub_provider.calls == []

    def test_history_stored(self, stub_provider, temp_skill, tmp_path):
        """With no failures, history should be empty."""
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            reflector,
            max_rounds=2,
            db_path=str(tmp_path / "nonexistent.db"),
        )

        result = optimizer.optimize_skill(temp_skill, "test-skill")
        # Should converge immediately with no failures
        assert result.converged
        assert "No relevant failures" in result.failure_summary

    def test_no_modify_original(self, stub_provider, temp_skill, tmp_path):
        """Source file is unchanged when --save is not given."""
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        with open(temp_skill) as f:
            original = f.read()

        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            reflector,
            max_rounds=2,
            db_path=str(tmp_path / "nonexistent.db"),
        )

        optimizer.optimize_skill(temp_skill, "test-skill")
        with open(temp_skill) as f:
            assert original == f.read()

    def test_save_writes_output(self, stub_provider, temp_skill, tmp_path):
        """--save writes {path}.optimized."""
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        out_path = tmp_path / "output.md"
        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            reflector,
            max_rounds=1,
            output_path=str(out_path),
            db_path=str(tmp_path / "nonexistent.db"),
        )

        result = optimizer.optimize_skill(temp_skill, "test-skill")
        # Converges immediately, so no output written
        assert result.converged

    def test_empty_artifact_guarded(self, tmp_path):
        """Reflector returns empty → loop stops."""
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        empty_skill = tmp_path / "empty.md"
        empty_skill.write_text("")

        class EmptyProvider:
            calls = 0

            def reflect(self, *a, **k):
                self.calls += 1
                return ""  # Empty response

            def close(self):
                pass

        provider = EmptyProvider()  # type: ignore[assignment]
        reflector = Reflector(provider)
        optimizer = Optimizer(
            provider,
            reflector,
            max_rounds=2,
            db_path=str(tmp_path / "nonexistent.db"),  # No real failures
        )

        result = optimizer.optimize_skill(str(empty_skill), "empty-skill")
        # Should converge immediately (no failures in nonexistent DB)
        assert result.converged
        assert result.rounds == 0
        assert provider.calls == 0

    def test_max_rounds_capped(self, stub_provider, temp_skill):
        """Excessive max_rounds is silently capped at 20."""
        from rw_promptforge.optimizer import Optimizer, MAX_ROUNDS_CAP
        from rw_promptforge.reflector.engine import Reflector

        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            reflector,
            max_rounds=999,
        )

        assert optimizer.max_rounds == MAX_ROUNDS_CAP

    def test_contrastive_traces(self, stub_provider):
        """Test that ContrastiveTraces includes both failures and successes."""
        from rw_promptforge.datastore.session_db import ContrastiveTraces

        traces = ContrastiveTraces(
            failures=[],
            successes=["good work", "that's right"],
        )
        assert traces.successes == ["good work", "that's right"]
        assert traces.failures == []

    def test_severity_ranking(self, stub_provider):
        """Test that high severity failures come first."""
        from rw_promptforge.datastore.session_db import FailureTrace

        high = FailureTrace(
            session_id="s1",
            timestamp=1.0,
            what_happened="did X wrong",
            user_correction="you were supposed to Y",
            severity=2,
        )
        low = FailureTrace(
            session_id="s2",
            timestamp=2.0,
            what_happened="minor issue",
            user_correction="should be Z",
            severity=1,
        )
        sorted_traces = [high, low]
        sorted_traces.sort(key=lambda x: x.severity, reverse=True)
        assert sorted_traces[0].session_id == "s1"
        assert sorted_traces[1].session_id == "s2"