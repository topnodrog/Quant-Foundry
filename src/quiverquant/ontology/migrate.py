"""Stream the DuckDB `raw_signals` table into the Open Foundry crypto ontology.

Reads every stored row, maps it to governed-action calls (`mapping.map_row`),
dedupes entity registrations within the run, and posts them via
`OpenFoundryClient`. `--dry-run` renders the plan (counts per action + samples)
without touching the network — the way to validate the mapping before the stack
is up.

    uv run quiverquant migrate-ontology --dry-run
    uv run quiverquant migrate-ontology --limit 500
    uv run quiverquant migrate-ontology --source dune
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any, Iterator

from quiverquant.ontology.client import OpenFoundryClient
from quiverquant.ontology.mapping import (
    EDGE_ENDPOINT_PARAMS,
    ActionCall,
    EdgeSpec,
    aggregate_edges,
    derive_edges,
    map_row,
)
from quiverquant.storage import get_connection


def _iter_rows(source: str | None, limit: int | None) -> Iterator[dict[str, Any]]:
    sql = "SELECT source, signal_type, entity, ts, payload, tier FROM raw_signals"
    params: list[Any] = []
    if source:
        sql += " WHERE source = ?"
        params.append(source)
    sql += " ORDER BY ts"
    if limit:
        sql += f" LIMIT {int(limit)}"
    con = get_connection()
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        for values in cur.fetchall():
            row = dict(zip(cols, values))
            payload = row.get("payload")
            row["payload"] = json.loads(payload) if isinstance(payload, str) else (payload or {})
            yield row
    finally:
        con.close()


def _plan(source: str | None, limit: int | None):
    """Yield (row, [ActionCall]) with within-run entity dedupe applied."""
    seen: set[str] = set()
    for row in _iter_rows(source, limit):
        emitted: list[ActionCall] = []
        for call in map_row(row):
            if call.dedupe_key is not None:
                if call.dedupe_key in seen:
                    continue
                seen.add(call.dedupe_key)
            emitted.append(call)
        yield row, emitted


def run(source: str | None = None, limit: int | None = None,
        dry_run: bool = False, sample: int = 3) -> int:
    client = OpenFoundryClient(dry_run=dry_run)
    action_counts: Counter[str] = Counter()
    fail_by_action: Counter[str] = Counter()
    error_samples: dict[str, str] = {}
    skipped_types: Counter[str] = Counter()
    node_ids: dict[str, str] = {}          # dedupe_key -> created object id
    edge_specs: list[EdgeSpec] = []
    rows_seen = 0
    calls_made = 0
    samples: dict[str, dict[str, Any]] = {}
    failures = 0

    def _do(action: str, params: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal calls_made, failures
        action_counts[action] += 1
        if action not in samples and len(samples) < 100:
            samples[action] = params
        try:
            result = client.call_action(action, params)
            calls_made += 1
            return result
        except Exception as exc:  # noqa: BLE001 - report, keep going
            failures += 1
            fail_by_action[action] += 1
            error_samples.setdefault(action, str(exc))
            return None

    # ── Pass 1: nodes + observations (capture created object ids) ──
    for row, calls in _plan(source, limit):
        rows_seen += 1
        edge_specs.extend(derive_edges(row))
        if not calls:
            skipped_types[row["signal_type"]] += 1
            continue
        for call in calls:
            result = _do(call.action, call.params)
            if call.dedupe_key and result and not dry_run:
                affected = (result.get("data") or {}).get("affectedObjects") or []
                if affected:
                    node_ids[call.dedupe_key] = affected[0]["id"]

    # ── Pass 2: graph edges (resolve endpoints by captured id, then createLink) ──
    edges = aggregate_edges(edge_specs)
    edge_unresolved = 0
    for e in edges:
        if dry_run:
            action_counts[e.action] += 1  # plan only — ids resolve at run time
            continue
        from_id, to_id = node_ids.get(e.from_key), node_ids.get(e.to_key)
        if not from_id or not to_id:
            edge_unresolved += 1
            continue
        p_from, p_to = EDGE_ENDPOINT_PARAMS[e.action]
        _do(e.action, {p_from: from_id, p_to: to_id, **e.props})

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n=== migrate-ontology [{mode}] ===")
    print(f"rows read:        {rows_seen}")
    print(f"action calls ok:  {calls_made}")
    print(f"aggregated edges: {len(edges)}" + (f" ({edge_unresolved} unresolved)" if edge_unresolved else ""))
    if failures:
        print(f"failures:         {failures}")
    print("\nby action (attempted / failed):")
    for action, n in sorted(action_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        f = fail_by_action.get(action, 0)
        print(f"  {action:24} {n:4}  fail={f}")
    if fail_by_action:
        print("\nfailure samples (one per action):")
        for action in sorted(fail_by_action):
            print(f"  {action}: {error_samples[action][:220]}")
    if skipped_types:
        print("\nskipped signal types (no ontology mapping):")
        for st, n in skipped_types.most_common():
            print(f"  {st:26} {n}")
    if dry_run and samples:
        print("\nsample params (one per action):")
        for action in sorted(samples):
            rendered = json.dumps(samples[action], default=str)
            if len(rendered) > 200:
                rendered = rendered[:200] + "…"
            print(f"  {action}: {rendered}")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="migrate-ontology",
                                 description="Migrate raw_signals into the Open Foundry crypto ontology")
    ap.add_argument("--dry-run", action="store_true",
                    help="render the plan without posting to Open Foundry")
    ap.add_argument("--source", help="only migrate rows from this collector source")
    ap.add_argument("--limit", type=int, help="cap rows processed")
    args = ap.parse_args(argv)
    return run(source=args.source, limit=args.limit, dry_run=args.dry_run)
