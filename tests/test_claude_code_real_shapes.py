"""Claude Code adapter fidelity on REAL transcript shapes (v0.3.0 grill).

The synthetic fixture embeds timestamps inside ``message``; real Claude Code
events carry them at the top level. Real usage carries cache-token fields
(sometimes null), sessions open with bookkeeping events (queue-operation,
attachment, custom-title), and ``isMeta`` user events are injected caveats.
These tests pin the adapter to the real shapes.
"""

from __future__ import annotations

import json
from pathlib import Path

from margledger.sources import claude_code

FIX = Path(__file__).parent / "fixtures"


def _write(tmp_path: Path, events: list[dict]) -> Path:
    p = tmp_path / "real.jsonl"
    p.write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    return p


def _assistant(inp: int, out: int, ts: str) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": inp, "output_tokens": out},
        },
    }


def _user(content, ts: str, **extra) -> dict:
    event = {
        "type": "user",
        "timestamp": ts,
        "message": {"role": "user", "content": content},
    }
    event.update(extra)
    return event


def test_event_level_timestamps_fill_wall_clock(tmp_path):
    """Real events carry the timestamp at the top level, not in message."""
    p = _write(
        tmp_path,
        [
            _user("go", "2024-05-01T00:00:00Z"),
            _assistant(10, 5, "2024-05-01T00:00:30Z"),
        ],
    )
    raw = claude_code.parse(p)
    assert len(raw) == 1
    assert raw[0].wall_s == 30.0


def test_message_level_timestamps_still_work(tmp_path):
    """The documented example format (fixture) nests timestamps in message."""
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    assert raw[0].wall_s is not None and raw[0].wall_s > 0


def test_mixed_timezone_styles_do_not_crash(tmp_path):
    """...Z and ...+08:00 in one file previously raised TypeError."""
    p = _write(
        tmp_path,
        [
            _user("go", "2024-05-01T00:00:00Z"),
            _assistant(10, 5, "2024-05-01T08:00:05+08:00"),  # == 00:00:05Z
        ],
    )
    raw = claude_code.parse(p)
    assert len(raw) == 1
    assert raw[0].wall_s == 5.0


def test_cache_tokens_count_toward_marginal_cost(tmp_path):
    p = _write(
        tmp_path,
        [
            _user("go", "2024-05-01T00:00:00Z"),
            {
                "type": "assistant",
                "timestamp": "2024-05-01T00:00:10Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_creation_input_tokens": 20,
                        "cache_read_input_tokens": 30,
                    },
                },
            },
        ],
    )
    raw = claude_code.parse(p)
    assert raw[0].marginal_tokens == 200


def test_null_cache_fields_are_tolerated(tmp_path):
    p = _write(
        tmp_path,
        [
            _user("go", "2024-05-01T00:00:00Z"),
            {
                "type": "assistant",
                "timestamp": "2024-05-01T00:00:10Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_creation_input_tokens": None,
                        "cache_read_input_tokens": None,
                    },
                },
            },
        ],
    )
    raw = claude_code.parse(p)
    assert raw[0].marginal_tokens == 150


def test_fixture_hero_token_math_unchanged():
    """The fixture carries no cache fields — its token math must not move."""
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    assert raw[0].marginal_tokens == 12000
    assert raw[3].marginal_tokens == 15000
    assert raw[9].marginal_tokens == 10000


def test_session_preamble_does_not_become_iteration_one(tmp_path):
    """queue-operation/custom-title before the first prompt are skipped."""
    p = _write(
        tmp_path,
        [
            {"type": "queue-operation", "timestamp": "2024-05-01T00:00:00Z"},
            {"type": "custom-title", "timestamp": "2024-05-01T00:00:01Z"},
            _user("go", "2024-05-01T00:00:10Z"),
            _assistant(100, 50, "2024-05-01T00:00:15Z"),
        ],
    )
    raw = claude_code.parse(p)
    assert len(raw) == 1
    assert raw[0].iter == 1
    assert raw[0].marginal_tokens == 150
    # Preamble timestamps are excluded from the iteration's wall clock.
    assert raw[0].wall_s == 5.0


def test_is_meta_user_events_do_not_split_iterations(tmp_path):
    p = _write(
        tmp_path,
        [
            _user("go", "2024-05-01T00:00:00Z"),
            _user(
                [{"type": "text", "text": "Base directory for this skill: ..."}],
                "2024-05-01T00:00:02Z",
                isMeta=True,
            ),
            _assistant(100, 50, "2024-05-01T00:00:05Z"),
            _user("again", "2024-05-01T00:01:00Z"),
            _assistant(80, 40, "2024-05-01T00:01:05Z"),
        ],
    )
    raw = claude_code.parse(p)
    assert len(raw) == 2
    assert raw[0].marginal_tokens == 150
    assert raw[1].marginal_tokens == 120


def test_existing_fixture_iteration_count_unchanged():
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    assert len(raw) == 10
