"""MargLedger — per-iteration marginal-value ledger for AI coding-agent loops.

For each agent-loop iteration, MargLedger attributes marginal value (test-suite
delta, the machine-checkable oracle) against marginal token/time cost, surfaces
a value/cost curve, and recommends when to stop the loop (diminishing returns
versus a hard budget cutoff).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("margledger")
except PackageNotFoundError:  # pragma: no cover - not installed in dev tree
    __version__ = "0.2.0"

__all__ = ["__version__"]
