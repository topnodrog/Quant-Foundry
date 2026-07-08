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


# --- walk-forward validation (§6 step 2 for the pit book) ---------------------

DEFAULT_GRID: list[tuple[int, int, int]] = [
    # (lookback, hold, top_k) — spans monthly (candidate #6's guess) to the
    # weekly cadence the academic momentum factor actually uses.
    (90, 30, 10), (90, 30, 5), (30, 30, 10),
    (30, 7, 10), (60, 14, 15), (30, 7, 5),
]


def _windows_in(price_df, lookback: int, hold: int, lo: int, hi: int):
    """Rebalance windows whose START index falls in [lo, hi). Selection at a
    window start only uses trailing data, so bounding by start introduces no
    lookahead even though a window's end may cross ``hi``."""
    return [w for w in rebalance_windows(len(price_df), lookback, hold) if lo <= w[0] < hi]


def pit_walkforward(
    grid: list[tuple[int, int, int]] | None = None,
    n_folds: int = 4, train_frac: float = 0.4, fee_bps: float = 10.0,
    top_n: int = 80, oos_permutations: int = 200, seed: int = 42,
) -> dict:
    """Anchored walk-forward over the point-in-time universe.

    Per fold: grid-search (lookback, hold, top_k) on all data BEFORE the fold
    (in-sample criterion = momentum minus the equal-weight active book, a cheap
    stand-in for the random-null mean), then score the chosen config on the
    fold's out-of-sample window against a fresh random-selection null. The
    number that matters is the OOS pattern across folds, not any in-sample p."""
    from quiverquant.features.pit_universe import membership_series, pit_price_df

    grid = grid or DEFAULT_GRID
    membership = membership_series(top_n=top_n)
    all_slugs = sorted({s for _, members in membership for s in members})
    price_df = pit_price_df(all_slugs).dropna(axis=1, how="all")
    n = len(price_df)
    fee_rate = fee_bps / 10_000.0

    train_end0 = int(n * train_frac)
    fold_len = (n - train_end0) // n_folds

    def mom_fn(top_k):
        def f(ret, active):
            return list(ret.nlargest(top_k).index)
        return f

    def market_fn(ret, active):
        return list(ret.index)

    folds = []
    for k in range(n_folds):
        t0 = train_end0 + k * fold_len
        t1 = n if k == n_folds - 1 else t0 + fold_len

        # in-sample: everything before the fold (anchored/expanding)
        best = None
        for lb, hold, tk in grid:
            w_is = _windows_in(price_df, lb, hold, lb, t0)
            if not w_is:
                continue
            mom, _ = pit_book_return(price_df, w_is, lb, membership, mom_fn(tk), fee_rate)
            mkt, _ = pit_book_return(price_df, w_is, lb, membership, market_fn, fee_rate)
            if mom is None or mkt is None:
                continue
            excess = mom - mkt
            if best is None or excess > best["is_excess"]:
                best = {"lookback": lb, "hold": hold, "top_k": tk, "is_excess": round(excess, 2)}
        if best is None:
            continue

        # out-of-sample: the fold window, chosen config, fresh null
        lb, hold, tk = best["lookback"], best["hold"], best["top_k"]
        w_oos = _windows_in(price_df, lb, hold, t0, t1)
        mom_oos, n_active = pit_book_return(price_df, w_oos, lb, membership, mom_fn(tk), fee_rate)

        rng = random.Random(seed + k)

        def rand(ret, active):
            idx = list(ret.index)
            return rng.sample(idx, min(tk, len(idx)))

        null = []
        for _ in range(oos_permutations):
            r, _ = pit_book_return(price_df, w_oos, lb, membership, rand, fee_rate)
            if r is not None:
                null.append(r)
        null_mean = round(sum(null) / len(null), 2) if null else None
        p = None
        if mom_oos is not None and null:
            ge = sum(1 for r in null if r >= mom_oos)
            p = round((ge + 1) / (len(null) + 1), 4)

        folds.append({
            **best,
            "test_start": str(price_df.index[t0].date()),
            "test_end": str(price_df.index[min(t1, n - 1)].date()),
            "oos_windows": n_active or 0,
            "oos_momentum_pct": mom_oos,
            "oos_null_mean_pct": null_mean,
            "oos_p": p,
        })

    beat = sum(1 for f in folds if f["oos_momentum_pct"] is not None and f["oos_null_mean_pct"] is not None
               and f["oos_momentum_pct"] > f["oos_null_mean_pct"])
    sig = sum(1 for f in folds if f["oos_p"] is not None and f["oos_p"] <= 0.05)
    compounded = 1.0
    any_oos = False
    for f in folds:
        if f["oos_momentum_pct"] is not None:
            compounded *= 1 + f["oos_momentum_pct"] / 100
            any_oos = True
    return {
        "folds": folds,
        "folds_beat_null_mean": beat,
        "folds_significant": sig,
        "compounded_oos_pct": round((compounded - 1) * 100, 2) if any_oos else None,
        "fee_bps": fee_bps, "grid_size": len(grid or []),
    }


def print_walkforward(s: dict) -> None:
    print("\n=== Survivorship-free momentum — anchored walk-forward ===")
    print(f"  grid: {s['grid_size']} configs · fee {s['fee_bps']}bps · "
          f"{len(s['folds'])} folds\n")
    print(f"  {'fold OOS window':24} {'chosen (lb/hold/K)':>18} {'OOS mom%':>9} {'null%':>8} {'p':>7}")
    for f in s["folds"]:
        cfg = f"{f['lookback']}/{f['hold']}/{f['top_k']}"
        print(f"  {f['test_start']} -> {f['test_end']:12} {cfg:>18} "
              f"{_fmt(f['oos_momentum_pct']):>9} {_fmt(f['oos_null_mean_pct']):>8} "
              f"{f['oos_p'] if f['oos_p'] is not None else 'n/a':>7}")
    print(f"\n  folds beating the random-null mean : {s['folds_beat_null_mean']}/{len(s['folds'])}")
    print(f"  folds significant at p<=0.05       : {s['folds_significant']}/{len(s['folds'])}")
    print(f"  compounded OOS momentum            : {_fmt(s['compounded_oos_pct'])}%")


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
