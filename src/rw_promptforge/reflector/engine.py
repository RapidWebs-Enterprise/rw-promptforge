"""Reflector: the LLM-based reflection step.

Given a current artifact (skill/prompt), an evaluation trace, and optional
historical session data, the reflector asks an LLM to propose an improved version.

This is the CORE of the Simplify-Reflect-Evolve loop.
"""

from __future__ import annotations

from rw_promptforge.provider import Provider

REFLECTION_SYSTEM_PROMPT = """You are a prompt engineering expert who specializes in improving prompts and skill definitions for LLM-based agent systems.  # noqa: E501

Your task: given a CURRENT artifact (a skill or prompt file), a FAILURE TRACE showing what went wrong when the artifact was used, and optional SESSION DATA showing real-world usage patterns, produce an IMPROVED version of the artifact.  # noqa: E501

Rules:
1. Keep the same structure and format. Do not rewrite from scratch — preserve what works.
2. Fix only what the failure trace reveals as broken.
3. Add missing steps, clarify ambiguous instructions, and update outdated commands/tool names.
4. Be specific: if a step was wrong, write the correct one. If a trigger was missing, add it.
5. Return ONLY the improved artifact text. No explanation, no commentary.
6. If the artifact has YAML frontmatter, preserve and update it.
"""

REFLECTION_USER_TEMPLATE = """CURRENT ARTIFACT:
```
{artifact}
```

PREVIOUS VERSIONS (for context):
```
{history}
```

EVALUATION TRACE:
```
{trace}
```

SESSION DATA (real-world failures involving this artifact):
{session_context}

Produce the improved artifact:"""


class Reflector:
    """LLM-powered reflection engine — reads traces, proposes fixes."""

    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    def reflect(
        self,
        artifact: str,
        trace: str,
        session_context: str = "(no session data available)",
        history: str = "(no prior versions)",
    ) -> str:
        """Produce an improved artifact using the reflection LLM.

        Args:
            artifact: The original skill/prompt text.
            trace: Evaluation failure output.
            session_context: Extra context from session_db queries.
            history: Track of changes from prior reflection rounds.

        Returns:
            The LLM field response — ideally the improved artifact text.
        """
        user_prompt = REFLECTION_USER_TEMPLATE.format(
            artifact=artifact,
            trace=trace,
            session_context=session_context,
            history=history,
        )
        return self.provider.reflect(
            prompt=user_prompt,
            system=REFLECTION_SYSTEM_PROMPT,
        )
