"""Oracle — the machine-checkable value signal.

For coding agent loops the only honest value oracle that exists is the test
suite: a test either passes or it does not. MargLedger does *not* fake-score
value without one (creative / research agents are an explicit non-user). The
marginal value of an iteration is the test-suite delta it produced:

    marginal_value(iter) = passed(after) - passed(before)

This is grounded — the ground truth exists and is re-runnable. Flaky tests are
a surfaced limitation, never hidden.

Two ingestion paths:
    - ``parse_junit``        — a JUnit XML file (the ``--tests`` oracle).
    - ``parse_pytest_text``  — best-effort parse of inline ``pytest`` summary
      lines embedded in transcript tool results, so per-iteration deltas can
      be recovered even when only a final JUnit snapshot is available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from junitparser import JUnitXml
except Exception:  # pragma: no cover - junitparser is a hard dep but stay safe
    JUnitXml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class TestResult:
    """A point-in-time snapshot of a test suite run.

    ``passed`` is derived: total - failures - errors - skipped.
    """

    __test__ = False  # not a pytest test class

    total: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0

    @property
    def passed(self) -> int:
        return max(0, self.total - self.failures - self.errors - self.skipped)

    @classmethod
    def empty(cls) -> "TestResult":
        return cls()


@dataclass
class TestDelta:
    """The signed marginal value between two test snapshots."""

    __test__ = False  # not a pytest test class

    passing_delta: int
    failing_delta: int
    value: float

    @classmethod
    def between(cls, before: TestResult, after: TestResult) -> "TestDelta":
        passing = after.passed - before.passed
        failing = after.failures + after.errors - before.failures - before.errors
        return cls(
            passing_delta=passing,
            failing_delta=failing,
            value=float(passing),
        )


_PYTEST_PASSED = re.compile(r"(\d+)\s+passed", re.IGNORECASE)
_PYTEST_FAILED = re.compile(r"(\d+)\s+failed", re.IGNORECASE)
_PYTEST_ERRORS = re.compile(r"(\d+)\s+errors?\b", re.IGNORECASE)
_PYTEST_SKIPPED = re.compile(r"(\d+)\s+skipped", re.IGNORECASE)


def parse_pytest_text(text: str) -> TestResult | None:
    """Best-effort parse of an inline ``pytest`` summary line.

    Order-independent: real pytest emits both ``"2 failed, 40 passed"`` and
    ``"40 passed, 2 failed"`` depending on version/flags, so each metric is
    scanned on its own. Returns ``None`` when no ``N passed`` token is found.
    Designed for the tool-result text embedded in agent transcripts — it
    tolerates the ANSI/escape noise that surrounds a real pytest run.
    """

    if not text:
        return None
    # Strip ANSI escape sequences so color codes don't split the summary line.
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", text)
    m = _PYTEST_PASSED.search(cleaned)
    if not m:
        return None
    passed = int(m.group(1))
    failed = _search_int(_PYTEST_FAILED, cleaned)
    errors = _search_int(_PYTEST_ERRORS, cleaned)
    skipped = _search_int(_PYTEST_SKIPPED, cleaned)
    total = passed + failed + errors + skipped
    return TestResult(
        total=total, failures=failed, errors=errors, skipped=skipped
    )


def _search_int(pattern: re.Pattern, text: str) -> int:
    m = pattern.search(text)
    return int(m.group(1)) if m else 0


def parse_junit(path: str | Path) -> TestResult:
    """Parse a JUnit XML file into a :class:`TestResult` snapshot.

    Sums across all ``<testsuite>`` elements so multi-suite reports (the
    common pytest --junitxml output) collapse to one honest total.
    """

    if JUnitXml is None:  # pragma: no cover
        raise RuntimeError("junitparser is required for the JUnit oracle")
    xml = JUnitXml.fromfile(str(path))
    total = failures = errors = skipped = 0
    suites: Any
    if hasattr(xml, "testsuites") and xml.testsuites is not None:
        suites = list(xml.testsuites)
    else:
        suites = [xml]
    # JUnitXml may itself iterate suites directly.
    if not suites and hasattr(xml, "test_suites") and xml.test_suites:
        suites = list(xml.test_suites)
    if not suites:
        suites = [xml]
    for suite in suites:
        attrs = {
            "tests": _to_int(getattr(suite, "tests", None)),
            "failures": _to_int(getattr(suite, "failures", None)),
            "errors": _to_int(getattr(suite, "errors", None)),
            "skipped": _to_int(getattr(suite, "skipped", None)),
        }
        # ElementTree element objects also expose .attrib
        if not any(attrs.values()) and hasattr(suite, "attrib"):
            attrs = {
                "tests": _to_int(suite.attrib.get("tests")),
                "failures": _to_int(suite.attrib.get("failures")),
                "errors": _to_int(suite.attrib.get("errors")),
                "skipped": _to_int(suite.attrib.get("skipped")),
            }
        total += attrs["tests"]
        failures += attrs["failures"]
        errors += attrs["errors"]
        skipped += attrs["skipped"]
    return TestResult(total=total, failures=failures, errors=errors, skipped=skipped)


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0
