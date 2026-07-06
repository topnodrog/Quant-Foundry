"""Cross-sectional VC-conviction long book (path 1, step C).

The first backtest that actually *uses* the graph-derived VC signal: hold an
equal-weight book of the VC-backed tokens and ask whether the **high-conviction**
subset (projects backed by >=2 distinct funds) beats (a) just holding BTC and
(b) a random equal-weight subset of the same VC universe.

Two nulls, on purpose:
- **BTC benchmark** answers "did this beat the obvious passive alternative?"
- **Random-subset permutation** answers "did *conviction* matter, or would any
  random pick of VC names have done as well?" — it needs no extra data because it
  resamples within the universe we already priced.

READ THIS BEFORE TRUSTING ANY NUMBER: the constituent list is a *current*
VC-portfolio snapshot, so it is **survivorship-biased** — dead VC bets are absent,
which inflates returns. Tokens also list at different dates, so the book's
composition grows over time (early history rests on very few names). This is an
educational upper bound, not a qualified strategy. The honest version needs the
point-in-time portfolio history from the path-2 archive.org scraper.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from quiverquant.features.graph import conviction_ranking, read_backings
from quiverquant.features.token_prices import read_price_df
from quiverquant.features.token_resolve import read_map


def conviction_companies(min_funds: int = 2) -> set[str]:
    """Company names backed by >= ``min_funds`` distinct funds."""
    return {c for c, _ in conviction_ranking(read_backings(), min_funds=min_funds)}


def _company_to_gecko() -> dict[str, str]:
    return {r.company: r.gecko_id for r in read_map()}


def universe_ids() -> list[str]:
    """All resolved VC-backed token ids (the full VC book)."""
    return [r.gecko_id for r in read_map()]


def conviction_ids(min_funds: int = 2) -> list[tuple[str, str]]:
    """(company, gecko_id) for high-conviction names that resolved to a token."""
    m = _company_to_gecko()
    conv = conviction_companies(min_funds=min_funds)
    return [(c, m[c]) for c in sorted(conv) if c in m]


def book_daily_returns(price_df, gecko_ids: list[str]):
    """Equal-weight, daily-rebalanced book return series (mean of available
    constituents' daily returns each day)."""
    cols = [g for g in gecko_ids if g in price_df.columns]
    if not cols:
        return None
    rets = price_df[cols].pct_change()
    return rets.mean(axis=1)  # skipna -> equal weight across whoever has data that day


def total_return_pct(daily_returns) -> float | None:
    if daily_returns is None or daily_returns.dropna().empty:
        return None
    eq = (1 + daily_returns.fillna(0)).cumprod()
    return round((float(eq.iloc[-1]) - 1) * 100, 2)


def btc_benchmark_pct(start, end) -> float | None:
    """BTC/USDT buy-&-hold over [start, end) from the cached CCXT ohlcv table."""
    from quiverquant.backtest.ohlcv import read_ohlcv_df

    df = read_ohlcv_df("binance", "BTC/USDT", "1d")
    if df.empty:
        return None
    df = df[(df.index >= start) & (df.index < end)]
    if len(df) < 2:
        return None
    return round((float(df["close"].iloc[-1]) / float(df["close"].iloc[0]) - 1) * 100, 2)


@dataclass(frozen=True)
class CrossSectionReport:
    n_universe: int
    conviction: list[tuple[str, str]]
    start: object
    end: object
    conviction_return_pct: float | None
    universe_return_pct: float | None
    btc_return_pct: float | None
    null_returns: list[float]
    n_permutations: int

    @property
    def null_p_value(self) -> float | None:
        """Fraction of random same-size VC subsets that matched/beat conviction."""
        if self.conviction_return_pct is None or not self.null_returns:
            return None
        ge = sum(1 for r in self.null_returns if r >= self.conviction_return_pct)
        return round((ge + 1) / (len(self.null_returns) + 1), 4)

    @property
    def null_mean_pct(self) -> float | None:
        return round(sum(self.null_returns) / len(self.null_returns), 2) if self.null_returns else None


def run_cross_section(min_funds: int = 2, n_permutations: int = 500, seed: int = 42) -> CrossSectionReport:
    price_df = read_price_df()
    if price_df.empty:
        raise ValueError("no token prices cached — run `quiverquant collect-prices` first")

    uni = [g for g in universe_ids() if g in price_df.columns]
    conv_pairs = [(c, g) for c, g in conviction_ids(min_funds=min_funds) if g in price_df.columns]
    conv_ids = [g for _, g in conv_pairs]

    start, end = price_df.index.min(), price_df.index.max()

    conv_daily = book_daily_returns(price_df, conv_ids)
    uni_daily = book_daily_returns(price_df, uni)

    # Random-subset null: same size as the conviction book, drawn from the VC universe.
    rng = random.Random(seed)
    k = len(conv_ids)
    null: list[float] = []
    if 0 < k < len(uni):
        for _ in range(n_permutations):
            pick = rng.sample(uni, k)
            r = total_return_pct(book_daily_returns(price_df, pick))
            if r is not None:
                null.append(r)

    return CrossSectionReport(
        n_universe=len(uni),
        conviction=conv_pairs,
        start=start,
        end=end,
        conviction_return_pct=total_return_pct(conv_daily),
        universe_return_pct=total_return_pct(uni_daily),
        btc_return_pct=btc_benchmark_pct(start, end),
        null_returns=null,
        n_permutations=n_permutations,
    )


def print_report(r: CrossSectionReport) -> None:
    print("\n=== Cross-sectional VC-conviction book (path 1) ===")
    print(f"  window            : {r.start.date()} -> {r.end.date()}")
    print(f"  VC universe (priced): {r.n_universe} tokens")
    print(f"  conviction book   : {len(r.conviction)} tokens (backed by >=2 funds)")
    print(f"    {', '.join(c for c, _ in r.conviction)}")
    print(f"\n  conviction book return : {_fmt(r.conviction_return_pct)}%")
    print(f"  full VC book return    : {_fmt(r.universe_return_pct)}%")
    print(f"  BTC buy-&-hold         : {_fmt(r.btc_return_pct)}%")
    if r.null_returns:
        print(f"\n  random {len(r.conviction)}-token VC subsets (n={len(r.null_returns)}): "
              f"mean {_fmt(r.null_mean_pct)}%")
        print(f"  conviction vs random-subset null : p = {r.null_p_value}")
        if r.null_p_value is not None and r.null_p_value <= 0.05:
            print("    -> conviction beats random VC picks at p<=0.05 (within-universe)")
        else:
            print("    -> conviction NOT distinguishable from random VC picks")
    print("\n  *** SURVIVORSHIP-BIASED (current-holdings snapshot) + growing composition:")
    print("  *** educational upper bound, NOT a qualified strategy. See module docstring.")


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"
