"""Walk-forward validation (PLAN.md §6 step 2).

A strategy that only works on the exact window whose parameters were tuned on it
is overfit, not qualified. Walk-forward guards against that: pick parameters on an
*in-sample* (training) window, then score them on the *next, unseen* out-of-sample
(test) window — and repeat, rolling forward. Only the out-of-sample results count.

Scheme here: **anchored (expanding) walk-forward.** The timeline is split into an
initial minimum training block (``train_frac`` of the span) followed by ``n_splits``
equal out-of-sample test windows. For each fold the training set is *everything
before* that fold's test window (so it grows fold to fold), a small threshold grid
is searched in-sample, and the single best (fear, greed) pair is evaluated once,
out-of-sample, on the test window. Each test window is an independent backtest that
starts from cash — nautilus has no turnkey walk-forward, so this is the "scripted
orchestration" §6 calls for, built on ``harness.run_window``.

The in-sample selection criterion is **excess return over buy-&-hold** (not raw
return): a Fear & Greed contrarian that merely rode a bull market up isn't evidence
the *signal* did anything, so we reward beating the passive benchmark, not the
market going up.
"""

from __future__ import annotations

from dataclasses import dataclass

from quiverquant.backtest.harness import (
    Dataset,
    WindowResult,
    load_dataset,
    run_window,
    slice_bars,
    slice_dev,
    slice_fg,
    slice_sentiment,
    slice_tvl,
    time_bounds,
)

# Small, defensible threshold grid. Kept coarse: each extra pair is another
# in-sample engine run per fold, and finer tuning is exactly the overfitting
# walk-forward exists to expose.
DEFAULT_FEARS = (20, 25, 30, 35)
DEFAULT_GREEDS = (60, 65, 70, 75, 80)
DEFAULT_DEV_WINDOWS = (4, 8, 13, 26)  # ISO weeks for the dev-activity moving average
DEFAULT_NEWS_LOWS = (-0.20, -0.10, -0.05)   # net-sentiment capitulation entry
DEFAULT_NEWS_HIGHS = (0.0, 0.05, 0.10)      # net-sentiment euphoria exit


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold: chosen params + their out-of-sample scorecard.

    ``params`` are the ``run_window`` kwargs of the winning in-sample config;
    ``param_label`` is a compact human rendering (e.g. ``F30/G70`` or ``MA8w``).
    """

    index: int
    train_bars: int
    params: dict
    param_label: str
    in_sample_excess_pct: float | None
    test: WindowResult


def _param_grid(strategy: str, fears, greeds, dev_windows,
                news_lows=DEFAULT_NEWS_LOWS, news_highs=DEFAULT_NEWS_HIGHS) -> list[dict]:
    """In-sample search grid as ``run_window`` kwargs, per strategy."""
    if strategy == "dev":
        return [{"dev_ma_window": w} for w in dev_windows]
    if strategy == "news":
        return [
            {"news_low": lo, "news_high": hi}
            for lo in news_lows for hi in news_highs if lo < hi
        ]
    # sentiment / regime tune the sentiment thresholds; regime also gets a fixed
    # tvl_ma_window from the caller (not searched, to keep the grid small).
    return [
        {"fear_threshold": f, "greed_threshold": g}
        for f in fears for g in greeds if f < g
    ]


def _param_label(params: dict) -> str:
    if "dev_ma_window" in params:
        return f"MA{params['dev_ma_window']}w"
    if "news_low" in params:
        return f"L{params['news_low']}/H{params['news_high']}"
    return f"F{params.get('fear_threshold')}/G{params.get('greed_threshold')}"


def _best_params(
    dataset: Dataset,
    train_bars: list,
    train_fg,
    train_tvl,
    train_dev,
    train_sent,
    grid: list[dict],
    starting_balance: float,
    strategy: str,
    tvl_ma_window: int,
) -> tuple[dict, float | None]:
    """Pick the grid config with the highest in-sample excess-over-buy&hold."""
    best_params: dict = dict(grid[0])
    best_excess: float | None = None
    best_score = float("-inf")
    for params in grid:
        r = run_window(
            dataset, train_bars, train_fg, train_tvl, train_dev, train_sent,
            strategy=strategy, tvl_ma_window=tvl_ma_window,
            starting_balance=starting_balance, **params,
        )
        score = r.excess_pct
        if score is None:
            continue
        if score > best_score:
            best_score = score
            best_params, best_excess = dict(params), score
    return best_params, best_excess


@dataclass(frozen=True)
class WalkForwardReport:
    n_splits: int
    train_frac: float
    folds: list[Fold]
    strategy: str = "sentiment"

    @property
    def oos_returns(self) -> list[float]:
        return [f.test.strategy_return_pct for f in self.folds if f.test.strategy_return_pct is not None]

    @property
    def oos_excess(self) -> list[float]:
        return [f.test.excess_pct for f in self.folds if f.test.excess_pct is not None]

    @property
    def compounded_oos_pct(self) -> float | None:
        """Return of stitching the out-of-sample windows together end to end."""
        rs = self.oos_returns
        if not rs:
            return None
        eq = 1.0
        for r in rs:
            eq *= 1 + r / 100
        return round((eq - 1) * 100, 2)

    @property
    def folds_positive(self) -> int:
        return sum(1 for r in self.oos_returns if r > 0)

    @property
    def folds_beating_buyhold(self) -> int:
        return sum(1 for e in self.oos_excess if e > 0)


def walk_forward(
    dataset: Dataset | None = None,
    *,
    n_splits: int = 4,
    train_frac: float = 0.4,
    fears=DEFAULT_FEARS,
    greeds=DEFAULT_GREEDS,
    dev_windows=DEFAULT_DEV_WINDOWS,
    strategy: str = "sentiment",
    tvl_ma_window: int = 30,
    starting_balance: float = 100_000.0,
    **load_kwargs,
) -> WalkForwardReport:
    """Run anchored walk-forward validation. ``strategy`` = ``sentiment`` (Fear &
    Greed only), ``regime`` (adds the TVL-momentum exit gate), ``dev``
    (developer-activity momentum), or ``news`` (crypto-news-sentiment contrarian)."""
    if not 0 < train_frac < 1:
        raise ValueError("train_frac must be in (0, 1)")
    if n_splits < 1:
        raise ValueError("n_splits must be >= 1")

    if dataset is None:
        dataset = load_dataset(**load_kwargs)
    if not dataset.bars:
        raise ValueError("no price bars loaded")

    grid = _param_grid(strategy, fears, greeds, dev_windows)
    if not grid:
        raise ValueError("empty search grid")

    ts0, ts_end = time_bounds(dataset.bars)
    span = ts_end - ts0
    initial_train_end = ts0 + int(span * train_frac)
    test_span = (ts_end - initial_train_end) / n_splits

    folds: list[Fold] = []
    for i in range(n_splits):
        test_start = initial_train_end + int(i * test_span)
        test_end = ts_end if i == n_splits - 1 else initial_train_end + int((i + 1) * test_span)

        train_bars = slice_bars(dataset.bars, ts0, test_start)
        train_fg = slice_fg(dataset.fg, ts0, test_start)
        train_tvl = slice_tvl(dataset.tvl, ts0, test_start)
        train_dev = slice_dev(dataset.dev, ts0, test_start)
        train_sent = slice_sentiment(dataset.sentiment, ts0, test_start)
        # Signal history predates price bars, so include all points up to the test
        # window (they warm up latest_fg / the TVL/dev/sentiment readings before the
        # first test bar).
        test_bars = slice_bars(dataset.bars, test_start, test_end)
        test_fg = slice_fg(dataset.fg, ts0, test_end)
        test_tvl = slice_tvl(dataset.tvl, ts0, test_end)
        test_dev = slice_dev(dataset.dev, ts0, test_end)
        test_sent = slice_sentiment(dataset.sentiment, ts0, test_end)

        best_params, is_excess = _best_params(
            dataset, train_bars, train_fg, train_tvl, train_dev, train_sent, grid,
            starting_balance, strategy, tvl_ma_window,
        )
        test_result = run_window(
            dataset, test_bars, test_fg, test_tvl, test_dev, test_sent,
            strategy=strategy, tvl_ma_window=tvl_ma_window,
            starting_balance=starting_balance, **best_params,
        )
        folds.append(
            Fold(
                index=i,
                train_bars=len(train_bars),
                params=best_params,
                param_label=_param_label(best_params),
                in_sample_excess_pct=is_excess,
                test=test_result,
            )
        )

    return WalkForwardReport(
        n_splits=n_splits, train_frac=train_frac, folds=folds, strategy=strategy
    )


_STRATEGY_LABEL = {
    "sentiment": "Fear & Greed contrarian",
    "regime": "Fear & Greed contrarian + TVL-momentum regime gate",
    "dev": "Developer-activity momentum",
    "news": "Crypto-news-sentiment contrarian",
}


def print_report(report: WalkForwardReport) -> None:
    label = _STRATEGY_LABEL.get(report.strategy, report.strategy)
    print(f"\n=== Walk-forward validation ({label}) ===")
    print(f"  {'fold':>4} {'train_bars':>10} {'params':>12} {'test_bars':>9} "
          f"{'oos_ret%':>9} {'buyhold%':>9} {'excess%':>8}")
    for f in report.folds:
        t = f.test
        print(f"  {f.index:>4} {f.train_bars:>10} {f.param_label:>12} {t.n_bars:>9} "
              f"{_fmt(t.strategy_return_pct):>9} {_fmt(t.buy_hold_return_pct):>9} {_fmt(t.excess_pct):>8}")

    n = len(report.folds)
    print(f"\n  out-of-sample compounded return : {_fmt(report.compounded_oos_pct)}%")
    print(f"  folds positive                  : {report.folds_positive}/{n}")
    print(f"  folds beating buy-&-hold        : {report.folds_beating_buyhold}/{n}")
    verdict = (
        "PASS-ish" if report.folds_beating_buyhold > n / 2 else "does NOT consistently beat buy&hold"
    )
    print(f"  walk-forward verdict            : {verdict}")
    print("  (out-of-sample only; in-sample tuning excluded - see PLAN.md sec.6 step 2)")


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"
