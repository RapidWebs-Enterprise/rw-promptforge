# ADR-004: Direct SQLite Read for Session DB

**Date:** 2026-08-03
**Status:** Accepted

## Context

To enrich the reflection step, we need historical data: what sessions
used the target skill, did they succeed, and did the user correct
the agent afterward.

The Hermes session database is an FTS5-backed SQLite file at
`~/.hermes/session_db/sessions.db`.

## Decision

**Read the SQLite file directly** via the Python `sqlite3` stdlib
— this is read-only, no dependency on Hermes, and no need to spin up
an Hermes API endpoint.

## Why

1. **Simplicity:** The session db is already SQLite. `sqlite3` is in
   the standard library. We only need ~3 queries:
   - Find sessions where skill X was loaded
   - Find correction messages (user says "no", "wrong", "actually")
     shortly after a skill was used
   - Get the tool-call history for a given session
2. **No Hermes dependency:** The tool is standalone. It should work
   on a workstation with Hermes' session data but not necessarily a
   running Hermes agent daemon.
3. **Read-only safety:** No risk of corruption or interference with
   the live Hermes agent.

## Schema Dependency Risk

The session_db schema may evolve across Hermes versions. Our queries
should be pinned to the current schema version and auto-detect schema
changes. If the schema doesn't match, we fall back to "no session data
available" rather than crashing.

## Consequences

- The tool needs access to the Hermes user's `~/.hermes/` directory
- If Hermes isn't installed locally, session enrichment is unavailable
  (the optimizer still works — just without historical context)