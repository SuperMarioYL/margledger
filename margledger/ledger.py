"""Ledger — the marginal-value ledger primitive.

The new primitive is the **marginal-value ledger entry** — one per loop
iteration. Value is grounded in the test-suite oracle (see :mod:`oracle`),
cost in real token / wall-clock deltas. The ledger is a ``list[LedgerEntry]``
serialized to JSON; the stop-recommender (:mod:`stop`) is a pure function
over it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .oracle import TestDelta, TestResult


@dataclass
class RawIteration:
    """Source-adapter output: one synthesized iteration, pre-value-attribution.

    ``test_result`` is the oracle snapshot *at the end of this iteration* (or
    ``None`` when no test run was observed in the transcript for it).
    """

    iter: int
    input_tokens: int
    output_tokens: int
    wall_s: float | None
    test_result: TestResult | None = None
    # Provenance flags for UNVERIFIED sources (e.g. Cursor per-file-context).
    sparse: bool = False
    schema_unverified: bool = False
    note: str | None = None

    @property
    def marginal_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LedgerEntry:
    """One row of the marginal-value ledger.

    Mirrors the core data model from mvp_plan §2. ``is_knee`` is set by the
    stop-recommender, not at build time (kept ``False`` here for an honest
    pre-recommendation snapshot).
    """

    iter: int
    marginal_value: float
    cumulative_value: float
    marginal_tokens: int
    marginal_wall_s: float | None
    cumulative_tokens: int
    value_per_ktoken: float
    is_knee: bool = False
    # Provenance passthrough for sparse / unverified sources.
    sparse: bool = False
    schema_unverified: bool = False
    note: str | None = None


def build_ledger(
    raw_iters: list[RawIteration],
    final_oracle: TestResult | None = None,
) -> list[LedgerEntry]:
    """Attribrute marginal value/cost across a list of raw iterations.

    Per-iteration marginal value = test-suite delta versus the previous
    iteration's cumulative passing count. When an iteration carries no
    inline test snapshot (``test_result is None``), its marginal value is 0
    and the cumulative is carried forward — this is the honest, conservative
    read (no test run observed → no value claim).

    ``final_oracle`` is an optional ``--tests`` JUnit snapshot. When provided,
    the last iteration's cumulative is reconciled to it (a real, re-runnable
    ground truth) and any reconciliation gap is reported on that entry's note.
    """

    entries: list[LedgerEntry] = []
    cumulative_value = 0.0
    cumulative_tokens = 0
    prev_passed = 0

    for raw in raw_iters:
        if raw.test_result is not None:
            before = TestResult(total=prev_passed)
            delta = TestDelta.between(before, raw.test_result)
            marginal_value = delta.value
            cumulative_value = cumulative_value + marginal_value
            prev_passed = raw.test_result.passed
        else:
            marginal_value = 0.0

        cumulative_tokens += raw.marginal_tokens
        ktoken = raw.marginal_tokens / 1000.0
        value_per_ktoken = (
            marginal_value / ktoken if ktoken > 0 else 0.0
        )
        entries.append(
            LedgerEntry(
                iter=raw.iter,
                marginal_value=round(marginal_value, 6),
                cumulative_value=round(cumulative_value, 6),
                marginal_tokens=raw.marginal_tokens,
                marginal_wall_s=raw.wall_s,
                cumulative_tokens=cumulative_tokens,
                value_per_ktoken=round(value_per_ktoken, 6),
                sparse=raw.sparse,
                schema_unverified=raw.schema_unverified,
                note=raw.note,
            )
        )

    if final_oracle is not None and entries:
        last = entries[-1]
        oracle_passed = final_oracle.passed
        gap = oracle_passed - last.cumulative_value
        if abs(gap) > 1e-9:
            note = (last.note + " | " if last.note else "") + (
                f"final oracle reconciled cumulative_value "
                f"{last.cumulative_value:.0f} -> {oracle_passed} "
                f"(delta {gap:+.0f})"
            )
            entries[-1] = _replace(last, cumulative_value=float(oracle_passed), note=note)

    return entries


def _replace(entry: LedgerEntry, **changes: Any) -> LedgerEntry:
    """Dataclass replace shim (avoids importing dataclasses.replace everywhere)."""
    from dataclasses import replace

    return replace(entry, **changes)


def to_json(ledger: list[LedgerEntry], path: str | Path | None = None) -> str:
    """Serialize a ledger to JSON. Writes to ``path`` when given, returns text."""

    payload = {
        "schema": "margledger/ledger/v1",
        "entries": [asdict(e) for e in ledger],
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def from_json(path: str | Path) -> list[LedgerEntry]:
    """Load a ledger written by :func:`to_json`."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries_raw = data.get("entries", data if isinstance(data, list) else [])
    out: list[LedgerEntry] = []
    for row in entries_raw:
        out.append(
            LedgerEntry(
                iter=int(row["iter"]),
                marginal_value=float(row["marginal_value"]),
                cumulative_value=float(row["cumulative_value"]),
                marginal_tokens=int(row["marginal_tokens"]),
                marginal_wall_s=(
                    None if row.get("marginal_wall_s") is None
                    else float(row["marginal_wall_s"])
                ),
                cumulative_tokens=int(row["cumulative_tokens"]),
                value_per_ktoken=float(row["value_per_ktoken"]),
                is_knee=bool(row.get("is_knee", False)),
                sparse=bool(row.get("sparse", False)),
                schema_unverified=bool(row.get("schema_unverified", False)),
                note=row.get("note"),
            )
        )
    return out
