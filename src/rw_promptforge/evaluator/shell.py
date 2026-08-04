"""Shell-based evaluator: run a command and score by exit code + output."""

from __future__ import annotations

EVAL_OUTPUT_MAX_CHARS = 4000
import re
import shlex
import subprocess
import time

# Patterns to scrub from eval output before sending to the reflection LLM.
# Prevents accidental credential leaks via eval STDERR/STDOUT.
_SANITIZE_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)[=:]\s*\S+"),  # noqa: E501
        r"\1=[REDACTED]"),
    (re.compile(r"Bearer\s+\S+"), "Bearer [REDACTED]"),
    (re.compile(r"-----BEGIN.*?-----.*?-----END.*?-----", re.DOTALL), "[REDACTED_KEY]"),
]


def _sanitize(text: str) -> str:
    """Scrub credential-looking patterns from evaluation output."""
    for pattern, replacement in _SANITIZE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class ShellEvaluator:
    """Execute a shell command against a target artifact and return the outcome."""

    def __init__(
        self,
        command_template: str,
        timeout: int = 300,
        sanitize_eval_output: bool = True,
    ) -> None:
        """Initialize with a command template.

        `{path}` is replaced with the artifact file path before execution.
        Example: "hermes skill_view test --skill-path {path}"

        Args:
            command_template: Shell command with `{path}` placeholder.
            timeout: Max seconds for the eval command.
            sanitize_eval_output: If True, scrub credential patterns
                from eval output before storing in EvalResult.
        """
        self.command_template = command_template
        self.timeout = timeout
        self.sanitize = sanitize_eval_output

    def evaluate(self, artifact_path: str) -> EvalResult:
        """Run the eval command and return structured results."""
        # Prevent shell injection: quote the path before substitution
        safe_path = shlex.quote(artifact_path)
        command = self.command_template.replace("{path}", safe_path)
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
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            if self.sanitize:
                stdout = _sanitize(stdout)
                stderr = _sanitize(stderr)
            # Truncate to prevent context overflow
            if len(stdout) > EVAL_OUTPUT_MAX_CHARS:
                stdout = stdout[:EVAL_OUTPUT_MAX_CHARS] + f"\n... [output truncated at {EVAL_OUTPUT_MAX_CHARS} chars] ...\n"
            if len(stderr) > EVAL_OUTPUT_MAX_CHARS:
                stderr = stderr[:EVAL_OUTPUT_MAX_CHARS] + f"\n... [stderr truncated at {EVAL_OUTPUT_MAX_CHARS} chars] ...\n"
            return EvalResult(
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
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
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"EVALUATION RESULT: {status} (exit={self.exit_code}, {self.elapsed:.1f}s)",
            f"COMMAND: {self.command}",
            "",
            "STDOUT:",
            self.stdout or "(empty)",
            "",
            "STDERR:",
            self.stderr or "(empty)",
        ]
        return "\n".join(lines)
