"""Optimizer — the core evaluate-reflect-improve loop.

Implements the RefineStop v2 algorithm:
- Multi-dimensional scoring (4 categories)
- Forward/reverse audit loop
- Convergence detection (fixed math)
- Redundancy/diminishing returns detection
- ARMORED section protection
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rw_promptforge.datastore.models import (
    FailureTrace,
    LearningLogEntry,
    OptimizeResult,
    CategoryScores,
    MultiplierEntry,
    compute_multipliers,
    compute_artifact_meta,
    truncate_artifact,
    MAX_ARTIFACT_CHARS,
    MAX_ROUNDS_CAP,
    MAX_EFFECTIVE_TRACES,
    FAILURE_TYPE_WEIGHTS,
    SIZE_MULTIPLIER_CAP,
)
from rw_promptforge.datastore.session_db import SessionDBReader
from rw_promptforge.reflector.engine import Reflector
from rw_promptforge.categories import score_categories, format_category_report
from rw_promptforge.convergence import (
    convergence_score,
    is_converged,
    check_redundancy,
    check_semantic_stability,
    format_convergence_report,
)
from rw_promptforge.auditor import reverse_audit, PASS, FAIL, REVIEW, extract_armored_sections


class Optimizer:
    """Session-db driven evaluate → reflect → improve loop (v2 RefineStop)."""

    def __init__(
        self,
        provider,
        reflector: Reflector,
        max_rounds: int = 3,
        output_path: str | None = None,
        db_path: str | None = None,
        learning_log_strategy: str = "none",
        post_mutation_verify: bool = False,
        semantic_threshold: float = 0.95,
        gain_threshold: float = 0.02,
        stability_threshold: float = 0.05,
        min_rounds: int = 2,
    ) -> None:
        self.provider = provider
        self.reflector = reflector
        self.max_rounds = min(max_rounds, MAX_ROUNDS_CAP)
        self.output_path = Path(output_path) if output_path else None
        self.db = SessionDBReader(db_path)
        self.learning_log_strategy = learning_log_strategy
        self.post_mutation_verify = post_mutation_verify
        self.semantic_threshold = semantic_threshold
        self.gain_threshold = gain_threshold
        self.stability_threshold = stability_threshold
        self.min_rounds = min_rounds
        self._learning_log: list[LearningLogEntry] = []
        self._score_history: list[CategoryScores] = []
        self._multiplier_history: list[MultiplierEntry] = []

    def optimize_skill(
        self, artifact_path: str, skill_name: str
    ) -> OptimizeResult:
        """Optimize a skill file — unified entry point."""
        return self._optimize(
            artifact_path=artifact_path,
            target_name=skill_name,
            target_type="skill",
            use_skill_traces=True,
        )

    def optimize_soul(self, artifact_path: str) -> OptimizeResult:
        """Optimize a SOUL.md file."""
        return self._optimize(
            artifact_path=artifact_path,
            target_name="soul",
            target_type="soul",
            use_skill_traces=False,
        )

    def _optimize(
        self,
        artifact_path: str,
        target_name: str,
        target_type: str,
        use_skill_traces: bool,
    ) -> OptimizeResult:
        """Core v2 RefineStop loop."""
        artifact = Path(artifact_path).read_text()
        original_size = len(artifact)

        meta = compute_artifact_meta(
            target_name, target_type, artifact,
            region_count=0,  # will be parsed by target parser
        )

        history: list[str] = []
        total_failures = 0
        prev_scores: CategoryScores | None = None

        for round_num in range(self.max_rounds):
            # ── Query failure traces (v2 flat API) ──
            traces = self.db.get_contrastive_traces(
                target_name if use_skill_traces else None,
                limit=MAX_EFFECTIVE_TRACES,
                weights=FAILURE_TYPE_WEIGHTS,
                round_number=round_num,
            )
            failure_summary = self.db.format_flat_traces(traces)

            # Check empty/early convergence
            if self._is_empty_traces(failure_summary, traces):
                return OptimizeResult(
                    artifact=artifact,
                    rounds=round_num,
                    failures_found=total_failures,
                    converged=True,
                    failure_summary="No relevant failures found.",
                    learning_log=list(self._learning_log),
                )

            # Count failures
            failure_count = failure_summary.count("### [")
            total_failures += max(failure_count, 1)
            history_text = "\n".join(history) if history else "(first iteration)"

            # Add learning log
            if self.learning_log_strategy != "none" and self._learning_log:
                log_entries = self._format_learning_log()
                history_text = f"LEARNING LOG:\n{log_entries}\n\n{history_text}"

            # ── Reflect ──
            old_artifact = artifact
            severity_before = self._max_severity(traces)

            truncated = truncate_artifact(artifact, MAX_ARTIFACT_CHARS)
            size_budget = int(original_size * SIZE_MULTIPLIER_CAP)
            artifact = self.reflector.reflect(
                artifact=truncated,
                failure_traces=failure_summary,
                history=history_text,
                size_budget=size_budget,
            )

            # Guard: reject empty/suspicious
            if not artifact or len(artifact.strip()) < 10:
                break

            # ── Score candidate ──
            scores = score_categories(artifact, failure_summary)
            multipliers = compute_multipliers(prev_scores or scores, scores)
            self._score_history.append(scores)
            self._multiplier_history.append(multipliers)

            # ── Reverse audit ──
            recent_snippets = [e.artifact_snippet for e in self._learning_log[-3:]]
            audit = reverse_audit(
                artifact_path=artifact_path if target_type == "soul" else None,
                old_artifact=old_artifact,
                new_artifact=artifact,
                failure_traces=failure_summary,
                original_size=original_size,
                recent_snippets=recent_snippets,
            )

            if audit == FAIL:
                # Revert and continue
                outcome = "rejected"
                self._learning_log.append(
                    LearningLogEntry(
                        attempted_change=f"Round {round_num + 1}",
                        observed_outcome=outcome,
                        severity_before=severity_before,
                        severity_after=severity_before,
                        change_summary=format_category_report(prev_scores or scores, scores),
                        artifact_snippet=artifact[:200],
                    )
                )
                artifact = old_artifact
                continue

            if audit == REVIEW:
                # Human review needed — stop and flag
                outcome = "review_needed"
                self._learning_log.append(
                    LearningLogEntry(
                        attempted_change=f"Round {round_num + 1} (needs review)",
                        observed_outcome=outcome,
                        severity_before=severity_before,
                        severity_after=severity_before,
                        change_summary=format_category_report(prev_scores or scores, scores),
                        artifact_snippet=artifact[:200],
                    )
                )
                break

            # ── Post-mutation verification ──
            if self.post_mutation_verify:
                improved, verified = self.reflector.reflect_with_verification(
                    old_artifact, failure_summary, history_text, verify=True
                )
                if not verified:
                    outcome = "rejected"
                    self._learning_log.append(
                        LearningLogEntry(
                            attempted_change=f"Round {round_num + 1} (failed verification)",
                            observed_outcome=outcome,
                            severity_before=severity_before,
                            severity_after=severity_before,
                            artifact_snippet=artifact[:200],
                        )
                    )
                    artifact = old_artifact
                    continue
                artifact = improved

            # ── Accept ──
            severity_after = severity_before  # simplified
            outcome = "improvement" if severity_after < severity_before else "neutral"

            self._learning_log.append(
                LearningLogEntry(
                    attempted_change=f"Round {round_num + 1}",
                    observed_outcome=outcome,
                    severity_before=severity_before,
                    severity_after=severity_after,
                    change_summary=format_category_report(prev_scores or scores, scores),
                    artifact_snippet=artifact[:200],
                    categories=str(scores.as_dict()),
                    multiplier=str(multipliers.multipliers),
                )
            )
            prev_scores = scores
            history.append(f"Round {round_num + 1}: score {scores.composite:.2f}")

            # ── Check redundancy ──
            if check_redundancy(self._learning_log):
                break

            # ── Check gain saturation ──
            if len(self._score_history) >= self.min_rounds:
                sat = abs(scores.composite - (prev_scores or scores).composite) < self.gain_threshold
                if sat:
                    break

            # ── Check convergence ──
            if len(self._learning_log) >= self.min_rounds:
                if is_converged(self._learning_log, self._multiplier_history):
                    break

        # ── Save output ──
        if self.output_path and artifact:
            self.output_path.write_text(artifact)

        return OptimizeResult(
            artifact=artifact,
            rounds=len(self._learning_log),
            failures_found=total_failures,
            converged=is_converged(self._learning_log, self._multiplier_history),
            failure_summary="\n".join(history),
            learning_log=list(self._learning_log),
            composite_score=prev_scores.composite if prev_scores else 0.0,
            categories=str([s.as_dict() for s in self._score_history]),
            multipliers=str([m.multipliers for m in self._multiplier_history]),
        )

    # ── Helpers ──

    def _is_empty_traces(self, failure_summary: str, traces: list) -> bool:
        """Check if failure traces indicate no actionable data."""
        if "No relevant traces found" in failure_summary or "No failure traces found" in failure_summary:
            return True
        if isinstance(traces, list) and len(traces) == 0:
            return True
        return False

    def _max_severity(self, traces) -> int:
        """Extract max severity from traces."""
        if isinstance(traces, list):
            return max((t.severity for t in traces), default=0)
        return 0

    def _format_soul_failures(self, violations, corrections) -> str:
        """Format SOUL.md violations and corrections into summary text."""
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
        return "\n\n".join(sections)

    def _build_traces(self, violations, corrections) -> list:
        """Build a flat list of FailureTraces from separate sources."""
        result = list(violations) if violations else []
        result.extend(corrections) if corrections else None
        return result

    def _format_learning_log(self) -> str:
        """Format learning log entries for the reflector prompt."""
        if not self._learning_log:
            return "(no prior learning)"
        entries = []
        for entry in self._learning_log[-5:]:
            entries.append(
                f"- {entry.attempted_change}: {entry.observed_outcome}"
            )
        return "\n".join(entries)