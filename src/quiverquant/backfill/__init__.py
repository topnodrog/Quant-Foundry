"""Historical backfills — turn point-in-time collectors into real time series.

The Phase 1 collectors mostly capture *current state* (one row per run), which
can't be backtested. These backfills pull the full available history for the
sources that expose it for free, storing it into the same ``raw_signals`` table
so the backtest signal reader and the ontology bridge both see it.

Run via ``uv run quiverquant backfill <source>``:
  - ``fear-greed``    — full Crypto Fear & Greed history (Alternative.me)
  - ``defillama-tvl`` — daily TVL history per top protocol (DefiLlama)
"""
