"""Optimizer — the core evaluate-reflect-improve loop.

Implements patterns from Darwinian Evolver:
- Learning Log: track mutation attempts and outcomes
- Post-Mutation Verification: filter bad mutations early
- Weighted Failure Sampling: bias toward critical failures

Uses REAL failure traces from Hermes session_db to improve skills and SOUL.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rw_promptforge.datastore.models import LearningLogEntry
from rw_promptforge.datastore.session_db import SessionDBReader
from rw_promptforge.reflector.engine import Reflector

MAX_ROUNDS_CAP = 20


@dataclass
class OptimizeResult:
    """Immutable optimization outcome."""

    artifact: str
    """The final (best) artifact text."""

    rounds: int
    """Number of reflection rounds executed."""

    failures_found: int
    """Total failure traces found and fed to the reflector."""

    converged: bool
    """True if no failures were found (nothing to improve)."""

    failure_summary: str
    """Summary of all failure traces used."""

    learning_log: list[LearningLogEntry]
    """History of mutation attempts and outcomes."""


class Optimizer:
    """Session-db driven evaluate → reflect → improve loop.

    For skills: finds real sessions where the skill was loaded and the agent failed.
    For SOUL.md: finds protocol violations the agent committed despite instructions.
    """

    def __init__(
        self,
        provider,  # Provider
        reflector: Reflector,
        max_rounds: int = 3,
        output_path: str | None = None,
        db_path: str | None = None,
        learning_log_strategy: str = "none",
        post_mutation_verify: bool = False,
    ) -> None:
        self.provider = provider
        self.reflector = reflector
        self.max_rounds = min(max_rounds, MAX_ROUNDS_CAP)
        self.output_path = Path(output_path) if output_path else None
        self.db = SessionDBReader(db_path)
        self.learning_log_strategy = learning_log_strategy
        self.post_mutation_verify = post_mutation_verify
        self._learning_log: list[LearningLogEntry] = []

    def optimize_skill(
        self, artifact_path: str, skill_name: str
    ) -> OptimizeResult:
        """Optimize a skill file using real session_db failure traces."""
        artifact = Path(artifact_path).read_text()
        history = []
        total_failures = 0

        for round_num in range(self.max_rounds):
            # Query for real failures
            traces = self.db.get_contrastive_summary(skill_name, limit=5)
            failure_summary = self.db.format_contrastive_traces(traces)

            if "No relevant traces found" in failure_summary or "No failure traces found" in failure_summary:
                return OptimizeResult(
                    artifact=artifact,
                    rounds=round_num,
                    failures_found=total_failures,
                    converged=True,
                    failure_summary="No relevant failures found in session history.",
                    learning_log=list(self._learning_log),
                )

            # Count failures
            failure_count = failure_summary.count("### [")
            total_failures += failure_count

            # Reflect on real failures
            history_text = "\n".join(history) if history else "(first iteration)"

            # Add learning log if strategy is enabled
            if self.learning_log_strategy != "none" and self._learning_log:
                log_entries = self._format_learning_log()
                history_text = f"LEARNING LOG:\n{log_entries}\n\n{history_text}"

            old_artifact = artifact
            severity_before = max((t.severity for t in traces.failures), default=0)

            artifact = self.reflector.reflect(
                artifact=artifact,
                failure_traces=failure_summary,
                history=history_text,
            )

            # Guard: reject empty/suspicious output
            if not artifact or len(artifact.strip()) < 10:
                break

            # Post-mutation verification
            if self.post_mutation_verify:
                improved, verified = self.reflector.reflect_with_verification(
                    old_artifact, failure_summary, history_text, verify=True
                )
                if not verified:
                    # Keep old artifact, log the failed attempt
                    self._learning_log.append(
                        LearningLogEntry(
                            attempted_change="Reflected on failures",
                            observed_outcome="rejected",
                            severity_before=severity_before,
                            severity_after=severity_before,
                        )
                    )
                    continue
                artifact = improved

            # Record learning log entry
            severity_after = severity_before  # Simplified — would need re-eval for real value
            self._learning_log.append(
                self.reflector.create_learning_log_entry(
                    old_artifact,
                    artifact,
                    severity_before,
                    severity_after,
                )
            )

            history.append(f"Round {round_num + 1}: fixed {failure_count} failures")

        # Save output if configured
        if self.output_path and artifact:
            self.output_path.write_text(artifact)

        return OptimizeResult(
            artifact=artifact,
            rounds=self.max_rounds,
            failures_found=total_failures,
            converged=False,
            failure_summary="\n".join(history),
            learning_log=list(self._learning_log),
        )

    def optimize_soul(
        self, artifact_path: str
    ) -> OptimizeResult:
        """Optimize SOUL.md using real protocol violation traces."""
        artifact = Path(artifact_path).read_text()
        history = []
        total_failures = 0

        for round_num in range(self.max_rounds):
            # Query for protocol violations
            violations = self.db.find_protocol_violations(limit=10)
            corrections = self.db.find_corrections(limit=5)

            if not violations and not corrections:
                return OptimizeResult(
                    artifact=artifact,
                    rounds=round_num,
                    failures_found=total_failures,
                    converged=True,
                    failure_summary="No protocol violations or corrections found.",
                    learning_log=list(self._learning_log),
                )

            # Build failure summary for SOUL.md
            sections = []
            if violations:
                sections.append("## PROTOCOL VIOLATIONS")
                for v in violations:
                    sections.append(
                        f"### Violation in session {v.session_id}\n"
                        f"{v.what_happened[:400]}"
                    )
            if corrections:
                sections.append("## USER CORRECTIONS")
                for c in corrections:
                    sections.append(
                        f"### Correction in session {c.session_id}\n"
                        f"What agent did: {c.what_happened[:200]}\n"
                        f"User said: {c.user_correction[:200]}"
                    )

            failure_summary = "\n\n".join(sections)
            failure_count = len(violations) + len(corrections)
            total_failures += failure_count

            # Reflect
            history_text = "\n".join(history) if history else "(first iteration)"

            # Add learning log if strategy is enabled
            if self.learning_log_strategy != "none" and self._learning_log:
                log_entries = self._format_learning_log()
                history_text = f"LEARNING LOG:\n{log_entries}\n\n{history_text}"

            old_artifact = artifact
            severity_before = max(
                [v.severity for v in violations] +
                [c.severity for c in corrections],
                default=0
            )

            artifact = self.reflector.reflect(
                artifact=artifact,
                failure_traces=failure_summary,
                history=history_text,
            )

            if not artifact or len(artifact.strip()) < 10:
                break

            # Record learning log
            self._learning_log.append(
                self.reflector.create_learning_log_entry(
                    old_artifact,
                    artifact,
                    severity_before,
                    severity_before,  # Simplified
                )
            )

            history.append(f"Round {round_num + 1}: addressed {failure_count} violations")

        if self.output_path and artifact:
            self.output_path.write_text(artifact)

        return OptimizeResult(
            artifact=artifact,
            rounds=self.max_rounds,
            failures_found=total_failures,
            converged=False,
            failure_summary="\n".join(history),
            learning_log=list(self._learning_log),
        )

    def _format_learning_log(self) -> str:
        """Format learning log entries for the reflector prompt."""
        if not self._learning_log:
            return "(no prior learning)"

        entries = []
        for entry in self._learning_log[-5:]:  # Last 5 entries
            entries.append(
                f"- {entry.attempted_change}: {entry.observed_outcome}"
            )
        return "\n".join(entries)
