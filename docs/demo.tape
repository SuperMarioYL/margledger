Output assets/demo.gif
Set FontSize 13
Set Width 1180
Set Height 560
Set Padding 20
Set Theme "Dracula"

# MargLedger — the agent-loop ledger that stops at diminishing returns.
# 10-minute happy path: trace a transcript -> ledger.json -> stop recommendation.

Type "echo 'MargLedger — per-iteration marginal-value ledger'"
Enter
Sleep 800ms

Type "margledger trace tests/fixtures/sample_transcript.jsonl --tests tests/fixtures/sample_junit.xml -o /tmp/ledger.json"
Enter
Sleep 3s

Type "margledger stop /tmp/ledger.json --hard-budget 10"
Enter
Sleep 4s

Type "margledger recommend /tmp/ledger.json --hard-budget 10 --json"
Enter
Sleep 2s

Type "echo 'STOP at iter 4 — ~50,000 tokens saved vs a 10-iter hard budget.'"
Enter
Sleep 1s
