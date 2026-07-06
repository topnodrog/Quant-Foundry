"""First real strategy — Fear & Greed contrarian on BTC/USDT (long/flat).

Deliberately simple and defensible, per PLAN.md §6: prove one signal end-to-end
before adding complexity. The classic "be greedy when others are fearful" rule:

- Enter long when the market-wide Fear & Greed index is at/below ``fear_threshold``
  (fear = discounted prices).
- Exit to flat (cash) when it is at/above ``greed_threshold`` (euphoria = take
  profit / step aside). Spot CASH account, so no shorting — long or flat only.
- Otherwise hold. The gap between thresholds is hysteresis to avoid churn.

This is NOT a qualified strategy — it's the first candidate that the §6 gates
(walk-forward, statistical significance, paper trading) will judge in Phase 4.
It uses Fear & Greed only; TvlData is available on the bus for a later version.
"""

from __future__ import annotations

from collections import deque

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import BarType, DataType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from quiverquant.backtest.data import FearGreedData, TvlData


class FearGreedContrarianConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    fear_threshold: int = 30
    greed_threshold: int = 70
    trade_fraction: float = 0.95  # fraction of free cash to deploy on entry


class FearGreedContrarianStrategy(Strategy):
    def __init__(self, config: FearGreedContrarianConfig) -> None:
        super().__init__(config)
        self.latest_fg: float | None = None
        self.instrument = None
        self.entries = 0
        self.exits = 0

    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_bars(self.config.bar_type)
        self.subscribe_data(DataType(FearGreedData))

    def on_data(self, data) -> None:  # noqa: ANN001 - nautilus Data
        if isinstance(data, FearGreedData):
            self.latest_fg = data.value

    def on_bar(self, bar) -> None:  # noqa: ANN001 - nautilus Bar
        if self.latest_fg is None or self.instrument is None:
            return  # no sentiment reading yet — stay out

        is_long = self.portfolio.net_position(self.config.instrument_id) > 0

        if self.latest_fg <= self.config.fear_threshold and not is_long:
            self._enter_long(bar)
        elif self.latest_fg >= self.config.greed_threshold and is_long:
            self.close_all_positions(self.config.instrument_id)
            self.exits += 1

    def _enter_long(self, bar) -> None:  # noqa: ANN001 - nautilus Bar
        account = self.portfolio.account(self.config.instrument_id.venue)
        if account is None:
            return
        free = account.balance_free(USDT)
        if free is None:
            return
        raw_qty = (free.as_double() * self.config.trade_fraction) / float(bar.close)
        qty = self.instrument.make_qty(raw_qty)
        if qty <= 0:
            return
        order = self.order_factory.market(
            self.config.instrument_id, OrderSide.BUY, qty
        )
        self.submit_order(order)
        self.entries += 1


class RegimeContrarianConfig(FearGreedContrarianConfig, frozen=True):
    """Fear & Greed contrarian + a DeFi-TVL momentum regime gate."""

    tvl_ma_window: int = 30  # days of aggregate TVL for the moving-average trend


class RegimeContrarianStrategy(FearGreedContrarianStrategy):
    """Adds one lever to the Fear & Greed contrarian: **do not sell into greed
    while DeFi TVL momentum is still rising.**

    The base strategy's weakness is that it exits to cash on greed and then sits
    out bull rallies (hence +46% vs +195% buy-&-hold, PLAN §9). Aggregate DeFi
    TVL is a market-wide risk-on/off proxy: if it is above its moving average the
    ecosystem is still expanding, so we hold the position through euphoria and
    only take profit once TVL momentum also rolls over (``latest_tvl < MA``).

    Entry is deliberately UNCHANGED from the base strategy, so a walk-forward /
    significance comparison isolates the single hypothesis being tested (the
    regime-gated exit), rather than confounding it with a new entry rule.
    """

    def __init__(self, config: RegimeContrarianConfig) -> None:
        super().__init__(config)
        self.latest_tvl: float | None = None
        self._tvl_window: deque[float] = deque(maxlen=config.tvl_ma_window)

    def on_start(self) -> None:
        super().on_start()
        self.subscribe_data(DataType(TvlData))

    def on_data(self, data) -> None:  # noqa: ANN001 - nautilus Data
        if isinstance(data, FearGreedData):
            self.latest_fg = data.value
        elif isinstance(data, TvlData):
            self.latest_tvl = data.total_usd
            self._tvl_window.append(data.total_usd)

    def _tvl_rising(self) -> bool:
        # Need a full window before trusting the trend; until then, behave like
        # the base strategy (treat momentum as not-rising -> exit on greed).
        if self.latest_tvl is None or len(self._tvl_window) < self._tvl_window.maxlen:
            return False
        ma = sum(self._tvl_window) / len(self._tvl_window)
        return self.latest_tvl >= ma

    def on_bar(self, bar) -> None:  # noqa: ANN001 - nautilus Bar
        if self.latest_fg is None or self.instrument is None:
            return

        is_long = self.portfolio.net_position(self.config.instrument_id) > 0

        if self.latest_fg <= self.config.fear_threshold and not is_long:
            self._enter_long(bar)
        elif self.latest_fg >= self.config.greed_threshold and is_long and not self._tvl_rising():
            self.close_all_positions(self.config.instrument_id)
            self.exits += 1
