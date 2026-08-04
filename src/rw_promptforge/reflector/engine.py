"""Reflector: the LLM-based reflection step.

Given a current artifact (skill/SOUL.md), REAL failure traces from session_db,
and the history of improvements, the reflector asks an LLM to produce an
improved version that prevents these failures from recurring.

This is the CORE of the Simplify-Reflect-Evolve loop — and the key difference
from a simple quality gate: we use REAL usage data, not synthetic evals.
"""

from __future__ import annotations

from rw_promptforge.provider import Provider

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
"""

REFLECTION_USER_TEMPLATE = """CURRENT ARTIFACT:
```
{artifact}
```

REAL FAILURE TRACES (from actual agent usage sessions):
{failure_traces}

PREVIOUS IMPROVEMENTS (for context):
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
    ) -> str:
        """Produce an improved artifact using real failure traces.

        Args:
            artifact: The original skill/SOUL.md text.
            failure_traces: Formatted failure traces from session_db.
            history: Track of improvements from prior reflection rounds.

        Returns:
            The improved artifact text.
        """
        user_prompt = REFLECTION_USER_TEMPLATE.format(
            artifact=artifact,
            failure_traces=failure_traces,
            history=history,
        )
        return self.provider.reflect(
            prompt=user_prompt,
            system=REFLECTION_SYSTEM_PROMPT,
        )
