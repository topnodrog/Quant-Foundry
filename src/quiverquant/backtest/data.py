"""nautilus_trader data adapters — the bridge between our stored data and the
types ``BacktestEngine`` consumes.

Two conversions live here:

- ``build_bars``      — DuckDB OHLCV DataFrame -> list[nautilus ``Bar``], via the
  official ``BarDataWrangler`` (so precision/formatting matches the instrument).
- ``FearGreedData`` + ``build_fear_greed_data`` — ``raw_signals`` Fear & Greed
  points -> a nautilus custom ``Data`` subclass, so the sentiment series flows
  through the same time-ordered event stream as price bars.

``FearGreedData`` is intentionally the first/only custom type wired up; adding a
second alt-data series later is a copy of this pattern.
"""

# NOTE: no `from __future__ import annotations` here — nautilus's
# @customdataclass introspects real annotation types (e.g. float.__name__),
# which PEP 563 stringized annotations would break.

from datetime import datetime

import pandas as pd

from nautilus_trader.core.data import Data
from nautilus_trader.model.custom import customdataclass
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.persistence.wranglers import BarDataWrangler

from quiverquant.backtest.signals import (
    DevTotalPoint,
    SentimentPoint,
    SignalPoint,
    TvlTotalPoint,
)


@customdataclass
class FearGreedData(Data):
    """Market-wide Crypto Fear & Greed reading as a nautilus custom data event.

    ``value`` is the 0-100 index; ``classification`` is the bucket label
    ("Extreme Fear" .. "Extreme Greed"). ``@customdataclass`` injects
    ``ts_event``/``ts_init`` and Arrow/dict serialization.
    """

    value: float
    classification: str


@customdataclass
class TvlData(Data):
    """Aggregate DeFi TVL (USD, summed across tracked protocols) for one day —
    a market-wide risk-on/off proxy delivered as a nautilus custom data event.
    """

    total_usd: float
    protocol_count: int


@customdataclass
class DevActivityData(Data):
    """Market-wide developer activity (commits summed across tracked core repos)
    for one ISO week — a builder-momentum proxy delivered as a nautilus custom
    data event.
    """

    total_commits: int
    repo_count: int


@customdataclass
class NewsSentimentData(Data):
    """Monthly crypto-news net sentiment (avg positive-minus-negative over sampled
    articles) delivered as a nautilus custom data event."""

    net_sentiment: float


def build_bars(
    instrument: Instrument,
    bar_type: BarType,
    df: pd.DataFrame,
) -> list[Bar]:
    """Convert an OHLCV DataFrame (index = tz-aware UTC, columns
    open/high/low/close/volume) into nautilus ``Bar`` objects."""
    if df.empty:
        return []
    wrangler = BarDataWrangler(bar_type, instrument)
    return wrangler.process(df)


def _dt_to_ns(ts: datetime) -> int:
    """UTC datetime -> Unix nanoseconds (nautilus timestamp unit)."""
    return int(ts.timestamp() * 1_000_000_000)


def build_fear_greed_data(points: list[SignalPoint]) -> list[FearGreedData]:
    """Map stored Fear & Greed ``SignalPoint``s into ``FearGreedData`` events.

    Skips points whose payload has no numeric ``value``. ``ts_event`` and
    ``ts_init`` are both the reading's timestamp — the index is dated as of that
    day's close, so there's no separate arrival time to model.
    """
    out: list[FearGreedData] = []
    for p in points:
        raw = p.payload.get("value")
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        ns = _dt_to_ns(p.ts)
        out.append(
            FearGreedData(
                ts_event=ns,
                ts_init=ns,
                value=value,
                classification=str(p.payload.get("classification") or ""),
            )
        )
    return out


def build_tvl_data(points: list[TvlTotalPoint]) -> list["TvlData"]:
    """Map aggregate daily TVL points into ``TvlData`` events."""
    out: list[TvlData] = []
    for p in points:
        ns = _dt_to_ns(p.ts)
        out.append(
            TvlData(
                ts_event=ns,
                ts_init=ns,
                total_usd=float(p.total_usd),
                protocol_count=int(p.protocol_count),
            )
        )
    return out


def build_dev_data(points: list[DevTotalPoint]) -> list["DevActivityData"]:
    """Map market-wide weekly dev-activity points into ``DevActivityData`` events."""
    out: list[DevActivityData] = []
    for p in points:
        ns = _dt_to_ns(p.ts)
        out.append(
            DevActivityData(
                ts_event=ns,
                ts_init=ns,
                total_commits=int(p.total_commits),
                repo_count=int(p.repo_count),
            )
        )
    return out


def build_news_sentiment_data(points: list[SentimentPoint]) -> list["NewsSentimentData"]:
    """Map monthly sentiment points into ``NewsSentimentData`` events."""
    out: list[NewsSentimentData] = []
    for p in points:
        ns = _dt_to_ns(p.ts)
        out.append(
            NewsSentimentData(ts_event=ns, ts_init=ns, net_sentiment=float(p.net_sentiment))
        )
    return out
