"""Report — shareable Markdown export of a ledger + stop recommendation.

The ``margledger replay --markdown`` path emits a single Markdown file a team
can drop into a PR comment or an internal wiki — the team-dashboard read of
``ledger.json`` (the hosted dashboard itself is a v0.2+ consumer, explicitly
out of scope here).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .ledger import LedgerEntry
from .stop import StopRecommendation, recommend, render_summary


def to_markdown(
    ledger: list[LedgerEntry],
    rec: StopRecommendation | None = None,
    *,
    title: str = "MargLedger report",
) -> str:
    """Render a ledger + recommendation to a Markdown document."""

    if rec is None:
        rec = recommend(ledger)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = [f"# {title}", "", f"_Generated {now}_", ""]

    lines.append("## Stop recommendation")
    lines.append("")
    lines.append("```")
    lines.append(render_summary(rec, ledger))
    lines.append("```")
    lines.append("")

    lines.append("## Ledger")
    lines.append("")
    lines.append(
        "| iter | marginal value | cumulative value | marginal tokens | "
        "cumulative tokens | value / ktoken | knee |"
    )
    lines.append(
        "|---:|---:|---:|---:|---:|---:|:---:|"
    )
    for e in ledger:
        knee = "knee" if e.is_knee else ""
        wall = (
            f"{e.marginal_wall_s:.1f}s"
            if e.marginal_wall_s is not None
            else "—"
        )
        sparse = " (sparse)" if e.sparse else ""
        lines.append(
            f"| {e.iter} | {e.marginal_value:g} | {e.cumulative_value:g} | "
            f"{e.marginal_tokens:,} | {e.cumulative_tokens:,} | "
            f"{e.value_per_ktoken:g} | {knee} |"
        )
        if e.note:
            lines.append(
                f"  <sub>iter {e.iter}: wall {wall}{sparse} — {e.note}</sub>"
            )
    lines.append("")

    if rec.stop and rec.knee_iter is not None:
        lines.append("## Why stop here")
        lines.append("")
        lines.append(
            f"Marginal value dropped to `<= {rec.epsilon}` for "
            f"`{rec.consecutive_flat}` consecutive iterations starting at "
            f"iteration **{rec.knee_iter}**. The stop rule "
            f"(`marginal_value ≤ ε for K consecutive iters`, "
            f"ε={rec.epsilon}, K={rec.k}) fired. "
            f"The {rec.tokens_saved:,} tokens spent on iterations after the "
            f"knee produced no net test gain — that is the waste a hard "
            f"budget cutoff would have burned."
        )
        lines.append("")

    lines.append("## Provenance")
    lines.append("")
    unverified = any(e.schema_unverified for e in ledger)
    sparse_any = any(e.sparse for e in ledger)
    if unverified:
        lines.append(
            "- At least one source is `schema_unverified` — token fields are "
            "a best-effort proxy, not model-attested. See the per-iteration "
            "notes."
        )
    if sparse_any:
        lines.append(
            "- At least one iteration is flagged `sparse` — wall-clock and "
            "token coverage are partial for that source."
        )
    if not (unverified or sparse_any):
        lines.append(
            "- All iterations carry model-attested token deltas (Claude Code "
            "JSONL) and a grounded test-suite oracle."
        )
    lines.append("")

    return "\n".join(lines)
