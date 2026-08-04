"""Optimizer — the core evaluate-reflect-improve loop."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rw_promptforge.evaluator.shell import EvalResult, ShellEvaluator
    from rw_promptforge.provider import Provider
    from rw_promptforge.reflector.engine import Reflector


MAX_ARTIFACT_CHARS = 60_000
MAX_ROUNDS_CAP = 20


@dataclass
class OptimizeResult:
    """Immutable optimization outcome."""

    artifact: str
    """The final (best) artifact text."""

    history: list[tuple[int, EvalResult]]
    """List of (round_number, eval_result) for each round."""

    converged: bool
    """True if the evaluator passed before max_rounds."""

    @property
    def rounds(self) -> int:
        return len(self.history)


class Optimizer:
    """Iterative evaluate → reflect → improve loop.

    Flow:
      1. Evaluate the current artifact via shell command.
      2. If it passes — done (converged).
      3. Reflect: send failure trace + artifact to LLM → improved artifact.
      4. Repeat up to max_rounds.
    """

    def __init__(
        self,
        provider: Provider,
        evaluator: ShellEvaluator,
        reflector: Reflector,
        eval_command: str,
        max_rounds: int = 3,
        output_path: str | None = None,
    ) -> None:
        self.provider = provider
        self.evaluator_class = type(evaluator)
        self.eval_command = eval_command
        self.eval_timeout = evaluator.timeout
        self.eval_sanitize = evaluator.sanitize
        self.reflector = reflector
        self.max_rounds = min(max_rounds, MAX_ROUNDS_CAP)
        self.output_path = Path(output_path) if output_path else None

    def optimize(self, artifact_path: str) -> OptimizeResult:
        """Run the loop and return the result."""

        artifact = Path(artifact_path).read_text()
        history: list[tuple[int, EvalResult]] = []

        for round_num in range(self.max_rounds):
            # Truncate very large artifacts for LLM reflection
            (
                artifact
                if len(artifact) <= MAX_ARTIFACT_CHARS
                else artifact[:MAX_ARTIFACT_CHARS // 2]
                + "\n\n... [TRUNCATED] ...\n\n"
                + artifact[-MAX_ARTIFACT_CHARS // 2 :]
            )

            # Write artifact to temp file, evaluate

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False
            ) as tf:
                tf.write(artifact)
                tf.flush()
                temp_path = tf.name

            from rw_promptforge.evaluator.shell import ShellEvaluator

            evaluator = ShellEvaluator(
                command_template=self.eval_command.replace(
                    "{path}", str(temp_path)
                ),
                timeout=self.eval_timeout,
                sanitize_eval_output=self.eval_sanitize,
            )
            result = evaluator.evaluate(temp_path)
            history.append((round_num + 1, result))

            # Cleanup temp file
            import os

            os.unlink(temp_path)

            if result.passed:
                break

            if round_num == self.max_rounds - 1:
                break

            # Reflect
            artifact = self.reflector.reflect(
                artifact=artifact,
                trace=result.format_trace(),
                session_context="(no session data available)",
                history=f"Round {round_num + 1}: FAIL ({result.elapsed:.1f}s)",
            )

            # Guard: reject empty/suspicious reflect output
            if not artifact or len(artifact.strip()) < 10:
                break

        # Save output if configured
        if self.output_path and artifact:
            self.output_path.write_text(artifact)

        return OptimizeResult(
            artifact=artifact,
            history=history,
            converged=any(r.passed for _, r in history),
        )
