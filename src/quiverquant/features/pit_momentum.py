"""Survivorship-free cross-sectional momentum (PLAN.md §9 step 2 — candidate #6 re-run).

Candidate #6 (features/momentum.py) ranked *today's* liquid alts — a universe that by
construction excludes every coin that died. This re-runs the same idea on the
survivorship-free data built in step 1: at each rebalance, the candidate set is exactly
the coins that were in that DATE's CoinMarketCap top-N (from ``universe_snapshot``) and
have price history (``pit_price_history``, sourced Binance-archive-first so dead coins
are included). Rank by trailing return, hold the top-K equal-weight until the next
rebalance.

Two honesty upgrades over candidate #6:
1. **Point-in-time membership** — a coin can only be picked in a window where it was
   really top-N, so a name that later 100×'d doesn't get retro-selected before it
   mattered, and a name that died is held through its collapse and realizes the loss.
2. **Turnover fees** — each rebalance pays a round-trip taker fee on the fraction of the
   book that actually changed hands, so a high-churn strategy is charged for it.

The null is unchanged in spirit and still the right one: random selection from the SAME
point-in-time membership set each window. momentum-vs-random isolates whether the RANKING
carries information, and both sides now share identical (survivorship-free) membership.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from quiverquant.features.momentum import qualifying, rebalance_windows, window_return


def _active_set(membership, when):
    """The most recent snapshot's member set on-or-before ``when`` (a pandas Timestamp)."""
    active: set[str] = set()
    wd = when.date() if hasattr(when, "date") else when
    for snap_date, members in membership:
        if snap_date <= wd:
            active = members
        else:
            break
    return active


def _turnover_cost(prev: set[str], cur: set[str], fee_rate: float) -> float:
    """Round-trip taker cost for moving from equal-weight book ``prev`` to ``cur``.

    Sold fraction = |prev\\cur|/|prev|, bought fraction = |cur\\prev|/|cur|; each pays
    ``fee_rate`` once. First rebalance (prev empty) pays the full entry (bought=100%)."""
    if not cur:
        return 0.0
    bought = len(cur - prev) / len(cur)
    sold = (len(prev - cur) / len(prev)) if prev else 0.0
    return fee_rate * (bought + sold)


def pit_book_return(price_df, windows, lookback, membership, select_fn, fee_rate):
    """Chain window returns with point-in-time membership + turnover fees.

    ``select_fn(ret_series, active_set)`` returns the slugs to hold. Returns
    ``(total_return_pct, n_active_windows)`` or ``(None, 0)`` if no window traded."""
    eq = 1.0
    prev: set[str] = set()
    active_windows = 0
    for start, end in windows:
        when = price_df.index[start]
        active = _active_set(membership, when)
        if not active:
            continue
        ret = qualifying(price_df, start, lookback)
        ret = ret[ret.index.isin(active)]  # only coins that were really top-N then
        if ret.empty:
            continue
        selected = select_fn(ret, active)
        if not selected:
            continue
        cur = set(selected)
        eq *= 1 - _turnover_cost(prev, cur, fee_rate)  # pay to trade into this book
        wr = window_return(price_df, start, end, selected)
        if wr is None:
            continue
        eq *= 1 + wr
        prev = cur
        active_windows += 1
    if active_windows == 0:
        return None, 0
    return round((eq - 1) * 100, 2), active_windows


@dataclass(frozen=True)
class PitMomentumReport:
    lookback: int
    hold: int
    top_k: int
    fee_bps: float
    n_windows: int
    start: object
    end: object
    momentum_return_pct: float | None
    null_returns: list[float]
    priced_universe: int
    median_active: int

    @property
    def null_p_value(self) -> float | None:
        if self.momentum_return_pct is None or not self.null_returns:
            return None
        ge = sum(1 for r in self.null_returns if r >= self.momentum_return_pct)
        return round((ge + 1) / (len(self.null_returns) + 1), 4)

    @property
    def null_mean_pct(self) -> float | None:
        return round(sum(self.null_returns) / len(self.null_returns), 2) if self.null_returns else None


def run_pit_momentum(
    lookback: int = 90, hold: int = 30, top_k: int = 10, fee_bps: float = 10.0,
    n_permutations: int = 500, seed: int = 42, top_n: int = 80,
) -> PitMomentumReport:
    """Run survivorship-free cross-sectional momentum. ``fee_bps`` is the one-way
    taker fee in basis points (10 = 0.1%, Binance spot); a round trip on changed
    names is charged each rebalance."""
    from quiverquant.features.pit_universe import membership_series, pit_price_df

    membership = membership_series(top_n=top_n)
    if not membership:
        raise ValueError("no point-in-time membership — run resolve-universe + collect-pit-prices first")

    all_slugs = sorted({s for _, members in membership for s in members})
    price_df = pit_price_df(all_slugs).dropna(axis=1, how="all")
    if price_df.empty:
        raise ValueError("no priced universe — run collect-pit-prices first")

    windows = rebalance_windows(len(price_df), lookback, hold)
    if not windows:
        raise ValueError("not enough price history for the chosen lookback/hold")

    fee_rate = fee_bps / 10_000.0

    def mom(ret, active):
        return list(ret.nlargest(top_k).index)

    momentum, n_active = pit_book_return(price_df, windows, lookback, membership, mom, fee_rate)

    rng = random.Random(seed)

    def make_rand():
        def rand(ret, active):
            idx = list(ret.index)
            return rng.sample(idx, min(top_k, len(idx)))
        return rand

    null = []
    for _ in range(n_permutations):
        r, _ = pit_book_return(price_df, windows, lookback, membership, make_rand(), fee_rate)
        if r is not None:
            null.append(r)

    active_sizes = sorted(len(_active_set(membership, price_df.index[s])) for s, _ in windows)
    median_active = active_sizes[len(active_sizes) // 2] if active_sizes else 0

    return PitMomentumReport(
        lookback=lookback, hold=hold, top_k=top_k, fee_bps=fee_bps,
        n_windows=n_active, start=price_df.index[windows[0][0]], end=price_df.index[windows[-1][1]],
        momentum_return_pct=momentum, null_returns=null,
        priced_universe=price_df.shape[1], median_active=median_active,
    )


def print_report(r: PitMomentumReport) -> None:
    print("\n=== Survivorship-free cross-sectional momentum (candidate #6 re-run) ===")
    print(f"  window            : {r.start.date()} -> {r.end.date()}  ({r.n_windows} rebalances)")
    print(f"  priced universe   : {r.priced_universe} slugs   median {r.median_active} tradeable per rebalance")
    print(f"  params            : lookback {r.lookback}d · hold {r.hold}d · top {r.top_k} · fee {r.fee_bps}bps round-trip")
    print(f"\n  momentum book     : {_fmt(r.momentum_return_pct)}%   (after fees)")
    if r.null_returns:
        print(f"  random top-{r.top_k} books (n={len(r.null_returns)}): mean {_fmt(r.null_mean_pct)}%")
        print(f"  momentum vs random-selection null : p = {r.null_p_value}")
        if r.null_p_value is not None and r.null_p_value <= 0.05:
            print("    -> momentum ranking BEATS random selection at p<=0.05  *** PASSES significance gate")
        else:
            print("    -> momentum ranking NOT distinguishable from random selection")
    print("\n  Survivorship-free: point-in-time top-N membership, dead coins priced from the")
    print("  Binance archive and held through their collapse. Identity caveats (reused")
    print("  tickers, homonym name-matches) noted in research/survivorship-free-universe.md.")


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"
