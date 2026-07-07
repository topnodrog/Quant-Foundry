"""Cross-sectional momentum on the liquid-alt universe (option 1).

Each rebalance (every ``hold`` days) rank the universe by trailing ``lookback``-day
return, hold the top ``top_k`` equal-weight until the next rebalance (buy-and-hold
within the window — no daily vol drag), then repeat. The question the gates ask
here isn't "beat BTC" but the cleaner cross-sectional one: **does ranking by
momentum beat picking the same number of coins at random from the same universe?**
That random-selection permutation is the null — and it needs no extra data because
it resamples the universe we already priced.

Selection uses only trailing data (ending at the rebalance date) to choose holdings
for the *next* window, so there's no lookahead. Survivorship caveat still applies
(today's liquid set — see ``universe.py``), but momentum rebalances and the null is
drawn from the same biased set, so the momentum-vs-random comparison is fair.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


def rebalance_windows(n_rows: int, lookback: int, hold: int) -> list[tuple[int, int]]:
    """(start_pos, end_pos) index windows: first rebalance once ``lookback`` history
    exists, then every ``hold`` rows. end_pos is the next rebalance (or last row)."""
    starts = list(range(lookback, n_rows, hold))
    out: list[tuple[int, int]] = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else n_rows - 1
        if e > s:
            out.append((s, e))
    return out


def qualifying(price_df, i: int, lookback: int):
    """Trailing-return Series for coins that have a price at both i and i-lookback."""
    now = price_df.iloc[i]
    then = price_df.iloc[i - lookback]
    ret = (now / then) - 1
    return ret.dropna()


def window_return(price_df, start_pos: int, end_pos: int, selected: list[str]) -> float | None:
    """Equal-weight buy-and-hold return over [start_pos, end_pos] for ``selected``
    coins that have complete data across the window."""
    cols = [c for c in selected if c in price_df.columns]
    if not cols:
        return None
    sub = price_df.iloc[start_pos:end_pos + 1][cols].dropna(axis=1, how="any")
    if sub.shape[1] == 0 or sub.shape[0] < 2:
        return None
    norm = sub / sub.iloc[0]           # each coin -> 1.0 at window start
    port = norm.mean(axis=1)           # equal-weight, weights drift (buy-and-hold)
    return float(port.iloc[-1]) - 1


def book_total_return(price_df, windows, lookback: int, select_fn) -> float | None:
    """Chain window returns for a selection function. ``select_fn(ret_series)``
    returns the coin ids to hold that window."""
    eq = 1.0
    any_window = False
    for start, end in windows:
        ret = qualifying(price_df, start, lookback)
        if ret.empty:
            continue
        selected = select_fn(ret)
        wr = window_return(price_df, start, end, selected)
        if wr is None:
            continue
        eq *= 1 + wr
        any_window = True
    return round((eq - 1) * 100, 2) if any_window else None


@dataclass(frozen=True)
class MomentumReport:
    universe_size: int
    lookback: int
    hold: int
    top_k: int
    n_windows: int
    start: object
    end: object
    momentum_return_pct: float | None
    market_return_pct: float | None
    btc_return_pct: float | None
    null_returns: list[float]

    @property
    def null_p_value(self) -> float | None:
        if self.momentum_return_pct is None or not self.null_returns:
            return None
        ge = sum(1 for r in self.null_returns if r >= self.momentum_return_pct)
        return round((ge + 1) / (len(self.null_returns) + 1), 4)

    @property
    def null_mean_pct(self) -> float | None:
        return round(sum(self.null_returns) / len(self.null_returns), 2) if self.null_returns else None


def run_momentum(
    lookback: int = 90, hold: int = 30, top_k: int = 10,
    n_permutations: int = 500, seed: int = 42,
) -> MomentumReport:
    from quiverquant.features.token_prices import read_price_df
    from quiverquant.features.universe import read_universe_ids

    ids = read_universe_ids()
    price_df = read_price_df(ids)
    if price_df.empty:
        raise ValueError("no universe prices — run `quiverquant collect-universe` first")
    price_df = price_df.dropna(axis=1, how="all")

    windows = rebalance_windows(len(price_df), lookback, hold)
    if not windows:
        raise ValueError("not enough history for the chosen lookback/hold")

    def mom(ret):
        return list(ret.nlargest(top_k).index)

    def market(ret):
        return list(ret.index)

    momentum = book_total_return(price_df, windows, lookback, mom)
    market_ret = book_total_return(price_df, windows, lookback, market)

    rng = random.Random(seed)

    def rand(ret):
        idx = list(ret.index)
        return rng.sample(idx, min(top_k, len(idx)))

    null = []
    for _ in range(n_permutations):
        r = book_total_return(price_df, windows, lookback, rand)
        if r is not None:
            null.append(r)

    start_dt = price_df.index[windows[0][0]]
    end_dt = price_df.index[windows[-1][1]]

    return MomentumReport(
        universe_size=price_df.shape[1],
        lookback=lookback, hold=hold, top_k=top_k, n_windows=len(windows),
        start=start_dt, end=end_dt,
        momentum_return_pct=momentum,
        market_return_pct=market_ret,
        btc_return_pct=_btc_return(start_dt, end_dt),
        null_returns=null,
    )


def _btc_return(start, end) -> float | None:
    from quiverquant.backtest.ohlcv import read_ohlcv_df

    df = read_ohlcv_df("binance", "BTC/USDT", "1d")
    if df.empty:
        return None
    df = df[(df.index >= start) & (df.index <= end)]
    if len(df) < 2:
        return None
    return round((float(df["close"].iloc[-1]) / float(df["close"].iloc[0]) - 1) * 100, 2)


def print_report(r: MomentumReport) -> None:
    print("\n=== Cross-sectional momentum (long top-K alts, monthly rebalance) ===")
    print(f"  window            : {r.start.date()} -> {r.end.date()}  ({r.n_windows} rebalances)")
    print(f"  universe          : {r.universe_size} alts   lookback {r.lookback}d · hold {r.hold}d · top {r.top_k}")
    print(f"\n  momentum book     : {_fmt(r.momentum_return_pct)}%")
    print(f"  equal-weight market: {_fmt(r.market_return_pct)}%")
    print(f"  BTC buy-&-hold    : {_fmt(r.btc_return_pct)}%")
    if r.null_returns:
        print(f"\n  random top-{r.top_k} books (n={len(r.null_returns)}): mean {_fmt(r.null_mean_pct)}%")
        print(f"  momentum vs random-selection null : p = {r.null_p_value}")
        if r.null_p_value is not None and r.null_p_value <= 0.05:
            print("    -> momentum ranking BEATS random selection at p<=0.05")
        else:
            print("    -> momentum ranking NOT distinguishable from random selection")
    print("\n  *** survivorship-biased universe (today's liquid set) - directional, not gospel.")


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"
