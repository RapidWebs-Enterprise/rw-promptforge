# ADR-001: Python over Rust

**Date:** 2026-08-03
**Status:** Accepted

## Context

We need a standalone CLI for iterative prompt/skill optimization.
The workstation has Rust tooling but also a well-established Python
workflow (UV, pytest, ruff, mypy). The core loop is I/O-bound
(shell out, HTTP call to LLM) — compute speed is irrelevant.

## Decision

**Python 3.10+ with src layout.**

## Rationale

1. **Speed irrelevant:** The bottleneck is LLM API calls and shell
   invocations — not CPU cycles. Python's I/O performance is fine.
2. **Ecosystem fit:** Hermes session_db is SQLite — Python has `sqlite3`
   stdlib. YAML frontmatter: `pyyaml`. HTTP: `httpx`. No friction.
3. **Iteration speed:** We can build the core loop in ~200 LOC Python
   vs. ~500+ LOC Rust with more ceremony around error types, async
   runtimes, and SQL client wiring.
4. **Workspace consistency:** All active RapidWebs projects (NexusAgent,
   ast-tools, hermes-help, rw-aiai, rw_codegate) are Python. Adding
   one more Python project keeps skills and conventions unified.
5. **Deploy anywhere:** `pip install` on the workstation (4GB), the
   dev VM, or any server. No rustup+cargo required.

## Trade-offs

- Slower startup (~50ms vs ~5ms) — negligible for an interactive CLI
- Larger install size (Python runtime) — already present on all target
  machines
- No single-binary compile — mitigated by `pip install` being trivial

## Consequences

- Uses `click` + `rich` for CLI (RapidWebs standard)
- Type-hinted and mypy-strict per coding standards
- TDD through pytest