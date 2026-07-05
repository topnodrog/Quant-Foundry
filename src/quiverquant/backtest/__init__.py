"""Phase 3 — nautilus_trader backtest pipeline.

This package is the plumbing that feeds the two data streams a strategy needs
into nautilus_trader's ``BacktestEngine``:

- ``ohlcv``  — historical price bars, pulled from CCXT and cached in DuckDB.
- ``signals`` — the alt-data time series collected in Phase 1 (``raw_signals``),
  exposed as a nautilus custom ``Data`` type so it interleaves with price bars
  without lookahead bias.

Phase 3 increment 1 deliberately ships *plumbing only*: a no-op observer
strategy (``observer``) confirms both streams arrive in correct time order.
Real signal/trading logic is a later increment (PLAN.md §5/§6).
"""
