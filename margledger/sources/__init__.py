"""Source adapters — turn raw agent-loop transcripts into normalized iterations.

Each adapter exposes a ``parse(path) -> list[RawIteration]`` function returning
machine-checkable per-iteration token / wall-clock / test-result data.

Adapters:
    - ``claude_code``  : native Claude Code JSONL transcript adapter.
    - ``generic_jsonl``: any JSONL transcript following the assistant↔user turn
      contract (iterations synthesized where no native marker exists).
    - ``cursor``       : best-effort, ``schema_unverified`` Cursor
      ``state.vscdb`` adapter (sparse per-file-context tokens).
"""

from __future__ import annotations
