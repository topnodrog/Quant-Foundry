"""CCXT — cross-exchange ticker snapshots (price/volume/spread). Free, public
market-data endpoints, no key. PLAN.md §2 #2.

Tracking the same symbols across exchanges is what makes this a QuiverQuant-
style signal (cross-venue spread/liquidity divergence), not just a single
price feed — that's why fetch() loops exchanges x symbols rather than
picking one venue.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import ccxt

from quiverquant.collectors.base import Collector

DEFAULT_EXCHANGES = ["binance", "coinbase", "kraken", "okx"]
DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT"]


class CCXTCollector(Collector):
    name = "ccxt"

    def __init__(
        self,
        exchanges: list[str] | None = None,
        symbols: list[str] | None = None,
    ):
        self.exchange_ids = exchanges or DEFAULT_EXCHANGES
        self.symbols = symbols or DEFAULT_SYMBOLS

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        for exchange_id in self.exchange_ids:
            try:
                exchange = getattr(ccxt, exchange_id)()
            except AttributeError:
                continue
            for symbol in self.symbols:
                yield from self._fetch_ticker(exchange, exchange_id, symbol)

    def _fetch_ticker(
        self, exchange: ccxt.Exchange, exchange_id: str, symbol: str
    ) -> Iterable[dict[str, Any]]:
        try:
            ticker = exchange.fetch_ticker(symbol)
        except Exception as exc:  # noqa: BLE001 - one bad venue/symbol shouldn't kill the run
            yield {
                "signal_type": "ticker_error",
                "entity": f"{exchange_id}:{symbol}",
                "ts": datetime.now(timezone.utc),
                "payload": {"error": str(exc)},
            }
            return
        ts = ticker.get("timestamp")
        ts_dt = (
            datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            if ts
            else datetime.now(timezone.utc)
        )
        yield {
            "signal_type": "ticker_snapshot",
            "entity": f"{exchange_id}:{symbol}",
            "ts": ts_dt,
            "payload": {
                "exchange": exchange_id,
                "symbol": symbol,
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "last": ticker.get("last"),
                "baseVolume": ticker.get("baseVolume"),
                "quoteVolume": ticker.get("quoteVolume"),
                "percentage": ticker.get("percentage"),
            },
        }
