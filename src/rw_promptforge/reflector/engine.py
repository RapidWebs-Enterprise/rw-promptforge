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

import re
import sys

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


class BudgetExceededError(Exception):
    """Raised when an LLM reflection result exceeds its size budget.

    Replaces the old silent head+marker+tail splice that corrupted the
    production SOUL.md on 2026-08-05 (three `... [TRUNCATED] ...` markers
    baked into live content). Callers decide the policy: retry with a
    compression instruction or keep the original content — but the
    un-truncated result is never silently mutilated again.
    """

    def __init__(self, context: str, actual: int, budget: int):
        self.context = context
        self.actual_chars = actual
        self.budget_chars = budget
        super().__init__(
            f"{context}: result is {actual} chars, budget is {budget} "
            f"(overflow {actual - budget})"
        )


class Reflector:
    """Generates improved prompts from failure analysis."""

    VALID_OVERFLOW_STRATEGIES = ("retry", "fail")

    def __init__(self, provider: Provider, on_overflow: str = "retry"):
        self.provider = provider
        if on_overflow not in self.VALID_OVERFLOW_STRATEGIES:
            raise ValueError(
                f"on_overflow must be one of {self.VALID_OVERFLOW_STRATEGIES}, "
                f"got {on_overflow!r}"
            )
        self.on_overflow = on_overflow
        self.max_retries = 1

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
        # Enforce size budget — never splice content mid-stream.
        # (The old head+marker+tail splice corrupted production SOUL.md
        # on 2026-08-05; see BudgetExceededError docstring.)
        if size_budget > 0 and len(result) > size_budget:
            result = self._fit_to_budget(
                result,
                size_budget,
                context="full-artifact reflection",
            )
        return result

    def _fit_to_budget(self, result: str, budget: int, context: str) -> str:
        """Bring an oversize reflection result within budget, or raise.

        Strategy ``retry`` (default): re-prompt the provider with an explicit
        compression instruction, up to ``max_retries`` times. If every retry
        still overflows, raise BudgetExceededError.

        Strategy ``fail``: raise BudgetExceededError immediately.
        """
        if len(result) <= budget:
            return result
        original_size = len(result)
        if self.on_overflow == "retry":
            for _attempt in range(self.max_retries):
                retry_prompt = (
                    f"Your previous response was {len(result)} characters, exceeding the "
                    f"budget of {budget}. Rewrite it to fit within {budget} characters "
                    f"while preserving all substantive content.\n\nPrevious response:\n{result}"
                )
                result = self.provider.reflect(
                    prompt=retry_prompt,
                    system=(
                        "You are a precise editor. Compress the provided text to fit the "
                        "stated character budget. Preserve every rule, protocol, and "
                        "structural element; shorten only prose."
                    ),
                ).strip()
                if len(result) <= budget:
                    return result
        raise BudgetExceededError(context, original_size, budget)

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
        size_budget: int = 0,
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

## Root Cause Analysis
{root_cause}

Apply the fix described above. Ensure the rewrite addresses the root cause.""",
        ).strip()

        if size_budget > 0 and len(improved) > size_budget:
            improved = self._fit_to_budget(improved, size_budget, context="artifact")

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

    # ── LLM Judge ──────────────────────────────────────────────────────

    JUDGE_SYSTEM_PROMPT = """You are a strict evaluator of LLM agent instructions (SOUL files, skills, protocols).
You are given:
1. A BASELINE artifact (the current version)
2. A PROPOSED REVISION (candidate improvement)
3. REAL FAILURES the revision is meant to fix

Rate the REVISION from 0.0 to 1.0 on how well it fixes the listed failures
while preserving what already works:

- 1.0: fully addresses the failures with clear, actionable, non-redundant fixes; no regressions
- 0.75: mostly addresses the failures, minor gaps or wordiness
- 0.5: partial fix — addresses some failures, misses others
- 0.25: barely any meaningful change / fix is superficial
- 0.0: no improvement, makes things worse, or drops/breaks existing structure

Be strict: cosmetic rewording without addressing the failures scores low.
Return ONLY the numeric score — nothing else, no explanation."""

    def judge(self, baseline: str, candidate: str, failure_traces: str) -> float:
        """LLM-as-judge: score candidate (0..1) vs baseline for the failures.

        Deterministic-ish: temperature 0.3, single call. Returns 0.0 when the
        judge cannot score (empty traces, parse failure) — safe default.
        """
        if not failure_traces or len(failure_traces.strip()) < 20:
            return 0.0
        # Baseline/candidate are truncated for token economy
        prompt = f"""BASELINE ARTIFACT:
```
{baseline[:8000]}
```

PROPOSED REVISION:
```
{candidate[:8000]}
```

REAL FAILURES TO FIX:
{failure_traces[:4000]}

Score the REVISION 0.0-1.0 (see rules). Return ONLY the number."""
        try:
            raw = self.provider.reflect(prompt=prompt, system=self.JUDGE_SYSTEM_PROMPT).strip()
            m = re.search(r"(-?\d+(?:\.\d+)?)", raw)
            if not m:
                return 0.0
            return max(0.0, min(1.0, float(m.group(1))))
        except Exception:
            return 0.0

    # ── Chunked section-level reflection ───────────────────────────────

    SECTION_REFINE_SYSTEM_PROMPT = """You are an expert editor of LLM agent instruction files.
You are given ONE SECTION of a larger SOUL.md / skill file, plus REAL failure
traces from actual agent usage. Rewrite ONLY this section so that the failures
are prevented, while preserving:

1. The exact same tag and name (e.g. <protocol name="x"> stays <protocol name="x">).
2. The section's role and structure — you are tightening content, not restructuring.
3. Any YAML frontmatter, priorities, or attributes on the opening tag.

Rules:
- Be SPECIFIC: where a failure trace shows the agent doing X wrongly, make the
  instruction say exactly what to do instead, with a concrete example.
- Tighten: cut redundancy, keep it dense and actionable.
- Do NOT add other sections, headers, or commentary.
- Return ONLY the section content (the text between <tag name="x"> and </tag>),
  with no code fences and no explanation."""

    SECTION_REFINE_USER_TEMPLATE = """SECTION TO IMPROVE (tag: {tag}, name: {name}):
```
{section}
```

REAL FAILURE TRACES:
{failure_traces}

PREVIOUS IMPROVEMENTS (Learning Log):
{history}

Return ONLY the improved section content — the text that goes inside <{tag} name="{name}">...</{tag}>."""

    def reflect_sections(
        self,
        sections: list[tuple[str, str, str]],
        failure_traces: str,
        history: str = "(no prior improvements)",
        size_budget: int = 0,
        max_workers: int = 8,
    ) -> dict[str, str]:
        """Refine each section independently, return {section_name: new_content}.

        Chunked reflection: a full 50KB artifact cannot be meaningfully
        rewritten in one 8K-token call (models echo the input verbatim).
        Refining each section separately makes every call small enough for
        a real rewrite. Sections are refined CONCURRENTLY (independent
        calls) — 23 sections take ~4 rounds of 8 parallel calls instead of
        23 sequential round-trips. Sections are keyed by name.
        """
        tasks: list[tuple[str, str, str]] = [
            (tag, name, content)
            for tag, name, content in sections
            if content.strip()
        ]
        improved: dict[str, str] = {}

        def _refine_one(task: tuple[str, str, str]) -> tuple[str, str] | None:
            tag, name, content = task
            user_prompt = self.SECTION_REFINE_USER_TEMPLATE.format(
                tag=tag,
                name=name,
                section=content[:6000],
                failure_traces=failure_traces[:3000],
                history=history[:1500],
            )
            try:
                result = self.provider.reflect(
                    prompt=user_prompt,
                    system=self.SECTION_REFINE_SYSTEM_PROMPT,
                ).strip()
                # Strip markdown code fences models often wrap output in
                result = _strip_code_fences(result)
                # Enforce per-section size budget (relative to original section).
                # Never splice — retry with compression or fail loud and keep
                # the original section (handled by the except below).
                if size_budget > 0 and len(result) > size_budget:
                    result = self._fit_to_budget(
                        result,
                        size_budget,
                        context=f"section {name!r}",
                    )
                if result and len(result) >= 10:
                    return name, result
            except BudgetExceededError as exc:
                print(f"  ⚠ {exc} — keeping original section", file=sys.stderr, flush=True)
                return name, content  # preserve original in results
            except Exception:
                pass
            return None  # keep original section on failure

        import concurrent.futures
        import time

        # Rate limiter: max 2 calls per second per worker to avoid 429 errors
        _last_call: float = 0.0

        def _rate_limited_refine(task: tuple[str, str, str]) -> tuple[str, str] | None:
            nonlocal _last_call
            # Stagger start by 50ms per worker to spread load at the provider
            if _last_call > 0:
                elapsed = time.time() - _last_call
                if elapsed < 0.5:
                    time.sleep(0.5 - elapsed)
            _last_call = time.time()
            return _refine_one(task)

        workers = min(max_workers, max(len(tasks), 1))
        done_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_rate_limited_refine, t) for t in tasks]
            for fut in concurrent.futures.as_completed(futures):
                done_count += 1
                if done_count % 4 == 0 or done_count == len(tasks):
                    print(f"  ↳ sections refined: {done_count}/{len(tasks)}", flush=True)
                result = fut.result()
                if result:
                    name, content = result
                    improved[name] = content
        return improved


def _strip_code_fences(text: str) -> str:
    """Remove ```...``` fences but KEEP the content between them."""
    if "```" not in text:
        return text
    lines = text.splitlines()
    out: list[str] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        out.append(line)
    return "\n".join(out).strip()
