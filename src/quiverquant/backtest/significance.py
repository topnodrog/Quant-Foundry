"""Statistical-significance check (PLAN.md §6 step 3).

A backtest return means nothing on its own — a coin-flip strategy on a rising
market also "makes money." The question is whether *this signal* did better than
the same strategy fed **noise**. This is a Monte-Carlo permutation test:

1. Run the real strategy over the full window -> ``actual`` return.
2. Many times, randomly **permute the Fear & Greed values across their own
   timestamps** and re-run. Shuffling values (not timestamps) keeps the price path
   and the signal's marginal distribution and trade cadence intact, but destroys
   any real relationship between sentiment and the price that follows it — exactly
   the null hypothesis "the signal carries no predictive information."
3. p-value = fraction of shuffled runs that did *at least as well* as the real one
   (with the standard +1/+1 correction so it's never a literal zero).

The test statistic is **total net-worth return**, not Sharpe/Sortino: with only a
handful of trades over the window (see README/PLAN §9) a daily-return ratio is too
noisy to trust, whereas end-to-end return is exactly what we care about and is
well-defined for every permutation.

A low p-value is necessary, not sufficient — walk-forward (``walkforward.py``) and
paper trading still gate promotion. And note the honest caveat: with one asset and
one four-year window, "beats shuffled-signal noise" is a weak bar. It rejects the
most embarrassing failure mode (no edge at all); it does not prove a durable edge.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from quiverquant.backtest.data import DevActivityData, FearGreedData, NewsSentimentData
from quiverquant.backtest.harness import Dataset, load_dataset, run_window


@dataclass(frozen=True)
class SignificanceReport:
    actual_return_pct: float | None
    n_permutations: int
    permuted_returns: list[float]
    seed: int
    strategy: str = "sentiment"

    @property
    def n_ge_actual(self) -> int:
        """Permutations that matched or beat the real strategy's return."""
        if self.actual_return_pct is None:
            return self.n_permutations
        return sum(1 for r in self.permuted_returns if r >= self.actual_return_pct)

    @property
    def p_value(self) -> float:
        # (b + 1) / (n + 1): standard unbiased Monte-Carlo permutation p-value.
        return round((self.n_ge_actual + 1) / (self.n_permutations + 1), 4)

    @property
    def null_mean_pct(self) -> float | None:
        if not self.permuted_returns:
            return None
        return round(sum(self.permuted_returns) / len(self.permuted_returns), 2)

    @property
    def null_max_pct(self) -> float | None:
        return round(max(self.permuted_returns), 2) if self.permuted_returns else None

    @property
    def null_min_pct(self) -> float | None:
        return round(min(self.permuted_returns), 2) if self.permuted_returns else None


def _shuffle_values(fg: list[FearGreedData], rng: random.Random) -> list[FearGreedData]:
    """New series: same timestamps, Fear & Greed values (and their labels)
    permuted across them. Breaks signal->price alignment, keeps the marginal
    distribution and count identical."""
    order = list(range(len(fg)))
    rng.shuffle(order)
    return [
        FearGreedData(
            ts_event=fg[i].ts_event,
            ts_init=fg[i].ts_init,
            value=fg[j].value,
            classification=fg[j].classification,
        )
        for i, j in enumerate(order)
    ]


def _shuffle_dev(dev: list[DevActivityData], rng: random.Random) -> list[DevActivityData]:
    """Dev-activity analogue of ``_shuffle_values``: same timestamps, commit counts
    permuted across them (breaks builder-momentum->price alignment)."""
    order = list(range(len(dev)))
    rng.shuffle(order)
    return [
        DevActivityData(
            ts_event=dev[i].ts_event,
            ts_init=dev[i].ts_init,
            total_commits=dev[j].total_commits,
            repo_count=dev[j].repo_count,
        )
        for i, j in enumerate(order)
    ]


def _shuffle_sentiment(sent: list[NewsSentimentData], rng: random.Random) -> list[NewsSentimentData]:
    """News-sentiment analogue: same timestamps, net-sentiment values permuted."""
    order = list(range(len(sent)))
    rng.shuffle(order)
    return [
        NewsSentimentData(
            ts_event=sent[i].ts_event,
            ts_init=sent[i].ts_init,
            net_sentiment=sent[j].net_sentiment,
        )
        for i, j in enumerate(order)
    ]


def permutation_test(
    dataset: Dataset | None = None,
    *,
    n_permutations: int = 100,
    strategy: str = "sentiment",
    fear_threshold: int = 30,
    greed_threshold: int = 70,
    tvl_ma_window: int = 30,
    dev_ma_window: int = 8,
    news_low: float = -0.10,
    news_high: float = 0.05,
    starting_balance: float = 100_000.0,
    seed: int = 42,
    progress: bool = True,
    **load_kwargs,
) -> SignificanceReport:
    """Permutation-test a strategy against a shuffled version of its primary signal.

    The signal the strategy keys on is shuffled (Fear & Greed for
    ``sentiment``/``regime``, dev-activity for ``dev``); any secondary series stays
    intact. So for ``regime`` the null is the stricter "does the TVL gate add value
    on top of a *noise* sentiment signal?", and for ``dev`` it is "does builder
    momentum beat a shuffled commit series?".
    """
    if n_permutations < 1:
        raise ValueError("n_permutations must be >= 1")

    if dataset is None:
        dataset = load_dataset(**load_kwargs)
    if not dataset.bars:
        raise ValueError("no price bars loaded")

    # Attach only the streams a strategy uses: sentiment=fg, regime=fg+tvl, dev=dev,
    # news=sentiment. Shuffle the signal the strategy keys on; keep any secondary real.
    tvl_stream = dataset.tvl if strategy == "regime" else None

    def _run(fg_series, dev_series, sent_series):
        return run_window(
            dataset, dataset.bars, fg_series, tvl_stream, dev_series, sent_series,
            strategy=strategy, fear_threshold=fear_threshold, greed_threshold=greed_threshold,
            tvl_ma_window=tvl_ma_window, dev_ma_window=dev_ma_window,
            news_low=news_low, news_high=news_high, starting_balance=starting_balance,
        )

    if strategy == "news":
        actual = _run([], None, dataset.sentiment)
    elif strategy == "dev":
        actual = _run([], dataset.dev, None)
    else:
        actual = _run(dataset.fg, None, None)

    rng = random.Random(seed)
    permuted: list[float] = []
    for k in range(n_permutations):
        if strategy == "news":
            r = _run([], None, _shuffle_sentiment(dataset.sentiment, rng))
        elif strategy == "dev":
            r = _run([], _shuffle_dev(dataset.dev, rng), None)
        else:
            r = _run(_shuffle_values(dataset.fg, rng), None, None)
        permuted.append(r.strategy_return_pct if r.strategy_return_pct is not None else 0.0)
        if progress and (k + 1) % 20 == 0:
            print(f"  [significance] {k + 1}/{n_permutations} permutations...")

    return SignificanceReport(
        actual_return_pct=actual.strategy_return_pct,
        n_permutations=n_permutations,
        permuted_returns=permuted,
        seed=seed,
        strategy=strategy,
    )


_STRATEGY_LABEL = {
    "sentiment": "Fear & Greed contrarian",
    "regime": "Fear & Greed contrarian + TVL-momentum regime gate",
    "dev": "Developer-activity momentum",
    "news": "Crypto-news-sentiment contrarian",
}


def print_report(report: SignificanceReport) -> None:
    label = _STRATEGY_LABEL.get(report.strategy, report.strategy)
    print(f"\n=== Statistical-significance check ({label}, permutation test) ===")
    print(f"  actual strategy return   : {_fmt(report.actual_return_pct)}%")
    print(f"  permutations             : {report.n_permutations} (shuffled Fear & Greed, seed {report.seed})")
    print(f"  null distribution        : min {_fmt(report.null_min_pct)}% / "
          f"mean {_fmt(report.null_mean_pct)}% / max {_fmt(report.null_max_pct)}%")
    print(f"  permutations >= actual   : {report.n_ge_actual}/{report.n_permutations}")
    print(f"  p-value                  : {report.p_value}")
    if report.p_value <= 0.05:
        verdict = "signal beats noise at p<=0.05 (necessary, not sufficient - still needs walk-forward + paper)"
    else:
        verdict = "NOT distinguishable from shuffled-signal noise at p<=0.05"
    print(f"  verdict                  : {verdict}")


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"
