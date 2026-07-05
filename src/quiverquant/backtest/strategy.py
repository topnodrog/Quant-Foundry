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

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import BarType, DataType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from quiverquant.backtest.data import FearGreedData


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
