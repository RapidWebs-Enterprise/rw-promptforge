# ADR-011: Embedding Cache Location

**Date:** 2026-09-14  
**Status:** Accepted  
**Context:** Where to store embedding cache for reuse across runs

## Decision

Store embedding cache in XDG-compliant location: `~/.cache/rw-promptforge/embeddings.pkl`

## Rationale

1. **XDG compliance:** Follows Linux standards (`$XDG_CACHE_HOME` or `~/.cache`)
2. **Not in .hermes/:** User explicit preference to avoid mixing project state with agent state
3. **Auto-cleanable:** System cleaners (bleachbit, etc.) can remove without affecting other systems
4. **Fast access:** Local filesystem, no network overhead
5. **Persistent:** Survives reboots, only lost on explicit cleanup

## Implementation

```python
from pathlib import Path
import os

CACHE_DIR = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "rw-promptforge"
CACHE_FILE = CACHE_DIR / "embeddings.pkl"

def ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
```

## Eviction Policy

- **Max entries:** 10,000 embeddings
- **Strategy:** LRU (Least Recently Used)
- **Trigger:** On insertion when at capacity, evict oldest entry
- **Rationale:** Covers ~500MB of text, more than sufficient for failure trace analysis

## TTL

**None.** Embeddings are deterministic functions of text content. No staleness possible.

## Cache Invalidation

Users can manually clear cache:
```bash
rm -rf ~/.cache/rw-promptforge/
```

Or programmatically:
```python
from rw_promptforge.cache import clear_cache
clear_cache()
```

## References

- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
- [Python pathlib documentation](https://docs.python.org/3/library/pathlib.html)
