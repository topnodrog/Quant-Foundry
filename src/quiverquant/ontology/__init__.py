"""Phase 2 — bridge from the Phase 1 `raw_signals` store into the Open Foundry
crypto ontology (PLAN.md §4).

`mapping` turns a raw_signals row into a list of governed-action calls (pure,
testable offline); `client` posts those actions to Open Foundry's REST API;
`migrate` streams the DuckDB table through both, with a `--dry-run` that renders
the plan without touching the network.
"""

from quiverquant.ontology.mapping import ActionCall, map_row

__all__ = ["ActionCall", "map_row"]
