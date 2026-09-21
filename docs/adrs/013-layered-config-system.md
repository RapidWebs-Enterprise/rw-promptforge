# ADR-013: Layered Configuration System

**Status:** Accepted
**Date:** 2026-09-14

## Decision

`rw-promptforge` adopts a 6-layer Pydantic-based configuration chain, modeled directly on `rw_telebot`'s `src/rw_telebot/configs/` package.

## Decisions

1. **Format:** TOML only (not YAML). Single format keeps the loader simple, matches `pyproject.toml` ecosystem conventions, and avoids the YAML surface area (anchors, aliases, implicit types) that bit us in the past.

2. **Env prefix:** `RW_PROMPTFORGE_` (long form). Unambiguous in infrastructure-wide process dumps (`ps`, `systemd show`), no collision risk with sibling tools. Nested keys split on `__`.

3. **Project config resolution:** **Walk up to git-root boundary.** Python equivalent of `git rev-parse --show-toplevel`:
   - Walk up from `cwd` looking for `./config.toml`, then `./config/rw-promptforge.toml` at each level
   - Stop when we hit `.git/` (project root) or filesystem root
   - First match wins and terminates the walk
   - `cwd` itself always searched first
   
   **Rationale:** lets a per-project `config.toml` at repo root override `~/`-level config regardless of where the user invokes the CLI inside the project tree. Avoids the "cd'd one directory too deep and lost my config" footgun, while the first-match-wins rule means a subfolder can still override the project root when deliberate.

## Precedence (low → high)

1. Pydantic defaults
2. User TOML (`~/.config/rw-promptforge/config.toml`)
3. Project TOML (walk-up search as above)
4. `.env` file at cwd
5. `RW_PROMPTFORGE_*` env vars
6. CLI flags

## Consequences

- Single `load_config()` entry point returns a fully validated `RootConfig`
- Component code reads `config.ml.endpoint`, never `os.environ`
- Old ad-hoc env vars (`RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL`) get one release with deprecation warnings, then removed
- `rw-promptforge config show` reports per-leaf provenance for debugging

## References

- SPEC: `docs/specs/spec-layered-config.md`
- Pattern source: `rw_telebot/src/rw_telebot/configs/`
