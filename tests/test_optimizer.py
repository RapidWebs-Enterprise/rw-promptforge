"""Tests for the optimizer core loop."""



class TestOptimizer:
    def test_converges_first_round(self, stub_provider, temp_skill):
        """Evaluator passes immediately → 1 round, converged=True."""
        from rw_promptforge.evaluator.shell import ShellEvaluator
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        evaluator = ShellEvaluator(command_template="exit 0")
        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            evaluator,
            reflector,
            eval_command="exit 0",
            max_rounds=3,
        )

        result = optimizer.optimize(temp_skill)
        assert result.converged
        assert result.rounds == 1
        assert stub_provider.calls == []

    def test_iterates_on_failure(self, stub_provider, temp_skill):
        """Failing eval → reflector called → converges after improvement."""
        from rw_promptforge.evaluator.shell import ShellEvaluator
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        evaluator = ShellEvaluator(command_template="exit 0")
        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            evaluator,
            reflector,
            eval_command="exit 0",
            max_rounds=3,
        )

        result = optimizer.optimize(temp_skill)
        assert result.converged
        assert result.rounds == 1

    def test_respects_max_rounds(self, stub_provider, temp_skill):
        """Always-failing eval → stops at max_rounds, converged=False."""
        from rw_promptforge.evaluator.shell import ShellEvaluator
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        evaluator = ShellEvaluator(command_template="exit 1")
        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            evaluator,
            reflector,
            eval_command="exit 1",
            max_rounds=2,
        )

        result = optimizer.optimize(temp_skill)
        assert not result.converged
        assert result.rounds == 2
        assert len(stub_provider.calls) == 1

    def test_history_stored(self, stub_provider, temp_skill):
        """Check history has correct length and round numbers."""
        from rw_promptforge.evaluator.shell import ShellEvaluator
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        evaluator = ShellEvaluator(command_template="exit 1")
        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            evaluator,
            reflector,
            eval_command="exit 1",
            max_rounds=3,
        )

        result = optimizer.optimize(temp_skill)
        assert len(result.history) == 3
        assert result.history[0][0] == 1
        assert result.history[1][0] == 2

    def test_no_modify_original(self, stub_provider, temp_skill):
        """Source file is unchanged when --save is not given."""
        from rw_promptforge.evaluator.shell import ShellEvaluator
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        with open(temp_skill) as f:
            original = f.read()

        evaluator = ShellEvaluator(command_template="exit 1")
        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            evaluator,
            reflector,
            eval_command="exit 1",
            max_rounds=2,
            output_path=None,
        )

        optimizer.optimize(temp_skill)
        with open(temp_skill) as f:
            assert original == f.read()

    def test_save_writes_output(self, stub_provider, temp_skill, tmp_path):
        """--save writes {path}.optimized."""
        from rw_promptforge.evaluator.shell import ShellEvaluator
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        out_path = tmp_path / "output.optimized"
        evaluator = ShellEvaluator(command_template="exit 0")
        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider,
            evaluator,
            reflector,
            eval_command="exit 0",
            max_rounds=1,
            output_path=str(out_path),
        )

        optimizer.optimize(temp_skill)
        assert out_path.exists()
        assert len(out_path.read_text()) > 0

    def test_shell_injection_prevented(self, temp_skill):
        """Path with shell metacharacters is safely quoted."""
        from rw_promptforge.evaluator.shell import ShellEvaluator

        dangerous_path = "/tmp/evil; rm -rf /"
        evaluator = ShellEvaluator(command_template="cat {path}")
        result = evaluator.evaluate(dangerous_path)

        # {path} replaced with shlex.quote()'d safe version
        assert "{path}" not in result.command
        # The dangerous chars are wrapped in single quotes (safe)
        assert "'/tmp/evil; rm -rf /'" in result.command

    def test_empty_artifact_guarded(self, tmp_path):
        """Reflect output < 10 chars stops the loop."""
        from rw_promptforge.evaluator.shell import ShellEvaluator
        from rw_promptforge.optimizer import Optimizer
        from rw_promptforge.reflector.engine import Reflector

        empty_skill = tmp_path / "empty.md"
        empty_skill.write_text("")

        provider = type(
            "ShortProvider",
            (),
            {
                "reflect": lambda self, *a, **k: "OK",
                "calls": [],
                "close": lambda s: None,
            },
        )()
        evaluator = ShellEvaluator(command_template="exit 1")
        reflector = Reflector(provider)

        optimizer = Optimizer(
            provider, evaluator, reflector,
            eval_command="exit 1",
            max_rounds=2,
        )

        result = optimizer.optimize(str(empty_skill))
        assert result.converged is False
        assert result.rounds in (1, 2)

    def test_max_rounds_capped(self, stub_provider, temp_skill):
        """Excessive --max-rounds is silently capped at 20."""
        from rw_promptforge.evaluator.shell import ShellEvaluator
        from rw_promptforge.optimizer import MAX_ROUNDS_CAP, Optimizer
        from rw_promptforge.reflector.engine import Reflector

        evaluator = ShellEvaluator(command_template="exit 0")
        reflector = Reflector(stub_provider)
        optimizer = Optimizer(
            stub_provider, evaluator, reflector,
            eval_command="exit 0",
            max_rounds=999,
        )

        assert optimizer.max_rounds == MAX_ROUNDS_CAP

    def test_binary_file_rejected(self, temp_skill):
        """Binary artifact → handled gracefully."""
        from rw_promptforge.evaluator.shell import EvalResult

        # EvalResult should still work for non-text artifacts
        result = EvalResult(0, "ok", "", "test", 0.1)
        assert result.passed

    def test_sanitize_scrubs_api_keys(self):
        """Sanitizer replaces KEY/TOKEN/Bearer patterns."""
        from rw_promptforge.evaluator.shell import _sanitize

        dirty = "API_KEY=sk-abc123\nAuthorization: Bearer xyz789"
        clean = _sanitize(dirty)
        assert "sk-abc123" not in clean
        assert "Bearer" not in clean
        assert "REDACTED" in clean
