# Changelog

All notable changes to MargLedger are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-10-09

### Fixed
- `marginal_wall_s` was `null` for every iteration on real Claude Code
  transcripts: the adapter read `timestamp` from inside `message`, but real
  events carry it at the top level (a real 646-event session has 565
  event-level timestamps and 0 message-level ones). The adapter now reads the
  event-level timestamp first and falls back to the message-level one, so the
  documented example format keeps working.
- Mixing timezone styles in one transcript (`...Z` and `...+08:00`) crashed
  `trace` with `TypeError: can't subtract offset-naive and offset-aware
  datetimes`. All timestamps now normalize to UTC (naive means UTC).
- `marginal_tokens` dropped cache tokens: `cache_creation_input_tokens` and
  `cache_read_input_tokens` are real, billed usage fields (32.4% of total
  token cost on a measured real session) and can be null. They are now
  included in the per-iteration marginal cost.
- Session preamble events (queue-operation, attachment, custom-title,
  last-prompt) no longer produce a phantom zero-token iteration 1, and
  `isMeta` user events (Claude Code's injected skill caveats) no longer split
  an in-flight iteration in two. Iteration numbering now matches what an
  operator reading the transcript would count.

### Changed
- Removed a dead exception path in the value/cost-curve renderer whose
  handler re-ran the identical `plt.build()` call; curve rendering is a
  single call again. No behavior change.

### Added
- `tests/test_version.py` pins the version single source of truth: the
  VERSION file, `pyproject.toml`, the package `__version__`, and the
  `--version` CLI output must stay in lockstep.

[0.3.0]: https://github.com/SuperMarioYL/margledger/releases/tag/v0.3.0

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
