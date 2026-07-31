# MargLedger — examples

The 3-command happy path. Run from a repo root where `margledger` is installed.

```bash
# 1. trace a Claude Code JSONL transcript + JUnit oracle -> ledger.json
margledger trace ~/.claude/projects/my-proj --tests junit.xml -o ledger.json

# 2. read the value/cost curve + stop recommendation
margledger stop ledger.json --hard-budget 10

# 3. export a shareable Markdown report for the team
margledger replay ledger.json --markdown -o report.md
```

A synthetic fixture lives under `tests/fixtures/` so you can try it without a
real transcript:

```bash
margledger trace tests/fixtures/sample_transcript.jsonl \
  --tests tests/fixtures/sample_junit.xml -o /tmp/ledger.json
margledger stop /tmp/ledger.json --hard-budget 10
```

The hero moment: the ledger auto-flags **iter 4** as the diminishing-returns
knee (marginal value `0` for the remaining iterations) and recommends
**STOP at iter 4 — ~50,000 tokens saved vs a 10-iter hard budget**.
