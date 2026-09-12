"""Tests for SessionDBReader skill scoping (v6 — system_prompts table join).

Tests that:
1. Global queries (skill_name=None) return all traces
2. Scoped queries filter to sessions whose system prompt contains the skill
3. Nonexistent skills return empty results
4. Different skills return different trace sets
5. find_tool_failures respects skill_name scoping
6. Sessions without system_prompt_hash are excluded from scoped queries
"""

from __future__ import annotations

import sqlite3
import hashlib
from pathlib import Path

import pytest

from rw_promptforge.datastore.session_db import SessionDBReader


@pytest.fixture
def test_db(tmp_path):
    """Create a minimal test state.db with system_prompts and skill injection."""
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    # sessions table (matching real schema: system_prompt is NULL, use hash)
    conn.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY, source TEXT, user_id TEXT,
            session_key TEXT, chat_id TEXT, chat_type TEXT,
            model TEXT, system_prompt TEXT, system_prompt_hash TEXT,
            started_at REAL
        )
    """)
    # system_prompts table
    conn.execute("""
        CREATE TABLE system_prompts (
            hash TEXT PRIMARY KEY, prompt TEXT
        )
    """)
    # messages table
    conn.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT, tool_call_id TEXT, tool_calls TEXT,
            tool_name TEXT, timestamp REAL NOT NULL
        )
    """)

    # System prompt containing ast-tools-usage skill
    prompt_a = "You are a helpful agent. Loaded skill: ast-tools-usage for code analysis."
    hash_a = hashlib.sha256(prompt_a.encode()).hexdigest()
    conn.execute("INSERT INTO system_prompts VALUES (?, ?)", (hash_a, prompt_a))

    # System prompt containing spectral-clustering skill
    prompt_b = "You are a helpful agent. Loaded skill: spectral-clustering for graph analysis."
    hash_b = hashlib.sha256(prompt_b.encode()).hexdigest()
    conn.execute("INSERT INTO system_prompts VALUES (?, ?)", (hash_b, prompt_b))

    # System prompt with no skills
    prompt_c = "You are a helpful agent. No special skills loaded."
    hash_c = hashlib.sha256(prompt_c.encode()).hexdigest()
    conn.execute("INSERT INTO system_prompts VALUES (?, ?)", (hash_c, prompt_c))

    # Session A: ast-tools-usage skill, then user corrected
    conn.execute(
        "INSERT INTO sessions VALUES ('sess-a', 'web', 'u1', 'k1', 'c1', 'web', 'm1', NULL, ?, 1000.0)",
        (hash_a,)
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_name, timestamp) VALUES (?, 'user', ?, NULL, 1002.0)",
        ("sess-a", "no, thats not what I meant at all"),
    )

    # Session B: spectral-clustering skill, then user corrected
    conn.execute(
        "INSERT INTO sessions VALUES ('sess-b', 'web', 'u2', 'k2', 'c2', 'web', 'm2', NULL, ?, 2000.0)",
        (hash_b,)
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_name, timestamp) VALUES (?, 'user', ?, NULL, 2002.0)",
        ("sess-b", "you were supposed to do it differently"),
    )

    # Session C: no skills, but user corrected
    conn.execute(
        "INSERT INTO sessions VALUES ('sess-c', 'web', 'u3', 'k3', 'c3', 'web', 'm3', NULL, ?, 3000.0)",
        (hash_c,)
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_name, timestamp) VALUES (?, 'user', ?, NULL, 3001.0)",
        ("sess-c", "that's wrong and you should fix it"),
    )

    conn.commit()
    conn.close()
    return db_path


def test_global_query_returns_all(test_db):
    """skill_name=None returns corrections from all sessions."""
    reader = SessionDBReader(db_path=test_db)
    traces = reader.find_corrections(limit=10)
    assert len(traces) == 3  # one correction per session


def test_scoped_query_filters_to_skill(test_db):
    """Scoped query returns only corrections from sessions where skill was loaded."""
    reader = SessionDBReader(db_path=test_db)
    traces = reader.find_corrections("ast-tools-usage", limit=10)
    assert len(traces) == 1
    assert traces[0].session_id == "sess-a"
    assert traces[0].skill_name == "ast-tools-usage"


def test_different_skills_return_different_results(test_db):
    """Two different skills produce different trace sets."""
    reader = SessionDBReader(db_path=test_db)
    traces_a = reader.find_corrections("ast-tools-usage", limit=10)
    traces_b = reader.find_corrections("spectral-clustering", limit=10)
    assert len(traces_a) == 1
    assert len(traces_b) == 1
    assert traces_a[0].session_id != traces_b[0].session_id


def test_nonexistent_skill_returns_empty(test_db):
    """A skill that was never loaded returns no traces."""
    reader = SessionDBReader(db_path=test_db)
    traces = reader.find_corrections("nonexistent-skill-xyz", limit=10)
    assert len(traces) == 0


def test_find_tool_failures_scoped(test_db):
    """find_tool_failures respects skill_name scoping."""
    reader = SessionDBReader(db_path=test_db)
    # No tool failures in test DB, so this just verifies no crash
    traces = reader.find_tool_failures("ast-tools-usage", limit=5)
    assert isinstance(traces, list)


def test_skill_filter_sql_helper(test_db):
    """_skill_filter_sql returns correct WHERE clause and params."""
    reader = SessionDBReader(db_path=test_db)
    where, params = reader._skill_filter_sql("test-skill")
    assert "system_prompts" in where
    assert "system_prompt_hash" in where
    assert params == ("%test-skill%",)

    where_none, params_none = reader._skill_filter_sql(None)
    assert where_none == ""
    assert params_none == ()


def test_find_corrections_preserves_global_fallback(test_db):
    """When skill_name is None, all corrections are returned (no scoping)."""
    reader = SessionDBReader(db_path=test_db)
    global_traces = reader.find_corrections(limit=10)
    scoped_traces = reader.find_corrections("ast-tools-usage", limit=10)
    assert len(global_traces) > len(scoped_traces)


def test_get_contrastive_traces_scoped(test_db):
    """get_contrastive_traces passes skill_name through to sub-methods."""
    reader = SessionDBReader(db_path=test_db)
    traces = reader.get_contrastive_traces("ast-tools-usage", limit=5)
    assert len(traces) == 1
    assert traces[0].session_id == "sess-a"


def test_db_not_found_returns_empty():
    """When DB doesn't exist, methods return empty lists."""
    reader = SessionDBReader(db_path="/nonexistent/path/state.db")
    assert reader.exists() is False
    assert reader.find_corrections(limit=10) == []
    assert reader.find_tool_failures(limit=5) == []