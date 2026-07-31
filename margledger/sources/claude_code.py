"""Claude Code JSONL transcript adapter.

Claude Code stores transcripts as JSONL under ``~/.claude/projects/``. Each
line is one message event:

    {"type": "user"|"assistant", "message": {"role": ..., "content": ...,
     "usage": {"input_tokens": N, "output_tokens": M}, "timestamp": "..."}}

There is **NO native agent-loop iteration marker** in this format — the
``message.usage.iterations`` field observed in real samples is a model-side
reasoning list (``[]``), not an iteration counter. So iterations are
**synthesized** from the assistant↔user turn sequence:

    iteration = one top-level user prompt + the assistant run it triggers
                (including all tool_use / tool_result sub-cycles) up to the
                next top-level user prompt.

Only ``usage.input_tokens`` / ``usage.output_tokens`` and ``timestamp`` are
real, model-attested fields — those drive the cost axis. The test-suite delta
is recovered from inline ``pytest`` summary lines embedded in tool results
(the machine-checkable oracle, grounded in the transcript itself).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ledger import RawIteration
from ..oracle import TestResult, parse_pytest_text


def _is_tool_result_message(message: dict) -> bool:
    """True when a ``user`` message is actually a tool_result (not a prompt)."""

    content = message.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                return True
    return False


def _is_top_level_prompt(message: dict) -> bool:
    """A user message that starts a new iteration (not a tool_result echo)."""

    role = message.get("role") or message.get("type")
    if role != "user":
        return False
    return not _is_tool_result_message(message)


def _extract_text(content: Any) -> str:
    """Flatten a message's content into a single text blob."""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif item.get("type") == "tool_result":
                    inner = item.get("content")
                    if isinstance(inner, str):
                        parts.append(inner)
                    elif isinstance(inner, list):
                        for sub in inner:
                            if isinstance(sub, dict) and isinstance(sub.get("text"), str):
                                parts.append(sub["text"])
                elif item.get("type") == "tool_use":
                    # Tool input sometimes carries the command being run.
                    inp = item.get("input")
                    if isinstance(inp, dict):
                        cmd = inp.get("command") or inp.get("cmd")
                        if isinstance(cmd, str):
                            parts.append(cmd)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def _parse_ts(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    # ISO 8601 with offset — let fromisoformat handle it.
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _usage_tokens(message: dict) -> tuple[int, int]:
    usage = message.get("usage") or {}
    if not isinstance(usage, dict):
        return (0, 0)
    inp = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    return (_to_int(inp), _to_int(out))


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse(path: str | Path) -> list[RawIteration]:
    """Parse a Claude Code JSONL transcript into synthesized iterations.

    Iterations are numbered from 1 in transcript order. Each carries real
    token deltas (summed across the iteration's assistant messages) and a
    best-effort end-of-iteration test snapshot when a ``pytest`` summary
    was observed in a tool result.
    """

    p = Path(path)
    events: list[dict] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Group events into iterations: a new iteration starts at a top-level user
    # prompt; everything up to the next top-level prompt belongs to it.
    iterations: list[list[dict]] = []
    current: list[dict] = []
    for event in events:
        message = event.get("message") if isinstance(event, dict) else None
        etype = event.get("type") if isinstance(event, dict) else None
        if message and etype == "user" and _is_top_level_prompt(message):
            if current:
                iterations.append(current)
            current = [event]
        else:
            current.append(event)
    if current:
        iterations.append(current)

    raw_iters: list[RawIteration] = []
    prev_end_ts: datetime | None = None
    for idx, group in enumerate(iterations, start=1):
        input_tokens = 0
        output_tokens = 0
        first_ts: datetime | None = None
        last_ts: datetime | None = None
        last_test: TestResult | None = None
        for event in group:
            message = event.get("message") if isinstance(event, dict) else None
            if not isinstance(message, dict):
                continue
            ts = _parse_ts(message.get("timestamp"))
            if ts is not None:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
            if message.get("role") == "assistant" or event.get("type") == "assistant":
                inp, out = _usage_tokens(message)
                input_tokens += inp
                output_tokens += out
            # Test oracle: scan every message's text for a pytest summary.
            text = _extract_text(message.get("content"))
            parsed = parse_pytest_text(text)
            if parsed is not None:
                last_test = parsed

        wall_s: float | None = None
        if first_ts is not None and last_ts is not None:
            wall_s = (last_ts - first_ts).total_seconds()
        # Cost provenance: tokens are real model-attested fields.
        raw_iters.append(
            RawIteration(
                iter=idx,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                wall_s=wall_s,
                test_result=last_test,
            )
        )
        prev_end_ts = last_ts

    return raw_iters
