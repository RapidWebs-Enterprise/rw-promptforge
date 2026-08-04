"""Shell-based evaluator: run a command and score by exit code + output."""

from __future__ import annotations

import subprocess
import time


class ShellEvaluator:
    """Execute a shell command against a target artifact and return the outcome."""

    def __init__(self, command_template: str, timeout: int = 300) -> None:
        """Initialize with a command template.

        `{path}` is replaced with the artifact file path before execution.
        Example: "hermes skill_view test --skill-path {path}"
        """
        self.command_template = command_template
        self.timeout = timeout

    def evaluate(self, artifact_path: str) -> EvalResult:
        """Run the eval command and return structured results."""
        command = self.command_template.replace("{path}", artifact_path)
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            elapsed = time.monotonic() - started
            return EvalResult(
                exit_code=result.exit_code,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                command=command,
                elapsed=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - started
            return EvalResult(
                exit_code=-1,
                stdout="",
                stderr=f"TIMEOUT after {self.timeout}s",
                command=command,
                elapsed=elapsed,
            )


class EvalResult:
    """Immutable evaluation outcome."""

    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        command: str,
        elapsed: float,
    ) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.command = command
        self.elapsed = elapsed

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    @property
    def failed(self) -> bool:
        return not self.passed and self.exit_code != -1

    @property
    def timed_out(self) -> bool:
        return self.exit_code == -1

    def format_trace(self) -> str:
        """Produce a diagnostic trace for the reflection LLM to read."""
        lines = [
            f"EVALUATION RESULT: {'PASS' if self.passed else 'FAIL'} (exit={self.exit_code}, {self.elapsed:.1f}s)",
            f"COMMAND: {self.command}",
            "",
            "STDOUT:",
            self.stdout or "(empty)",
            "",
            "STDERR:",
            self.stderr or "(empty)",
        ]
        return "\n".join(lines)