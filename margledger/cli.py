"""MargLedger CLI — trace / stop / replay / plot / recommend.

    margledger trace ~/.claude/projects/<proj> --tests junit.xml -o ledger.json
    margledger stop ledger.json
    margledger replay ledger.json --markdown > report.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .ledger import LedgerEntry, build_ledger, from_json, to_json
from .oracle import parse_junit
from .report import to_markdown
from .sources import claude_code, cursor, generic_jsonl
from .stop import recommend, render_curve, render_summary

app = typer.Typer(
    name="margledger",
    help="Per-iteration marginal-value ledger for AI coding-agent loops.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"margledger {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        bool, typer.Option("--version", "-V", callback=_version_callback, is_eager=True)
    ] = False,
) -> None:
    """MargLedger — stop agent loops at diminishing returns."""


def _detect_source(path: Path, source: str) -> str:
    if source != "auto":
        return source
    name = path.name.lower()
    if name.endswith(".vscdb") or name.endswith(".sqlite") or name.endswith(".db"):
        return "cursor"
    return "generic" if _jsonl_is_flat(path) else "claude_code"


def _jsonl_is_flat(path: Path) -> bool:
    """True when the first parseable JSON line carries no ``{type, message}``
    envelope.

    Flat transcripts (``{"role": ..., "usage": ...}`` per line) must be routed
    to the generic adapter; enveloped ones (Claude Code) to ``claude_code``.
    Malformed leading lines are skipped — the same "first parseable event"
    rule :func:`generic_jsonl.parse` uses to decide delegation, so detection
    and parsing always agree. An unreadable file falls back to ``False``
    (the claude_code default).
    """

    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                return not generic_jsonl._looks_enveloped(event)
    except (OSError, UnicodeDecodeError):
        return False
    return False


def _parse_source(path: Path, source: str):
    source = _detect_source(path, source)
    if source == "cursor":
        return cursor.parse(path), source
    if source == "generic":
        return generic_jsonl.parse(path), source
    return claude_code.parse(path), source


def _mark_knee(ledger: list[LedgerEntry], rec) -> list[LedgerEntry]:
    """Set is_knee on the entry the recommendation points at."""

    if rec.knee_iter is None:
        return ledger
    out: list[LedgerEntry] = []
    for e in ledger:
        if e.iter == rec.knee_iter:
            from dataclasses import replace

            e = replace(e, is_knee=True)
        out.append(e)
    return out


@app.command()
def trace(
    transcript: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="Agent-loop transcript (Claude Code JSONL, generic JSONL, "
            "or Cursor state.vscdb).",
        ),
    ],
    tests: Annotated[
        Optional[Path],
        typer.Option("--tests", "-t", help="JUnit XML oracle (final test state)."),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write ledger.json here."),
    ] = "ledger.json",
    source: Annotated[
        str,
        typer.Option("--source", help="auto|claude_code|generic|cursor"),
    ] = "auto",
    epsilon: Annotated[float, typer.Option("--epsilon")] = 0.0,
    k: Annotated[int, typer.Option("--k")] = 2,
    hard_budget: Annotated[
        Optional[int],
        typer.Option("--hard-budget", help="Hard-budget iteration count (framing)."),
    ] = None,
) -> None:
    """Parse a transcript + test oracle into a marginal-value ledger.json."""

    raw_iters, used_source = _parse_source(transcript, source)
    if not raw_iters:
        console.print(
            f"[red]no iterations synthesized from {transcript}[/red]"
        )
        raise typer.Exit(code=1)

    final_oracle = parse_junit(tests) if tests else None
    ledger = build_ledger(raw_iters, final_oracle=final_oracle)
    rec = recommend(ledger, epsilon=epsilon, k=k, hard_budget_iters=hard_budget)
    ledger = _mark_knee(ledger, rec)
    text = to_json(ledger, output)

    table = Table(title=f"ledger ({len(ledger)} iters, source={used_source})")
    for col in ("iter", "m.value", "cum.value", "m.tok", "cum.tok", "v/ktok", "knee"):
        table.add_column(col, justify="right")
    for e in ledger:
        table.add_row(
            str(e.iter),
            f"{e.marginal_value:g}",
            f"{e.cumulative_value:g}",
            f"{e.marginal_tokens:,}",
            f"{e.cumulative_tokens:,}",
            f"{e.value_per_ktoken:g}",
            "knee" if e.is_knee else "",
        )
    console.print(table)
    console.print()
    console.print("[bold]stop recommendation[/bold]")
    console.print(render_summary(rec, ledger))
    console.print(f"\nwrote [cyan]{output}[/cyan] ({len(text)} bytes)")


@app.command()
def stop(
    ledger_path: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="ledger.json")
    ],
    epsilon: Annotated[float, typer.Option("--epsilon")] = 0.0,
    k: Annotated[int, typer.Option("--k")] = 2,
    hard_budget: Annotated[Optional[int], typer.Option("--hard-budget")] = None,
    curve: Annotated[bool, typer.Option("--curve/--no-curve")] = True,
) -> None:
    """Print the value/cost curve + stop recommendation for a ledger."""

    ledger = from_json(ledger_path)
    rec = recommend(ledger, epsilon=epsilon, k=k, hard_budget_iters=hard_budget)
    if curve:
        console.print(render_curve(ledger, rec))
    console.print()
    console.print("[bold]stop recommendation[/bold]")
    console.print(render_summary(rec, ledger))


@app.command()
def plot(
    ledger_path: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="ledger.json")
    ],
) -> None:
    """Render only the value/cost curve for a ledger."""

    ledger = from_json(ledger_path)
    rec = recommend(ledger)
    console.print(render_curve(ledger, rec))


# Register under the short name "recommend".
@app.command(name="recommend")
def recommend_cmd(
    ledger_path: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="ledger.json")
    ],
    epsilon: Annotated[float, typer.Option("--epsilon")] = 0.0,
    k: Annotated[int, typer.Option("--k")] = 2,
    hard_budget: Annotated[Optional[int], typer.Option("--hard-budget")] = None,
    json_out: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Emit only the stop recommendation (text or JSON)."""

    ledger = from_json(ledger_path)
    rec = recommend(ledger, epsilon=epsilon, k=k, hard_budget_iters=hard_budget)
    if json_out:
        print(json.dumps(rec.as_dict(), indent=2, ensure_ascii=False))
    else:
        console.print(render_summary(rec, ledger))


@app.command()
def replay(
    ledger_path: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="ledger.json")
    ],
    markdown: Annotated[bool, typer.Option("--markdown")] = True,
    output: Annotated[
        Optional[Path], typer.Option("--output", "-o")
    ] = None,
) -> None:
    """Replay a ledger as a shareable Markdown report."""

    ledger = from_json(ledger_path)
    rec = recommend(ledger)
    md = to_markdown(ledger, rec)
    if output:
        output.write_text(md, encoding="utf-8")
        console.print(f"wrote [cyan]{output}[/cyan]")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    app()
