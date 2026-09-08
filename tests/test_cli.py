"""CLI smoke tests via typer's CliRunner — the m1/m2/m3 wiring."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from margledger.cli import app

FIX = Path(__file__).parent / "fixtures"
runner = CliRunner()


def test_trace_writes_ledger_json(tmp_path):
    out = tmp_path / "ledger.json"
    result = runner.invoke(
        app,
        [
            "trace",
            str(FIX / "sample_transcript.jsonl"),
            "--tests", str(FIX / "sample_junit.xml"),
            "--output", str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["schema"] == "margledger/ledger/v1"
    assert len(payload["entries"]) == 10


def test_stop_reads_ledger_and_recommends(tmp_path):
    out = tmp_path / "ledger.json"
    runner.invoke(
        app,
        [
            "trace",
            str(FIX / "sample_transcript.jsonl"),
            "--output", str(out),
        ],
    )
    result = runner.invoke(app, ["stop", str(out), "--hard-budget", "10"])
    assert result.exit_code == 0, result.output
    assert "STOP at iter 4" in result.output
    assert "50,000 tokens saved" in result.output


def test_recommend_json_output(tmp_path):
    out = tmp_path / "ledger.json"
    runner.invoke(
        app,
        ["trace", str(FIX / "sample_transcript.jsonl"), "--output", str(out)],
    )
    result = runner.invoke(
        app, ["recommend", str(out), "--hard-budget", "10", "--json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["stop"] is True
    assert data["knee_iter"] == 4
    assert data["tokens_saved"] == 50000


def test_replay_writes_markdown(tmp_path):
    out = tmp_path / "ledger.json"
    report = tmp_path / "report.md"
    runner.invoke(
        app,
        ["trace", str(FIX / "sample_transcript.jsonl"), "--output", str(out)],
    )
    result = runner.invoke(
        app, ["replay", str(out), "--markdown", "--output", str(report)]
    )
    assert result.exit_code == 0, result.output
    text = report.read_text()
    assert "STOP at iter 4" in text
    assert "MargLedger report" in text


def test_plot_command_runs(tmp_path):
    out = tmp_path / "ledger.json"
    runner.invoke(
        app,
        ["trace", str(FIX / "sample_transcript.jsonl"), "--output", str(out)],
    )
    result = runner.invoke(app, ["plot", str(out)])
    assert result.exit_code == 0, result.output


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "margledger" in result.output


def test_trace_auto_detects_flat_jsonl(tmp_path):
    """Default `--source auto` must route flat JSONL to the generic adapter
    (README: `.jsonl` -> Claude Code / generic JSONL), not silently produce a
    degenerate one-iteration, zero-token ledger via the Claude Code adapter."""
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
    flat = tmp_path / "flat.jsonl"
    flat.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")

    out_auto = tmp_path / "auto.json"
    result = runner.invoke(app, ["trace", str(flat), "--output", str(out_auto)])
    assert result.exit_code == 0, result.output
    entries = json.loads(out_auto.read_text())["entries"]
    assert len(entries) == 2
    assert [e["marginal_tokens"] for e in entries] == [150, 120]


def test_replay_markdown_table_survives_notes(tmp_path):
    """Per-entry notes must not break the GFM ledger table: every data row
    stays inside the table block and the notes render below it."""
    # An oracle that disagrees with the inline snapshots (60 vs 55) forces a
    # final-oracle reconciliation note on the last ledger entry.
    junit = tmp_path / "mismatched_junit.xml"
    junit.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testsuites name="mismatch" tests="60" failures="0" errors="0" skipped="0">\n'
        '  <testsuite name="tests.test_app" tests="60" failures="0" errors="0" '
        'skipped="0" time="3.0"/>\n'
        "</testsuites>\n",
        encoding="utf-8",
    )
    out = tmp_path / "ledger.json"
    report = tmp_path / "report.md"
    assert runner.invoke(
        app,
        ["trace", str(FIX / "sample_transcript.jsonl"), "--tests", str(junit),
         "--output", str(out)],
    ).exit_code == 0
    assert runner.invoke(
        app, ["replay", str(out), "--output", str(report)]
    ).exit_code == 0

    lines = report.read_text().splitlines()
    assert any("final oracle reconciled" in l for l in lines)
    hdr = next(i for i, l in enumerate(lines) if l.startswith("| iter |"))
    # The GFM table block: every line from the header until the first
    # pipe-free line must be a table row — all 10 data rows stay inside.
    table_rows = []
    for line in lines[hdr:]:
        if "|" not in line:
            break
        table_rows.append(line)
    assert len(table_rows) == 12  # header + delimiter + 10 data rows
    # Notes render below the table, not between its rows.
    note_idx = next(i for i, l in enumerate(lines) if "final oracle reconciled" in l)
    assert note_idx > hdr + len(table_rows) - 1
    assert any(l == "## Notes" for l in lines)
