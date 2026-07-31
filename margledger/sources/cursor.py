"""Cursor ``state.vscdb`` adapter — BEST-EFFORT, ``schema_unverified``.

Honest scope from the real sample (136 ``composerData:<uuid>`` sessions under
``cursorDiskKV``): the only token-bearing bubble fields
``tokenCountUpUntilHere`` / ``tokenDetailsUpUntilHere`` measure **per-FILE
attached-context size, NOT model input/output tokens**, and are populated in
only ~1/136 sessions. The native ``isCapabilityIteration`` marker is **never
set** (0/136); per-bubble ``timingInfo`` wall-clock exists on only ~12/136
sessions.

So this adapter emits ``marginal_wall_s`` only where ``timingInfo`` is
present and reports the token fields as a **best-effort, sparse, per-file-
context proxy** (clearly labeled, NOT the model-token primitive the Claude
Code source provides). Every iteration it emits carries
``schema_unverified=True`` and ``sparse=True`` where applicable. The headline
~50k-tokens-saved math is driven by the Claude Code (m1/m2) ledger; Cursor is
a secondary, sparsely-populated source, not the source of the token math.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ledger import RawIteration


SCHEMA_UNVERIFIED = True


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value) / 1000.0)
    except (ValueError, OSError):
        return None
    if isinstance(value, str):
        cleaned = value.rstrip("Z")
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def _iter_bubbles(bubble: Any) -> list[dict]:
    """Yield the bubble dicts from a Cursor composer bubble payload."""

    if isinstance(bubble, dict):
        if isinstance(bubble.get("bubbles"), list):
            return [b for b in bubble["bubbles"] if isinstance(b, dict)]
        if "type" in bubble or "text" in bubble:
            return [bubble]
    return []


def _bubbles_from_session(session_value: Any) -> list[dict]:
    """Extract bubbles from a Cursor composerData session value.

    The session value is a JSON blob (possibly stringified twice) with a
    ``fullBubbles`` / ``bubbles`` list. We are deliberately lenient.
    """

    payload: Any = session_value
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    if isinstance(payload, str):  # double-stringified
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    if not isinstance(payload, dict):
        return []
    bubbles = payload.get("fullBubbles") or payload.get("bubbles")
    if not isinstance(bubbles, list):
        return []
    out: list[dict] = []
    for b in bubbles:
        out.extend(_iter_bubbles(b))
    return out


def _bubbles_to_iterations(
    bubbles: list[dict], iter_no_start: int = 1
) -> list[RawIteration]:
    """Collapse a composer session's bubbles into synthesized iterations.

    Each user (``Chat``) bubble starts a new iteration; the bubbles that
    follow (assistant responses, tool calls) belong to it. ``timingInfo``
    provides wall-clock where present; token fields are surfaced as a sparse,
    per-file-context proxy and clearly flagged.
    """

    iterations: list[RawIteration] = []
    current: list[dict] = []
    started = False
    for b in bubbles:
        btype = (b.get("type") or b.get("bubbleType") or "").lower()
        is_user = btype in ("chat", "user") and b.get("text")
        if is_user and started:
            iterations.append(current)
            current = []
        current.append(b)
        started = True
    if current:
        iterations.append(current)

    raw_iters: list[RawIteration] = []
    for idx, group in enumerate(iterations, start=iter_no_start):
        first_ts: datetime | None = None
        last_ts: datetime | None = None
        proxy_tokens = 0
        sparse = True
        for b in group:
            ti = b.get("timingInfo") or {}
            if isinstance(ti, dict):
                started_ts = ti.get("startTime") or ti.get("startedAt")
                ended_ts = ti.get("endTime") or ti.get("endedAt") or ti.get("timestamp")
                s = _parse_ts(started_ts)
                e = _parse_ts(ended_ts)
                if s and first_ts is None:
                    first_ts = s
                if e:
                    last_ts = e
            # Per-file-context proxy (NOT model tokens) — only where present.
            count = b.get("tokenCountUpUntilHere")
            if isinstance(count, (int, float)) and count > 0:
                proxy_tokens = int(count)
                sparse = False
        wall_s: float | None = None
        if first_ts and last_ts:
            wall_s = (last_ts - first_ts).total_seconds()
        raw_iters.append(
            RawIteration(
                iter=idx,
                # We have no real model input/output tokens for Cursor.
                input_tokens=0,
                output_tokens=0,
                wall_s=wall_s,
                test_result=None,
                sparse=sparse,
                schema_unverified=SCHEMA_UNVERIFIED,
                note=(
                    "cursor: per-file-context token proxy (NOT model tokens); "
                    "no test oracle available"
                ),
            )
        )
    return raw_iters


def parse(path: str | Path) -> list[RawIteration]:
    """Parse a Cursor ``state.vscdb`` file into best-effort iterations.

    Reads the ``cursorDiskKV`` / ``ItemTable`` table for ``composerData:``
    sessions and synthesizes iterations from the bubble sequence. Every
    returned iteration is flagged ``schema_unverified=True``.
    """

    p = Path(path)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        # Cursor stores KV in one of two known tables.
        table = None
        key_col = "key"
        val_col = "value"
        try:
            cur = conn.execute("SELECT key, value FROM cursorDiskKV LIMIT 1")
            cur.fetchone()
            table = "cursorDiskKV"
        except sqlite3.OperationalError:
            try:
                cur = conn.execute("SELECT key, value FROM ItemTable LIMIT 1")
                cur.fetchone()
                table = "ItemTable"
            except sqlite3.OperationalError as exc:
                raise RuntimeError(
                    "state.vscdb has neither cursorDiskKV nor ItemTable — "
                    "not a recognized Cursor workspace DB"
                ) from exc

        rows = conn.execute(
            f"SELECT {key_col}, {val_col} FROM {table} "
            f"WHERE {key_col} LIKE 'composerData:%'"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    all_iters: list[RawIteration] = []
    next_no = 1
    for row in rows:
        bubbles = _bubbles_from_session(row[val_col])
        if not bubbles:
            continue
        iters = _bubbles_to_iterations(bubbles, iter_no_start=next_no)
        if iters:
            all_iters.extend(iters)
            next_no = iters[-1].iter + 1

    return all_iters
