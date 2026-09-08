# Changelog

All notable changes to MargLedger are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-09-09

### Fixed
- `margledger stop` / `margledger plot` crashed on every fresh install with
  `AttributeError: module 'plotext' has no attribute 'clf'`: the unbounded
  `plotext>=5.3` dependency now resolves to plotext 6.x, which removed the
  whole 5.x terminal API. The dependency is pinned to `plotext>=5.3,<6`
  (the line the chart renderer targets).
- Generic-JSONL transcripts now actually work with the default
  `--source auto`, as documented: a flat (non-enveloped) JSONL file was
  silently routed to the Claude Code adapter and produced a degenerate
  one-iteration, zero-token ledger. Auto-detection now peeks the first JSON
  line and routes flat transcripts to the generic adapter.
- The generic JSONL adapter no longer crashes on a malformed/truncated line
  (e.g. a partially-written final line of a live transcript); bad lines are
  skipped, matching the Claude Code adapter's behavior.
- The generic JSONL adapter no longer writes its normalized scratch file
  into the transcript's own directory (which failed on read-only transcript
  dirs and raced concurrent parses); it now uses the system tempdir.
- `margledger replay` Markdown reports render the ledger table correctly for
  ledgers with per-entry notes (Cursor sources, final-oracle reconciliation):
  note lines used to terminate the GFM table mid-body, orphaning every
  following data row as plain text. Notes now render as a list below the
  table.

### Added
- `web/site.json` now carries `meta.content_version` so the Pages site
  reflects the shipped release version.

[0.2.0]: https://github.com/SuperMarioYL/margledger/releases/tag/v0.2.0
[0.1.0]: https://github.com/SuperMarioYL/margledger/releases/tag/v0.1.0

## [0.1.0] - 2026-08-01

### Added
- `margledger trace` — parse a Claude Code JSONL transcript, synthesize
  agent-loop iterations from the assistant↔user turn sequence, attribute
  per-iteration marginal value (test-suite delta) against marginal token/time
  cost, and write `ledger.json`.
- `margledger stop` — read `ledger.json`, compute the value/cost curve, detect
  the diminishing-returns knee (`marginal_value ≤ ε` for `K` consecutive
  iterations), and print a terminal stop recommendation with tokens-saved
  versus a hard budget cutoff.
- `margledger replay` — export `ledger.json` to a shareable Markdown report.
- `margledger plot` and `margledger recommend` — render the value/cost curve
  and emit the stop recommendation independently.
- Oracle: JUnit XML parser (`junitparser`) + best-effort pytest-text parser for
  inline test runs embedded in transcript tool results.
- Sources: Claude Code JSONL adapter (native) + generic JSONL adapter + a
  best-effort, `schema_unverified` Cursor `state.vscdb` adapter that emits
  `marginal_wall_s` only where `timingInfo` is present and flags sparse
  per-file-context token fields.
- Bilingual README (zh-CN primary + full English sibling), animated dark/light
  hero and architecture SVGs, vhs demo tape, and CI/release/demo workflows.
