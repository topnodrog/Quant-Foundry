# Survivorship-free cross-sectional data — research notes (2026-07-07)

**UPDATE (later same day): both collectors built, tested, and run for real.**
`backfill/cmc_snapshots.py` (`quiverquant backfill cmc-snapshots`) confirmed CMC's
`/historical/YYYYMMDD/` pages are server-rendered HTML (checked 2015 and 2022 samples byte-for-byte
— no `__NEXT_DATA__` JSON trick needed, no browser UA needed, no login gate on the data itself).
Ran a monthly backfill 2018-01→2026-06: **104 snapshots, 0 failures, 417 distinct coins ever
ranked top-80** — vs. 48 in candidate #6's current CoinGecko-today universe. Confirmed real
recoveries: BitConnect (rank 20, 2018-01-01 only — the Ponzi scheme collapsed within weeks),
HEX, Terra + TerraUSD (last seen 2022-07, matching the real collapse), FTX Token (last seen
2024-01, matching FTX's wind-down), Waves (dropped 2022-09, its real de-peg crisis).

`backfill/binance_vision.py` (`quiverquant backfill binance-archive --symbol X/USDT`) confirmed
data.binance.vision serves monthly kline zips for delisted pairs. Verified against BTCST/USDT
(delisted from Binance in 2021 for wash-trading): backfilled 682 real daily bars, 2021-01-13
through 2022-11-28 — a full year+ of price history that CCXT's live `fetch_ohlcv` cannot see at
all today. Rows go straight into the existing `ohlcv` table (`exchange="binance"`), so no schema
changes and no risk of colliding with live-CCXT-cached data for the same pair.

**Not yet done:** joining these into a time-varying universe for the momentum backtest (resolving
the ~200+ members that only have a name/slug, not a ticker; picking a price source per coin per
era; re-running walk-forward against `universe_snapshot(t)` instead of a static list). See PLAN.md
§9 step 2 for the exact recipe.

---

The cross-sectional experiments so far (VC-conviction book, momentum candidate #6) all share
one caveat big enough to invalidate a positive result: the universe is **today's** liquid set.
Coins that died (LUNA, FTT, SafeMoon, ~58% of everything ever listed) are absent, and industry
estimates put the resulting inflation of backtested returns at 200–400%. The momentum design
partially defuses this (the random-selection null draws from the same biased set, so the
*ranking-vs-random* p-value is fair), but absolute returns, market comparisons, and any
long-term "hold the book" conclusion remain upper bounds until membership is point-in-time.

## The two halves of the fix (both free)

### 1. Point-in-time universe membership — CoinMarketCap `/historical/` snapshots

- CMC publishes weekly snapshot pages back to 2013: `coinmarketcap.com/historical/YYYYMMDD/`
  — the top coins by market cap *as ranked on that date*, dead coins included.
- Free HTML (no API key). Also mirrored on archive.org if CMC ever gates it.
  The `crypto2` R package demonstrates the underlying data is reachable keylessly.
- Plan: scrape ~monthly snapshots 2019→today (≈90 pages — well inside the Firecrawl budget
  if plain `requests` doesn't parse cleanly), store `(snapshot_date, rank, symbol, name)` in a
  `universe_snapshot` DuckDB table. That is the membership function `universe(t)`.
- The paid-API alternative (Concretum Group's approach: iterate all ~40k permanent CMC IDs via
  `/v2/cryptocurrency/ohlcv/historical`) gets per-coin history for everything ever listed, but
  needs a paid plan and ~20h of rate-limited pulls. Snapshots + exchange archives below get us
  the same decision-relevant answer for free.

### 2. Price history for dead/delisted coins — Binance public data archive

- `data.binance.vision` (github.com/binance/binance-public-data) hosts monthly/daily kline
  zips per pair, **including pairs that no longer trade** — the archive is append-only, so a
  delisted coin's history up to its delisting stays downloadable. Free, no key, plain HTTPS.
- CCXT `fetch_ohlcv` (what we use today) can only see currently-listed markets — that is
  exactly the survivorship hole. The archive closes it for every coin that was ever on Binance,
  which for top-80-by-mcap membership since 2019 is the overwhelming majority.
- Plan: a `binance_vision` backfill module — given `universe_snapshot` symbols, download
  `data/spot/monthly/klines/<SYMBOL>USDT/1d/*.zip`, unpack into `token_price_history`
  (keyed by symbol at first; gecko_id mapping only matters for the graph joins).
- Delisting IS the crash in many cases — a book holding a coin into delisting should realize
  that loss. Rule: if a held coin's prices stop mid-window, mark the position down to its last
  archived close (conservative: assume exit at the final print, or −100% stress variant).

## Why cross-sectional momentum is the right next target (literature)

- Liu, Tsyvinski & Wu, "Common Risk Factors in Cryptocurrency" (J. Finance 2022; SSRN 3379131):
  market + size + **momentum** three-factor model prices the crypto cross-section; the momentum
  effect concentrates in *large* coins (matches our top-80 liquid universe), weekly frequency.
- JFQA 2024 "A Trend Factor for the Cross Section of Cryptocurrency Returns": trend/momentum
  information at multiple horizons carries cross-sectional predictive power.
- Multiple 2024-25 replications ("…under Realistic Assumptions") confirm cross-sectional
  momentum survives realistic fees on liquid subsets, while daily BTC *timing* strategies —
  what candidates #1–#5 were — generally do not. Our own gate scoreboard reproduced that split.

Caveat the literature also flags: crypto momentum is regime-dependent and drawdown-prone
(2022-style crashes hit past winners hardest). Walk-forward folds must straddle a full
bull/bear cycle before believing any p-value.

## Sources

- https://concretumgroup.com/building-a-survivorship-bias-free-crypto-dataset-with-coinmarketcap-api/
- https://coinmarketcap.com/historical/
- https://stratbase.ai/en/blog/survivorship-bias-crypto (dead-coin failure rates, bias magnitude)
- https://data.binance.vision/ and https://github.com/binance/binance-public-data
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3379131 (Liu-Tsyvinski-Wu)
- https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/trend-factor-for-the-cross-section-of-cryptocurrency-returns/4C1509ACBA33D5DCAF0AC24379148178
- https://www.sebastianstoeckl.com/crypto2/ (keyless CMC access precedent)
