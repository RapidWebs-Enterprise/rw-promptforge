"""Tests for SessionDBReader skill scoping (v5 — tool_name + content columns).

Tests that:
1. Global queries (skill_name=None) return all traces
2. Scoped queries filter to sessions where the skill was loaded
3. Nonexistent skills return empty results
4. Different skills return different trace sets
5. find_tool_failures respects skill_name scoping
"""

from __future__ import annotations

import sqlite3
import json
import tempfile
import os
from pathlib import Path

import pytest

from rw_promptforge.datastore.session_db import SessionDBReader
from rw_promptforge.datastore.models import FailureTrace


@pytest.fixture
def test_db(tmp_path):
    """Create a minimal test state.db with skill_view calls and corrections."""
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    # sessions table
    conn.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY, source TEXT, user_id TEXT,
            session_key TEXT, chat_id TEXT, chat_type TEXT,
            model TEXT, system_prompt TEXT, started_at REAL
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

    # Session A: loaded skill "ast-tools-usage", then user corrected
    conn.execute(
        "INSERT INTO sessions VALUES ('sess-a', 'web', 'u1', 'k1', 'c1', 'web', 'm1', 'system prompt', 1000.0)"
    )
    # skill_view tool result for ast-tools-usage
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_name, timestamp) VALUES (?, 'tool', ?, 'skill_view', 1001.0)",
        ("sess-a", json.dumps({"success": True, "name": "ast-tools-usage"})),
    )
    # User correction in same session
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_name, timestamp) VALUES (?, 'user', ?, NULL, 1002.0)",
        ("sess-a", "no, thats not what I meant at all"),
    )

    # Session B: loaded a different skill, then user corrected
    conn.execute(
        "INSERT INTO sessions VALUES ('sess-b', 'web', 'u2', 'k2', 'c2', 'web', 'm2', 'different prompt', 2000.0)"
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_name, timestamp) VALUES (?, 'tool', ?, 'skill_view', 2001.0)",
        ("sess-b", json.dumps({"success": True, "name": "spectral-clustering"})),
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_name, timestamp) VALUES (?, 'user', ?, NULL, 2002.0)",
        ("sess-b", "you were supposed to do it differently"),
    )

    # Session C: no skill loaded, but user corrected
    conn.execute(
        "INSERT INTO sessions VALUES ('sess-c', 'web', 'u3', 'k3', 'c3', 'web', 'm3', 'no skill', 3000.0)"
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
    assert "skill_view" in where
    assert "skill_manage" in where
    assert params == ('%"test-skill"%',)

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