"""Tests for the CMC historical-snapshot parser (pure HTML parsing, no network).

Runs under pytest, or standalone: ``python tests/test_cmc_snapshots.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.backfill.cmc_snapshots import parse_snapshot  # noqa: E402

# Trimmed real markup shape (two full rows + two locked "sign up" teaser rows),
# matching what coinmarketcap.com/historical/YYYYMMDD/ actually renders.
HTML = """
<table>
<tr class="cmc-table-row"><td class="cmc-table__cell cmc-table__cell--sort-by__rank"><div class="">1</div></td>
<td><div class="cmc-table__column-name"><a href="/currencies/bitcoin/" title="Bitcoin" class="cmc-table__column-name--symbol cmc-link">BTC</a><a href="/currencies/bitcoin/" title="Bitcoin" class="cmc-table__column-name--name cmc-link">Bitcoin</a></div></td>
<td class="cmc-table__cell cmc-table__cell--sort-by__market-cap"><div>$902,104,193,384.61</div></td></tr>
<tr class="cmc-table-row"><td class="cmc-table__cell cmc-table__cell--sort-by__rank"><div class="">2</div></td>
<td><div class="cmc-table__column-name"><a href="/currencies/ethereum/" title="Ethereum" class="cmc-table__column-name--symbol cmc-link">ETH</a><a href="/currencies/ethereum/" title="Ethereum" class="cmc-table__column-name--name cmc-link">Ethereum</a></div></td>
<td class="cmc-table__cell cmc-table__cell--sort-by__market-cap"><div>$448,537,615,143.00</div></td></tr>
<tr class="sc-c594c4ec-1 hfEsTf cmc-table-row"><td></td><td class="name-cell"><span class="image-placeholder"></span><a href="/currencies/terrausd/" class="cmc-link">TerraUSD</a></td><td colSpan="999" style="height:44px"></td></tr>
<tr class="sc-c594c4ec-1 hfEsTf cmc-table-row"><td></td><td class="name-cell"><span class="image-placeholder"></span><a href="/currencies/ftx-token/" class="cmc-link">FTX Token</a></td><td colSpan="999" style="height:44px"></td></tr>
</table>
"""


def test_parses_full_rows_with_rank_symbol_and_market_cap():
    rows = parse_snapshot(HTML)
    btc, eth = rows[0], rows[1]
    assert btc == {"rank": 1, "slug": "bitcoin", "name": "Bitcoin", "symbol": "BTC", "market_cap": 902104193384.61}
    assert eth["rank"] == 2 and eth["symbol"] == "ETH"


def test_teaser_rows_get_positional_rank_and_no_symbol_or_market_cap():
    rows = parse_snapshot(HTML)
    terra, ftt = rows[2], rows[3]
    assert terra == {"rank": 3, "slug": "terrausd", "name": "TerraUSD", "symbol": None, "market_cap": None}
    assert ftt == {"rank": 4, "slug": "ftx-token", "name": "FTX Token", "symbol": None, "market_cap": None}


def test_rank_is_contiguous_across_full_and_teaser_rows():
    ranks = [r["rank"] for r in parse_snapshot(HTML)]
    assert ranks == [1, 2, 3, 4]


def test_empty_html_returns_no_rows():
    assert parse_snapshot("<html><body>nothing here</body></html>") == []


def test_teaser_only_html_starts_rank_at_21():
    html = (
        '<tr class="sc-c594c4ec-1 hfEsTf cmc-table-row"><td></td>'
        '<td class="name-cell"><span class="image-placeholder"></span>'
        '<a href="/currencies/dogecoin/" class="cmc-link">Dogecoin</a></td>'
        '<td colSpan="999" style="height:44px"></td></tr>'
    )
    rows = parse_snapshot(html)
    assert rows == [{"rank": 21, "slug": "dogecoin", "name": "Dogecoin", "symbol": None, "market_cap": None}]


def _run_standalone() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
