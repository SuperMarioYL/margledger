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
from pathlib import Path
from typing import Any

from ..ledger import RawIteration
from ..oracle import TestResult, parse_pytest_text
from . import claude_code


def _looks_enveloped(event: Any) -> bool:
    return isinstance(event, dict) and isinstance(event.get("message"), dict)


def parse(path: str | Path) -> list[RawIteration]:
    """Parse a generic JSONL transcript. Falls back to Claude Code parsing
    when the file is in the enveloped format; otherwise normalizes flat
    messages into the envelope and reuses the same synthesis."""

    p = Path(path)
    raw_lines: list[str] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                raw_lines.append(line)

    if not raw_lines:
        return []

    first = json.loads(raw_lines[0])
    if _looks_enveloped(first):
        return claude_code.parse(p)

    # Flat format: normalize each line into the Claude Code envelope so the
    # same synthesis path applies. The envelope is {type, message{role,...}}.
    normalized: list[str] = []
    for line in raw_lines:
        msg = json.loads(line)
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
    tmp = p.with_suffix(p.suffix + ".normalized.jsonl")
    tmp.write_text("\n".join(normalized) + "\n", encoding="utf-8")
    try:
        return claude_code.parse(tmp)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


__all__ = ["parse", "TestResult", "parse_pytest_text"]
