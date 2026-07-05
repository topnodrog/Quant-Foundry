"""No-op observer strategy — Phase 3 increment 1's deliverable.

It places no orders. Its only job is to prove the plumbing: that price ``Bar``s
and the ``FearGreedData`` custom stream both arrive, and that the
``BacktestEngine`` delivers them in non-decreasing event-time order (no
lookahead). It records counts, first/last event times, and any out-of-order
delivery, which ``run.py`` surfaces as the run summary.

Real trading logic replaces ``on_bar``/``on_data`` in a later increment
(PLAN.md §5/§6).
"""

from __future__ import annotations

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import BarType, DataType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from quiverquant.backtest.data import FearGreedData


class ObserverConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType


class ObserverStrategy(Strategy):
    def __init__(self, config: ObserverConfig) -> None:
        super().__init__(config)
        self.bar_count = 0
        self.signal_count = 0
        self.first_ts_event: int | None = None
        self.last_ts_event: int | None = None
        self.out_of_order = 0
        self._prev_ts_event = 0

    def on_start(self) -> None:
        self.subscribe_bars(self.config.bar_type)
        self.subscribe_data(DataType(FearGreedData))
        self.log.info("ObserverStrategy started — subscribed to bars + FearGreedData")

    def on_bar(self, bar) -> None:  # noqa: ANN001 - nautilus Bar
        self.bar_count += 1
        self._track(bar.ts_event)

    def on_data(self, data) -> None:  # noqa: ANN001 - nautilus Data
        if isinstance(data, FearGreedData):
            self.signal_count += 1
            self._track(data.ts_event)

    def on_stop(self) -> None:
        self.log.info(
            f"ObserverStrategy stop — bars={self.bar_count} "
            f"signals={self.signal_count} out_of_order={self.out_of_order}"
        )

    def _track(self, ts_event: int) -> None:
        if self.first_ts_event is None:
            self.first_ts_event = ts_event
        self.last_ts_event = ts_event
        if self._prev_ts_event and ts_event < self._prev_ts_event:
            self.out_of_order += 1
        self._prev_ts_event = ts_event
