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
