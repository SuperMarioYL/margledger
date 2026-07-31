"""Tests for the oracle — the machine-checkable value signal (m1)."""

from __future__ import annotations

from pathlib import Path

from margledger.oracle import (
    TestDelta,
    TestResult,
    parse_junit,
    parse_pytest_text,
)

FIX = Path(__file__).parent / "fixtures"


def test_parse_junit_fixture_snapshot():
    res = parse_junit(FIX / "sample_junit.xml")
    assert res.total == 55
    assert res.failures == 0
    assert res.errors == 0
    assert res.skipped == 0
    assert res.passed == 55


def test_testresult_passed_is_derived():
    res = TestResult(total=10, failures=2, errors=1, skipped=1)
    assert res.passed == 6


def test_parse_pytest_text_simple_passing():
    res = parse_pytest_text("========================= 40 passed in 3.20s =========================")
    assert res is not None
    assert res.passed == 40
    assert res.failures == 0


def test_parse_pytest_text_with_failures_and_skipped():
    res = parse_pytest_text("2 failed, 40 passed, 3 skipped in 4.0s")
    assert res is not None
    assert res.passed == 40
    assert res.failures == 2
    assert res.skipped == 3


def test_parse_pytest_text_tolerates_ansi_noise():
    raw = "\x1b[32m\u001b[0m 12 passed \x1b[31m1 failed\x1b[0m in 2.0s"
    res = parse_pytest_text(raw)
    assert res is not None
    assert res.passed == 12
    assert res.failures == 1


def test_parse_pytest_text_returns_none_when_no_summary():
    assert parse_pytest_text("just some build output, no test summary here") is None
    assert parse_pytest_text("") is None


def test_delta_between_counts_new_passing():
    before = TestResult(total=40)
    after = TestResult(total=52)
    delta = TestDelta.between(before, after)
    assert delta.passing_delta == 12
    assert delta.value == 12.0


def test_delta_between_is_signed_when_tests_break():
    before = TestResult(total=55)
    after = TestResult(total=55, failures=3)  # 3 newly broken
    delta = TestDelta.between(before, after)
    assert delta.passing_delta == -3
    assert delta.value == -3.0
