"""Generic JSONL transcript adapter.

Accepts the flat per-line message contract used by many agent loops that don't
emit Claude Code's ``{type, message}`` envelope:

    {"role": "user"|"assistant", "content": ..., "usage": {...},
     "timestamp": "..."}

and also tolerates the Claude Code envelope (delegating to
:mod:`claude_code`). Iterations are synthesized from the assistant↔user turn
sequence — no native iteration marker is required.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from ..ledger import RawIteration
from ..oracle import TestResult, parse_pytest_text
from . import claude_code


def _looks_enveloped(event: Any) -> bool:
    return isinstance(event, dict) and isinstance(event.get("message"), dict)


def _read_events(path: Path) -> list[Any]:
    """Parse the JSONL file, skipping malformed lines.

    A live-written transcript routinely ends with a partially-written line;
    like :func:`claude_code.parse`, we tolerate and skip anything that does
    not decode instead of crashing the whole trace.
    """

    events: list[Any] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def parse(path: str | Path) -> list[RawIteration]:
    """Parse a generic JSONL transcript. Falls back to Claude Code parsing
    when the file is in the enveloped format; otherwise normalizes flat
    messages into the envelope and reuses the same synthesis."""

    p = Path(path)
    events = _read_events(p)
    if not events:
        return []

    if _looks_enveloped(events[0]):
        return claude_code.parse(p)

    # Flat format: normalize each event into the Claude Code envelope so the
    # same synthesis path applies. The envelope is {type, message{role,...}}.
    normalized: list[str] = []
    for msg in events:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or msg.get("type") or "user"
        envelope = {
            "type": role,
            "message": {
                "role": role,
                "content": msg.get("content"),
                "usage": msg.get("usage") or {},
                "timestamp": msg.get("timestamp"),
            },
        }
        normalized.append(json.dumps(envelope))
    if not normalized:
        return []
    # Normalize in the system tempdir — never write scratch files into the
    # transcript's own directory (it may be read-only, and sibling writes
    # race concurrent parses of the same file).
    with tempfile.NamedTemporaryFile(
        "w", suffix=".normalized.jsonl", encoding="utf-8", delete=False
    ) as tmp_fh:
        tmp_fh.write("\n".join(normalized) + "\n")
        tmp = Path(tmp_fh.name)
    try:
        return claude_code.parse(tmp)
    finally:
        tmp.unlink(missing_ok=True)


__all__ = ["parse", "TestResult", "parse_pytest_text"]
