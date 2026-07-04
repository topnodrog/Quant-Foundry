"""Shared interface every collector implements.

`fetch()` does the network work and returns normalized dicts; `run()` wraps
that with the tier lookup and storage write so collectors stay pure/testable
independent of DuckDB.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable

from quiverquant.config import get_source
from quiverquant.storage import insert_signals


class Collector(ABC):
    #: key into quiverquant.config.SOURCES
    name: str

    @abstractmethod
    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        """Fetch and normalize records. Each record must include at least:
        signal_type, ts, payload (source/tier are filled in by run())."""
        raise NotImplementedError

    def run(self) -> int:
        source = get_source(self.name)
        tier = source.tier()
        records = []
        for r in self.fetch(tier):
            r.setdefault("source", self.name)
            r.setdefault("tier", tier)
            records.append(r)
        return insert_signals(records)
