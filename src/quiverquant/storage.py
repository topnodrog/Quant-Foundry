"""DuckDB-backed raw signal storage for Phase 1.

Phase 1 uses one generic append-only table (`raw_signals`) rather than a
per-source schema — PLAN.md §4 defers real entity modeling to the Open
Foundry ontology in Phase 2. Each collector writes normalized rows here;
`source`/`signal_type` let downstream code filter without needing a schema
migration per new field.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

import duckdb

from quiverquant.config import DATA_DIR, DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_signals (
    source        VARCHAR NOT NULL,
    signal_type   VARCHAR NOT NULL,
    entity        VARCHAR,           -- token/protocol/wallet/etc. identifier
    ts            TIMESTAMP NOT NULL, -- when the underlying event/observation occurred
    fetched_at    TIMESTAMP NOT NULL, -- when we pulled it
    payload       JSON NOT NULL,      -- full normalized record
    tier          VARCHAR NOT NULL    -- 'free' or 'paid', which tier fetched this row
);
"""

_INDEX = """
CREATE INDEX IF NOT EXISTS idx_raw_signals_source_type_ts
    ON raw_signals (source, signal_type, ts);
"""


def get_connection() -> duckdb.DuckDBPyConnection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(_SCHEMA)
    con.execute(_INDEX)
    return con


def insert_signals(records: Iterable[dict[str, Any]]) -> int:
    """Insert normalized records. Each dict needs: source, signal_type, ts,
    payload, tier, and optionally entity. Returns the number of rows inserted."""
    rows = []
    now = datetime.now(timezone.utc)
    for r in records:
        rows.append(
            (
                r["source"],
                r["signal_type"],
                r.get("entity"),
                r["ts"],
                now,
                json.dumps(r["payload"], default=str),
                r["tier"],
            )
        )
    if not rows:
        return 0
    con = get_connection()
    try:
        con.executemany(
            "INSERT INTO raw_signals "
            "(source, signal_type, entity, ts, fetched_at, payload, tier) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        con.close()
    return len(rows)


def count_signals(source: str | None = None) -> int:
    con = get_connection()
    try:
        if source:
            return con.execute(
                "SELECT count(*) FROM raw_signals WHERE source = ?", [source]
            ).fetchone()[0]
        return con.execute("SELECT count(*) FROM raw_signals").fetchone()[0]
    finally:
        con.close()
