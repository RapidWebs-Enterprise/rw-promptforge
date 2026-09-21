# ADR-013 Amendment: Adopt pydantic-settings

**Supersedes:** ADR-013 §Decision (hand-rolled loaders)
**Date:** 2026-09-20
**Status:** Accepted

## Change

**FROM:** Hand-roll 4 loader modules (~400 LOC) with custom deep-merge and provenance tracking
**TO:** Use `pydantic-settings` with 4 custom `PydanticBaseSettingsSource` subclasses (~160 LOC) + explicit CLI allowlist

## Rationale

The reverse audit (R2) correctly identified that hand-rolling absorbs complexity that:
1. `pydantic-settings` has already solved (env parsing, type coercion, dotenv loading)
2. Would otherwise be re-implemented with new edge cases
3. Violates the "don't build what exists" principle

**The hand-roll justification in v1 ("TOML-only, custom walk-up, provenance") is wrong** — all three are achievable on top of pydantic-settings.

## Concrete Shifts

| v1 | v2 |
|----|-----|
| 4 hand-rolled loader modules | 4 `PydanticBaseSettingsSource` subclasses |
| Custom `_deep_merge` recursion | pydantic-settings built-in chain |
| Provenance via custom merge walk | Provenance mixin on each source |
| Click `locals()` mapped via `cli_loader.py` | Explicit `CLI_OVERRIDE_MAP` dict |

## Files Replaced

| v1 File | v2 Replacement |
|---------|----------------|
| `configs/env_loader.py` | `configs/sources/cli_source.py` (Click allowlist) |
| `configs/env_loader.py` (env part) | pydantic-settings built-in `env_settings` |
| `configs/env_loader.py` (dotenv part) | `configs/sources/dotenv_source.py` |
| `configs/file_loader.py` (user) | `configs/sources/user_toml_source.py` |
| `configs/file_loader.py` (project) | `configs/sources/project_toml_source.py` |
| `configs/cli_loader.py` | `configs/sources/cli_source.py` (allowlist) |
| `configs/core.py` (merge) | `configs/core.py` (settings_customise_sources only) |

## Result

- ~400 LOC hand-rolled → ~240 LOC total (models + sources + core + CLI map)
- Precedence chain identical to v1 spec
- Secrets handling via pydantic `SecretStr` (G1 fix)
- Extra key rejection via `extra="forbid"` (G2 fix)
- Provenance carried as side-channel on each source

## Test Matrix

Same 22 tests as plan v2 §"Fix: Test Matrix Expansion".
