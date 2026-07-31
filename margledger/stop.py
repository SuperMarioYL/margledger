"""Stop-recommender — a pure function over the ledger.

Stop rule (mvp_plan §2): ``marginal_value ≤ ε`` for ``K`` consecutive
iterations (default ``ε = 0``, ``K = 2``). The recommendation is post-hoc
(v0.1 analyzes a finished transcript) and **recommends**; the operator
decides whether to halt. The hero moment:

    STOP at iter 4 — marginal value 0 for 2 iters; ~50k tokens saved
    vs a 10-iter hard budget.

The value/cost curve is rendered with ``plotext`` directly to the terminal
(house-style: no external chart deps).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import plotext as plt

from .ledger import LedgerEntry


@dataclass
class StopRecommendation:
    stop: bool
    knee_iter: int | None
    stop_iter: int | None
    reason: str
    tokens_saved: int
    hard_budget_iters: int | None
    consecutive_flat: int
    epsilon: float
    k: int

    def as_dict(self) -> dict:
        return asdict(self)


def recommend(
    ledger: list[LedgerEntry],
    *,
    epsilon: float = 0.0,
    k: int = 2,
    hard_budget_iters: int | None = None,
) -> StopRecommendation:
    """Compute the stop recommendation for a finished ledger.

    ``hard_budget_iters`` only frames the tokens-saved narrative; the
    tokens-saved number itself is the *observed* waste — the sum of marginal
    tokens spent on iterations strictly after the knee. When the transcript
    ran to the budget, observed waste == budget waste.
    """

    n = len(ledger)
    if n == 0:
        return StopRecommendation(
            stop=False,
            knee_iter=None,
            stop_iter=None,
            reason="empty ledger — nothing to stop",
            tokens_saved=0,
            hard_budget_iters=hard_budget_iters,
            consecutive_flat=0,
            epsilon=epsilon,
            k=k,
        )

    knee_index = _find_knee(ledger, epsilon=epsilon, k=k)
    if knee_index is None:
        # No diminishing run found — value is still accruing.
        max_flat = _max_consecutive_flat(ledger, epsilon=epsilon)
        return StopRecommendation(
            stop=False,
            knee_iter=None,
            stop_iter=None,
            reason=(
                f"no {k}-consecutive marginal_value <= {epsilon} run found; "
                f"value still accruing (max flat run = {max_flat})"
            ),
            tokens_saved=0,
            hard_budget_iters=hard_budget_iters,
            consecutive_flat=max_flat,
            epsilon=epsilon,
            k=k,
        )

    knee_entry = ledger[knee_index]
    # Tokens wasted = observed spend on iterations strictly after the knee.
    tokens_saved = sum(e.marginal_tokens for e in ledger[knee_index + 1:])
    flat_run = _consecutive_flat_from(ledger, knee_index, epsilon=epsilon)

    return StopRecommendation(
        stop=True,
        knee_iter=knee_entry.iter,
        stop_iter=knee_entry.iter,
        reason=(
            f"marginal_value <= {epsilon} for {flat_run} consecutive iters "
            f"from iter {knee_entry.iter}"
        ),
        tokens_saved=tokens_saved,
        hard_budget_iters=hard_budget_iters,
        consecutive_flat=flat_run,
        epsilon=epsilon,
        k=k,
    )


def _find_knee(
    ledger: list[LedgerEntry], *, epsilon: float, k: int
) -> int | None:
    """Index of the first iteration that begins a K-long flat run."""

    n = len(ledger)
    if k <= 0 or n < k:
        return None
    for i in range(n - k + 1):
        if all(ledger[j].marginal_value <= epsilon for j in range(i, i + k)):
            return i
    return None


def _consecutive_flat_from(
    ledger: list[LedgerEntry], start: int, *, epsilon: float
) -> int:
    count = 0
    for entry in ledger[start:]:
        if entry.marginal_value <= epsilon:
            count += 1
        else:
            break
    return count


def _max_consecutive_flat(
    ledger: list[LedgerEntry], *, epsilon: float
) -> int:
    best = run = 0
    for entry in ledger:
        if entry.marginal_value <= epsilon:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def render_curve(
    ledger: list[LedgerEntry],
    rec: StopRecommendation | None = None,
    *,
    width: int = 78,
    height: int = 18,
) -> str:
    """Render the value/cost curve as an inline plotext string.

    Two series share the iteration axis:
        - cumulative value (line) — the value accrued so far.
        - marginal value (bars) — the per-iteration delta, so the flat tail
          after the knee is visually obvious.
    A vertical marker flags the knee iteration when a recommendation exists.
    """

    if not ledger:
        return "(empty ledger — nothing to plot)"

    if rec is None:
        rec = recommend(ledger)

    iters = [e.iter for e in ledger]
    cumulative = [e.cumulative_value for e in ledger]
    marginal = [e.marginal_value for e in ledger]
    tokens = [e.marginal_tokens for e in ledger]

    plt.clf()
    plt.subplots(1, 2)
    # Left: value curve.
    plt.subplot(1, 1)
    plt.title("value / cost curve")
    plt.plot(iters, cumulative, label="cumulative value")
    plt.bar(iters, marginal, label="marginal value", width=0.4)
    plt.xlabel("iteration")
    plt.ylabel("passing tests (delta)")
    if rec.knee_iter is not None:
        plt.vline(rec.knee_iter, color="red")
    # Right: cost axis (tokens per iteration).
    plt.subplot(1, 2)
    plt.title("marginal token cost")
    plt.bar(iters, tokens, label="tokens", width=0.5)
    plt.xlabel("iteration")
    plt.ylabel("tokens")
    if rec.knee_iter is not None:
        plt.vline(rec.knee_iter, color="red")

    plt.theme("clear")
    try:
        rendered = plt.build()
    except Exception:
        # plotext build() returns a string; guard for env quirities.
        rendered = plt.build()
    return rendered


def render_summary(rec: StopRecommendation, ledger: list[LedgerEntry]) -> str:
    """A compact, copy-pasteable textual summary of the recommendation."""

    lines: list[str] = []
    if rec.stop and rec.knee_iter is not None:
        budget_note = ""
        if rec.hard_budget_iters:
            budget_note = f" vs a {rec.hard_budget_iters}-iter hard budget"
        lines.append(
            f"STOP at iter {rec.knee_iter} — {rec.reason}; "
            f"~{rec.tokens_saved:,} tokens saved{budget_note}."
        )
    else:
        lines.append(f"CONTINUE — {rec.reason}")
    if ledger:
        spent = ledger[-1].cumulative_tokens
        lines.append(
            f"observed: {len(ledger)} iters, {spent:,} tokens spent, "
            f"final cumulative value {ledger[-1].cumulative_value:g} passing tests."
        )
    return "\n".join(lines)
