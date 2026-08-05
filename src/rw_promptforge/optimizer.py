"""Optimizer — the core evaluate-reflect-improve loop.

Implements the RefineStop v2 algorithm:
- Multi-dimensional scoring (4 categories)
- Forward/reverse audit loop
- Convergence detection (fixed math)
- Redundancy/diminishing returns detection
- ARMORED section protection

v2.1 (data-driven optimizer style):
- Candidate beam: N variants per round with varied emphasis
- Ranked frontier: top-K candidates kept by combined rank score
- Few-shot examples: FPO-style gap-bridging toward gold targets/rubrics
- Pluggable programmatic metrics (exact_match / rouge / bleu / tool_call_valid)
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
    Candidate,
    Frontier,
    FewShotExample,
    MetricType,
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
from rw_promptforge.auditor import (
    reverse_audit,
    PASS,
    FAIL,
    REVIEW,
    extract_armored_sections,
    merge_artifact_sections,
    _replace_section_content,
    _stagnation_probe,
)
from rw_promptforge.evaluator.metrics import batch_score

# Beam variation hints — each slot asks the reflector for a different emphasis,
# producing diverse candidates for the frontier (DDO-style exploration).
BEAM_HINTS = (
    "structural coherence and section ordering",
    "failure coverage and behavioral specificity",
    "conciseness and redundancy removal",
    "actionability and executable instructions",
)


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
        # v2.1
        beam_size: int = 1,
        metric: MetricType | str = "llm",
        examples: list[FewShotExample] | None = None,
        frontier_size: int = 5,
        # v2.2 tuning knobs
        convergence_threshold: float = 0.8,
        no_reverse_audit: bool = False,
        max_growth: float = SIZE_MULTIPLIER_CAP,
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
        # v2.1
        self.beam_size = max(1, beam_size)
        self.metric = MetricType(metric) if isinstance(metric, str) else metric
        self.examples = list(examples or [])
        self.frontier = Frontier(max_size=max(1, frontier_size))
        # v2.2 tuning knobs
        self.convergence_threshold = convergence_threshold
        self.no_reverse_audit = no_reverse_audit
        self.max_growth = max_growth
        self._learning_log: list[LearningLogEntry] = []
        self._score_history: list[CategoryScores] = []
        self._multiplier_history: list[MultiplierEntry] = []
        # LLM judge context (baseline artifact, failure traces) — set per round
        self._judge_context: tuple[str, str] | None = None
        # Concurrency for chunked section refinement (fewer = gentler on rate limits)
        self.section_workers = 4

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
        round_base_size = len(artifact)  # Track current round's base size for audit

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

            # Few-shot examples replace db traces when provided (FPO mode)
            if self.examples:
                failure_summary = self._format_examples_summary(self.examples)

            # Check empty/early convergence (only when no examples given)
            if not self.examples and self._is_empty_traces(failure_summary, traces):
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

            # ── Reflect (beam) ──
            old_artifact = artifact
            severity_before = self._max_severity(traces)

            truncated = truncate_artifact(artifact, MAX_ARTIFACT_CHARS)
            size_budget = int(original_size * self.max_growth)

            variants: list[tuple[int, str]] = []
            # Chunked reflection: a large soul artifact (>25KB) cannot be
            # meaningfully rewritten in one call — the model echoes input.
            # Refine per-section instead, then merge back into the skeleton.
            # ARMORED sections are EXCLUDED: they are safety-critical and the
            # reverse audit rejects any variant that touches them.
            chunk_sections: list[tuple[str, str, str]] = []
            if target_type == "soul" and len(artifact) > 25000:
                try:
                    from rw_promptforge.auditor import _iter_sections
                    from rw_promptforge.targets.soul import SoulTarget

                    chunk_sections = [
                        (tag, name, content)
                        for tag, name, content in _iter_sections(artifact)
                        if name not in SoulTarget.ARMORED_SECTIONS
                    ]
                except Exception:
                    chunk_sections = []

            for slot in range(self.beam_size):
                variation = ""
                if self.beam_size > 1:
                    variation = f"\nVARIATION {slot + 1}: focus your rewrite on {BEAM_HINTS[slot % len(BEAM_HINTS)]}."

                if chunk_sections:
                    # Per-section refinement: one LLM call per section
                    per_section_budget = max(2000, int(original_size * self.max_growth) // max(len(chunk_sections), 1))
                    improved = self.reflector.reflect_sections(
                        sections=chunk_sections,
                        failure_traces=failure_summary,
                        history=history_text + variation,
                        size_budget=per_section_budget,
                        max_workers=self.section_workers,
                    )
                    if not improved:
                        continue
                    # Reassemble: original skeleton, refined section content
                    variant = merge_artifact_sections(artifact, artifact)
                    for name, content in improved.items():
                        variant = _replace_section_content(variant, name, content)
                else:
                    variant = self.reflector.reflect(
                        artifact=truncated,
                        failure_traces=failure_summary,
                        history=history_text + variation,
                        size_budget=size_budget,
                    )
                # Structural merge: LLMs delete sections; guarantee the
                # original skeleton survives by construction (target_type soul)
                if target_type == "soul" and artifact:
                    variant = merge_artifact_sections(artifact, variant)
                # Guard: reject empty/suspicious variants
                if variant and len(variant.strip()) >= 10:
                    variants.append((slot, variant))

            if not variants:
                break

            # ── Score + audit every variant, populate frontier ──
            # Judge context: current artifact + failure traces (LLM metric)
            self._judge_context = (artifact[:8000], failure_summary[:4000])
            accepted: list[tuple[int, str, CategoryScores]] = []
            for slot, variant in variants:
                scores = score_categories(variant, failure_summary)
                metric_score = self._candidate_metric(variant)
                candidate = Candidate(
                    artifact=variant,
                    scores=scores,
                    metric_score=metric_score,
                    size_delta=len(variant) / original_size if original_size else 0.0,
                    round_generated=round_num + 1,
                )

                # ── Reverse audit ──
                # Stagnation check must only compare against ACCEPTED artifacts —
                # rejected siblings (same round, same base) are near-identical
                # by construction and would falsely trip the 0.95 threshold.
                recent_snippets = [
                    e.artifact_snippet
                    for e in self._learning_log[-3:]
                    if e.observed_outcome in ("improvement", "neutral")
                ]
                if self.no_reverse_audit:
                    audit = PASS
                else:
                    audit = reverse_audit(
                                        artifact_path=artifact_path if target_type == "soul" else None,
                                        old_artifact=old_artifact,
                                        new_artifact=variant,
                                        failure_traces=failure_summary,
                                        original_size=round_base_size,
                                        recent_snippets=recent_snippets,
                                        size_cap=self.max_growth,
                                    )

                if audit == FAIL:
                    self._learning_log.append(
                        LearningLogEntry(
                            attempted_change=f"Round {round_num + 1} slot {slot + 1}",
                            observed_outcome="rejected",
                            severity_before=severity_before,
                            severity_after=severity_before,
                            change_summary=format_category_report(prev_scores or scores, scores),
                            artifact_snippet=_stagnation_probe(variant),
                        )
                    )
                    continue

                if audit == REVIEW:
                    self._learning_log.append(
                        LearningLogEntry(
                            attempted_change=f"Round {round_num + 1} slot {slot + 1} (needs review)",
                            observed_outcome="review_needed",
                            severity_before=severity_before,
                            severity_after=severity_before,
                            change_summary=format_category_report(prev_scores or scores, scores),
                            artifact_snippet=_stagnation_probe(variant),
                        )
                    )
                    continue

                # Passed audit → candidate enters the frontier
                self.frontier.add(candidate)
                accepted.append((slot, variant, scores))

            if not accepted:
                artifact = old_artifact
                continue

            # ── Post-mutation verification on the best variant ──
            best_slot, best_variant, best_scores = max(
                accepted, key=lambda t: self._rank(*t)
            )

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
                            artifact_snippet=_stagnation_probe(best_variant),
                        )
                    )
                    artifact = old_artifact
                    continue
                best_variant = improved

            # ── Accept best variant ──
            artifact = best_variant
            round_base_size = len(best_variant)  # Update base for next round's audit
            scores = best_scores
            multipliers = compute_multipliers(prev_scores or scores, scores)
            self._score_history.append(scores)
            self._multiplier_history.append(multipliers)

            severity_after = severity_before  # simplified
            outcome = "improvement" if severity_after < severity_before else "neutral"

            self._learning_log.append(
                LearningLogEntry(
                    attempted_change=f"Round {round_num + 1}",
                    observed_outcome=outcome,
                    severity_before=severity_before,
                    severity_after=severity_after,
                    change_summary=format_category_report(prev_scores or scores, scores),
                    artifact_snippet=_stagnation_probe(artifact),
                    categories=str(scores.as_dict()),
                    multiplier=str(multipliers.multipliers),
                )
            )
            prev_scores = scores
            history.append(f"Round {round_num + 1}: score {scores.composite:.2f}")

            # ── Incremental output: never lose progress to timeouts ──
            # Write best-so-far artifact each round so an interrupted run
            # still yields a usable refined file.
            if self.output_path:
                best_so_far = self.frontier.best.artifact if self.frontier.best else artifact
                try:
                    self.output_path.write_text(best_so_far)
                except OSError:
                    pass  # best-effort; final write happens at end

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
                if is_converged(
                    self._learning_log,
                    self._multiplier_history,
                    threshold=self.convergence_threshold,
                ):
                    break

        # ── Save output (best of frontier when populated, else final artifact) ──
        final_artifact = artifact
        if self.frontier.best is not None:
            final_artifact = self.frontier.best.artifact

        if self.output_path and final_artifact:
            self.output_path.write_text(final_artifact)

        return OptimizeResult(
            artifact=final_artifact,
            rounds=len(self._learning_log),
            failures_found=total_failures,
            converged=is_converged(
                self._learning_log,
                self._multiplier_history,
                threshold=self.convergence_threshold,
            ),
            failure_summary="\n".join(history),
            learning_log=list(self._learning_log),
            composite_score=prev_scores.composite if prev_scores else 0.0,
            categories=str([s.as_dict() for s in self._score_history]),
            multipliers=str([m.multipliers for m in self._multiplier_history]),
            frontier=list(self.frontier.candidates),
            metric_type=self.metric.value if isinstance(self.metric, MetricType) else str(self.metric),
            metric_score=self.frontier.best.metric_score if self.frontier.best else 0.0,
        )

    # ── Helpers ──

    @staticmethod
    def _rank(slot: int, variant: str, scores: CategoryScores) -> float:
        """Rank key for accepted variants — composite only (metric applied via frontier)."""
        return scores.composite

    def _candidate_metric(self, artifact: str) -> float:
        """Metric score for a candidate vs gold target responses.

        - LLM metric: reflector.judge() scores the candidate against the
          current artifact + failure traces (0..1). Falls back to 0.0 when
          no judge context is available (safe default).
        - Programmatic metrics: mean of the chosen metric computed between
          the candidate artifact and each target-response example.
        """
        if self.metric is MetricType.LLM:
            ctx = self._judge_context
            if ctx is None:
                return 0.0
            baseline, failure_traces = ctx
            return self.reflector.judge(baseline, artifact, failure_traces)
        if not self.examples:
            return 0.0
        refs = [e.target_response for e in self.examples if e.is_target_shape]
        if not refs:
            return 0.0
        return batch_score([artifact] * len(refs), self.metric, refs)

    def _format_examples_summary(self, examples: list[FewShotExample]) -> str:
        """Format few-shot examples into reflector context (FPO gap-bridging).

        Worst-performing examples (lowest rubric hit rate / largest gap to
        target) surface first — they carry the most corrective signal.
        """
        ranked = sorted(
            examples,
            key=lambda e: (e.rubric_hit_rate(), 0.0 if e.is_target_shape else 1.0),
        )
        sections = ["## FEW-SHOT EXAMPLES (gap-bridging targets)"]
        for i, ex in enumerate(ranked[:MAX_EFFECTIVE_TRACES], start=1):
            sections.append(f"### Example {i}")
            sections.append(f"Prompt: {ex.prompt[:400]}")
            if ex.model_response:
                sections.append(f"Model response (suboptimal): {ex.model_response[:300]}")
            if ex.is_target_shape:
                sections.append(f"Target response (gold): {ex.target_response[:300]}")
            if ex.is_rubrics_shape:
                for rubric, met in zip(ex.rubrics, ex.rubrics_evaluations):
                    mark = "✓" if met else "✗"
                    sections.append(f"- [{mark}] {rubric}")
        return "\n".join(sections)

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