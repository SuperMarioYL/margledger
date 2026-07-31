# Changelog

All notable changes to MargLedger are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/SuperMarioYL/margledger/releases/tag/v0.1.0
