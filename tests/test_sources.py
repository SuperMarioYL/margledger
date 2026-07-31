"""Tests for the m3 sources — the best-effort, schema_unverified Cursor
``state.vscdb`` adapter and the generic JSONL adapter.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from margledger.sources import cursor, generic_jsonl

FIX = Path(__file__).parent / "fixtures"


def _make_vscdb(path: Path, sessions: dict[str, dict]):
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)"
    )
    for key, value in sessions.items():
        conn.execute(
            "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )
    conn.commit()
    conn.close()


def test_cursor_parse_flags_schema_unverified(tmp_path):
    db = tmp_path / "state.vscdb"
    session = {
        "fullBubbles": [
            {"type": "chat", "text": "iter 1 prompt",
             "timingInfo": {"startTime": "2024-05-01T00:00:00", "endTime": "2024-05-01T00:00:30"}},
            {"type": "assistant", "text": "response"},
            {"type": "chat", "text": "iter 2 prompt",
             "timingInfo": {"startTime": "2024-05-01T00:01:00", "endTime": "2024-05-01T00:01:45"}},
            {"type": "assistant", "text": "response"},
        ]
    }
    _make_vscdb(db, {"composerData:abc": session})
    raw = cursor.parse(db)
    assert len(raw) == 2
    assert all(r.schema_unverified is True for r in raw)
    # Wall-clock is emitted only where timingInfo is present.
    assert raw[0].wall_s == 30.0
    assert raw[1].wall_s == 45.0
    # No real model tokens for Cursor — flagged sparse.
    assert all(r.marginal_tokens == 0 for r in raw)
    assert all(r.sparse is True for r in raw)


def test_cursor_parse_raises_on_non_cursor_db(tmp_path):
    """A file with no recognized KV table is not a Cursor DB — raise honestly."""
    import pytest

    db = tmp_path / "empty.vscdb"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE unrelated (id INTEGER)")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError):
        cursor.parse(db)


def test_cursor_parse_returns_empty_when_no_sessions(tmp_path):
    """A valid Cursor DB with no composerData sessions yields zero iterations."""
    db = tmp_path / "state.vscdb"
    _make_vscdb(db, {})  # cursorDiskKV present, no rows
    raw = cursor.parse(db)
    assert raw == []


def test_cursor_parse_sparse_when_no_timing(tmp_path):
    db = tmp_path / "state.vscdb"
    session = {
        "fullBubbles": [
            {"type": "chat", "text": "no timing info here"},
            {"type": "assistant", "text": "response"},
        ]
    }
    _make_vscdb(db, {"composerData:xyz": session})
    raw = cursor.parse(db)
    assert len(raw) == 1
    assert raw[0].wall_s is None
    assert raw[0].schema_unverified is True


def test_generic_jsonl_delegates_for_flat_format(tmp_path):
    # Flat per-line message contract, no {type, message} envelope.
    lines = [
        {"role": "user", "content": "go", "timestamp": "2024-05-01T00:00:00"},
        {"role": "assistant", "content": [{"type": "text", "text": "ok"}],
         "usage": {"input_tokens": 100, "output_tokens": 50},
         "timestamp": "2024-05-01T00:00:05"},
        {"role": "user", "content": "again", "timestamp": "2024-05-01T00:01:00"},
        {"role": "assistant", "content": [{"type": "text", "text": "ok2"}],
         "usage": {"input_tokens": 80, "output_tokens": 40},
         "timestamp": "2024-05-01T00:01:05"},
    ]
    p = tmp_path / "flat.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    raw = generic_jsonl.parse(p)
    assert len(raw) == 2
    assert raw[0].marginal_tokens == 150
    assert raw[1].marginal_tokens == 120


def test_generic_jsonl_handles_enveloped_format():
    # The Claude Code fixture IS the enveloped format; generic adapter delegates.
    raw = generic_jsonl.parse(FIX / "sample_transcript.jsonl")
    assert len(raw) == 10
    assert raw[3].test_result.passed == 55
