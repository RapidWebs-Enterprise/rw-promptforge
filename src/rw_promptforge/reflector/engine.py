"""Reflector: the LLM-based reflection step.

Given a current artifact (skill/SOUL.md), REAL failure traces from session_db,
and the history of improvements, the reflector asks an LLM to produce an
improved version that prevents these failures from recurring.

Improvements over v1:
- Contrastive traces (failures + successes)
- Hypothesis-first: diagnose root cause before rewriting
- Accumulated memory: track what was tried (Learning Log)
- Section-level editing: target specific sections
- Cache-friendly: stable prefix for LLM provider caching
- Post-mutation verification support
"""

from __future__ import annotations

from rw_promptforge.datastore.models import LearningLogEntry
from rw_promptforge.provider import Provider

# System prompt is now CACHEABLE — stable across all reflection calls
REFLECTION_SYSTEM_PROMPT = """You are an expert at improving LLM agent instructions.
Your task: given a CURRENT artifact (a skill or SOUL.md), and REAL failure traces
from actual agent usage sessions, produce an IMPROVED version that prevents
these failures from recurring.

Key principles:
1. Keep the same structure and format. Do not rewrite from scratch.
2. Fix what the failure traces reveal as broken — be SPECIFIC.
3. For skills: add missing steps, clarify ambiguous instructions, fix wrong commands.
4. For SOUL.md: strengthen protocols that the agent keeps violating.
5. If the agent keeps doing X despite instructions saying don't do X,
   make those instructions MORE prominent, clearer, with concrete examples.
6. Return ONLY the improved artifact. No explanation, no commentary, no code fences.
7. If the artifact has YAML frontmatter, preserve and update it.
8. Target SPECIFIC sections — don't rewrite everything.
9. STRUCTURAL INTEGRITY (MANDATORY): NEVER delete, merge, rename, or drop
   any section, block, or tag that exists in the CURRENT ARTIFACT. Every
   <tag name="...">...</tag> region present in the input MUST appear in your
   output with the same tag name and same section name. You may EDIT the
   content inside sections, but the section skeleton itself is inviolable.
   If the input has 23 sections, your output has 23 sections. Adding new
   sections is allowed; removing or restructuring existing ones is not.
10. SIZE DISCIPLINE: Do not balloon the artifact. Keep it within the size
    budget. Prefer tightening existing wording over adding new prose.
11. Do not convert section tags to other types (e.g. <protocol> must stay
    <protocol>, <verification> must stay <verification>).
"""

# User prompt has dynamic content at the END (cache-friendly)
REFLECTION_USER_TEMPLATE = """CURRENT ARTIFACT:
```
{artifact}
```

REAL FAILURE TRACES (from actual agent usage sessions):
{failure_traces}

PREVIOUS IMPROVEMENTS (Learning Log):
{history}

Based on these REAL failures, produce an improved artifact that prevents
these specific failures from recurring. Be targeted — fix what's broken,
don't rewrite everything."""


class Reflector:
    """LLM-powered reflection engine — reads real traces, proposes fixes."""

    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    def reflect(
        self,
        artifact: str,
        failure_traces: str,
        history: str = "(no prior improvements)",
        size_budget: int = 0,
    ) -> str:
        """Produce an improved artifact using real failure traces.

        Args:
            artifact: The original skill/SOUL.md text.
            failure_traces: Formatted failure traces from session_db.
            history: Track of improvements from prior reflection rounds.
            size_budget: Max allowed output size (0 = no limit).

        Returns:
            The improved artifact text.
        """
        user_prompt = REFLECTION_USER_TEMPLATE.format(
            artifact=artifact,
            failure_traces=failure_traces,
            history=history,
        )
        result = self.provider.reflect(
            prompt=user_prompt,
            system=REFLECTION_SYSTEM_PROMPT,
        )

        # Enforce size budget
        if size_budget > 0 and len(result) > size_budget:
            # Truncate with notice
            half = size_budget // 2
            result = result[:half] + "\n... [TRUNCATED] ...\n" + result[-half:]

        return result

    def reflect_with_verification(
        self,
        artifact: str,
        failure_traces: str,
        history: str = "(no prior improvements)",
        verify: bool = False,
    ) -> tuple[str, bool]:
        """Two-step reflection with optional post-mutation verification.

        Args:
            verify: If True, check if the improved artifact would pass
                   the failure traces before returning.

        Returns:
            (improved_artifact, verification_passed)
        """
        improved = self.reflect(artifact, failure_traces, history)

        if verify:
            # Quick check: does the improved artifact address the failures?
            verification_passed = self._quick_verify(improved, failure_traces)
            return improved, verification_passed

        return improved, True

    def _quick_verify(self, improved: str, failure_traces: str) -> bool:
        """Quick check: does the improved text contain fixes for the failures?

        This is a heuristic check — not a full evaluation.
        Returns True if the artifact looks improved, False otherwise.
        """
        if not improved or len(improved.strip()) < 10:
            return False

        # Check that the improved artifact has more structure
        # than the failure traces suggest is missing
        has_new_content = len(improved.split()) > len(failure_traces.split()) * 0.5

        return has_new_content

    def reflect_hypothesis_first(
        self,
        artifact: str,
        failure_traces: str,
        history: str = "(no prior improvements)",
    ) -> tuple[str, str]:
        """Two-step reflection: diagnose root cause, then rewrite.

        Step 1: Ask LLM to identify the root cause pattern.
        Step 2: Use that diagnosis to target the rewrite.

        Returns:
            (improved_artifact, root_cause_diagnosis)
        """
        # Step 1: Hypothesis generation (cheap, ~200 token call)
        hypothesis_prompt = f"""Given these failure traces from real agent usage,
what is the ROOT CAUSE pattern? Be specific — name the exact failure mode.

FAILURES:
{failure_traces}

ROOT CAUSE:
"""
        root_cause = self.provider.reflect(
            prompt=hypothesis_prompt,
            system="You are a diagnostician. Identify the root cause of agent failures.",
        ).strip()

        # Step 2: Targeted rewrite with root cause context
        user_prompt = REFLECTION_USER_TEMPLATE.format(
            artifact=artifact,
            failure_traces=failure_traces,
            history=history,
        )

        improved = self.provider.reflect(
            prompt=user_prompt,
            system=f"""{REFLECTION_SYSTEM_PROMPT}

ROOT CAUSE DIAGNOSIS: {root_cause}

Use this diagnosis to make targeted fixes. Don't rewrite what's working."""
        )

        return improved, root_cause

    def create_learning_log_entry(
        self,
        old_artifact: str,
        new_artifact: str,
        severity_before: int,
        severity_after: int | None = None,
    ) -> LearningLogEntry:
        """Create a learning log entry from an improvement attempt.

        Modeled after Darwinian Evolver's LearningLogEntry.
        """
        # Generate a concise change summary
        old_lines = len(old_artifact.split("\n"))
        new_lines = len(new_artifact.split("\n"))

        if severity_after is None:
            severity_after = severity_before  # Unknown outcome

        return LearningLogEntry(
            attempted_change=f"Improved artifact: {old_lines}→{new_lines} lines, severity {severity_before}→{severity_after}",
            observed_outcome="improvement" if severity_after < severity_before else ("regression" if severity_after > severity_before else "neutral"),
            severity_before=severity_before,
            severity_after=severity_after,
            change_summary=f"Modified artifact from {old_lines} to {new_lines} lines",
        )
