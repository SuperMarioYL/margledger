"""End-to-end tests for ingestion, ledger build, and the stop recommendation.

Covers m1 (parse + oracle + ledger.json) and m2 (value/cost curve + knee +
stop recommendation with tokens-saved) against the real synthetic fixture
that produces the hero STOP-at-iter-4 moment.
"""

from __future__ import annotations

import json
from pathlib import Path

from margledger.ledger import build_ledger, from_json, to_json
from margledger.oracle import parse_junit
from margledger.sources import claude_code
from margledger.stop import recommend, render_curve, render_summary

FIX = Path(__file__).parent / "fixtures"


def test_ingestion_synthesizes_ten_iterations():
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    assert len(raw) == 10
    # Token deltas are real, model-attested fields summed per iteration.
    assert raw[0].marginal_tokens == 12000
    assert raw[3].marginal_tokens == 15000
    assert raw[9].marginal_tokens == 10000
    # Each iteration recovered an end-of-iteration test snapshot.
    assert raw[0].test_result is not None
    assert raw[0].test_result.passed == 40
    assert raw[2].test_result.passed == 55
    # Wall-clock is real (timestamp deltas).
    assert raw[0].wall_s is not None and raw[0].wall_s > 0


def test_build_ledger_attributes_marginal_value():
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    ledger = build_ledger(raw)
    marginal = [e.marginal_value for e in ledger]
    assert marginal == [40.0, 12.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    cumulative = [e.cumulative_value for e in ledger]
    assert cumulative == [40.0, 52.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0]
    # value_per_ktoken is marginal_value / (marginal_tokens/1000).
    assert ledger[0].value_per_ktoken == round(40.0 / 12.0, 6)
    assert ledger[3].value_per_ktoken == 0.0


def test_final_oracle_reconciles_without_gap():
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    final = parse_junit(FIX / "sample_junit.xml")
    ledger = build_ledger(raw, final_oracle=final)
    # Final cumulative == oracle (55); no reconciliation note expected.
    assert ledger[-1].cumulative_value == 55.0
    assert ledger[-1].note is None


def test_ledger_json_round_trip(tmp_path):
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    ledger = build_ledger(raw)
    out = tmp_path / "ledger.json"
    to_json(ledger, out)
    loaded = from_json(out)
    assert len(loaded) == len(ledger)
    assert loaded[3].marginal_value == 0.0
    assert loaded[0].cumulative_tokens == 12000
    assert loaded[9].cumulative_tokens == 104000  # sum of all marginal tokens


def test_stop_recommendation_hero_moment():
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    ledger = build_ledger(raw)
    rec = recommend(ledger, hard_budget_iters=10)
    assert rec.stop is True
    assert rec.knee_iter == 4
    assert rec.consecutive_flat >= 2
    # Hero math: iters 5..10 burned for zero value = 50,000 tokens saved.
    assert rec.tokens_saved == 50000


def test_stop_recommendation_summary_text():
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    ledger = build_ledger(raw)
    rec = recommend(ledger, hard_budget_iters=10)
    summary = render_summary(rec, ledger)
    assert "STOP at iter 4" in summary
    assert "50,000 tokens saved" in summary
    assert "10-iter hard budget" in summary


def test_stop_recommendation_no_knee_when_value_keeps_accruing():
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    ledger = build_ledger(raw)
    # Mutate so every iteration keeps adding value — no flat run.
    from dataclasses import replace

    ledger = [replace(e, marginal_value=5.0) for e in ledger]
    rec = recommend(ledger)
    assert rec.stop is False
    assert rec.tokens_saved == 0


def test_render_curve_emits_a_chart():
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    ledger = build_ledger(raw)
    rec = recommend(ledger)
    chart = render_curve(ledger, rec)
    assert isinstance(chart, str)
    assert len(chart) > 0
    # The knee iteration marker should appear in the rendered plot.
    assert "4" in chart


def test_trace_then_stop_via_real_ledger_json(tmp_path):
    """The m1+m2 happy path: trace -> ledger.json -> stop reads it back."""
    raw = claude_code.parse(FIX / "sample_transcript.jsonl")
    final = parse_junit(FIX / "sample_junit.xml")
    ledger = build_ledger(raw, final_oracle=final)
    out = tmp_path / "ledger.json"
    to_json(ledger, out)
    loaded = from_json(out)
    rec = recommend(loaded, hard_budget_iters=10)
    assert rec.knee_iter == 4
    assert rec.tokens_saved == 50000
    # The persisted JSON is valid and self-describing.
    payload = json.loads(out.read_text())
    assert payload["schema"] == "margledger/ledger/v1"
    assert len(payload["entries"]) == 10
