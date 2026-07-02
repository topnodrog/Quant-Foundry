"""Whale Alert — real-time large-transaction alerts. PLAN.md §2 #7.

PLAN.md scoped this as "free feed not paid API" — i.e. Whale Alert's X/
Telegram feed, not their paid REST API. Neither has a clean keyless HTTP
endpoint:
  - X/Telegram require their own auth (a Telegram bot token to read
    @whale_alert's public channel via the Bot API, or X API access).
  - Their paid REST API (api.whale-alert.io) is explicitly out of scope.

Not implemented yet — needs a decision on which free feed to integrate
(Telegram Bot API is the more tractable of the two: no X API cost/limits)
before writing fetch(). WHALE_ALERT_SOURCE in config.py is a placeholder
for whichever token that ends up needing.
"""

from __future__ import annotations

from typing import Any, Iterable

from quiverquant.collectors.base import Collector


class WhaleAlertCollector(Collector):
    name = "whale_alert"

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        return []
