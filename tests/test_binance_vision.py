"""Tests for the Binance-archive kline parser (pure, no network).

Runs under pytest, or standalone: ``python tests/test_binance_vision.py``.
"""

from __future__ import annotations

import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.backfill.binance_vision import _pair, parse_kline_zip  # noqa: E402

# Real row shape from a BTCST/USDT June-2021 archive month (verified live —
# BTCST was delisted from Binance in 2021, proving the archive survives delisting).
_CSV = (
    "1622505600000,37.38700000,39.76000000,34.37400000,35.92700000,150312.98900000,"
    "1622591999999,5463742.60598000,22065,74997.68300000,2725326.30847600,0\n"
    "1622592000000,35.90000000,36.50000000,35.00000000,36.10000000,90000.00000000,"
    "1622678399999,3200000.00000000,15000,50000.00000000,1800000.00000000,0\n"
)


def _zip_bytes(csv_text: str, name: str = "BTCSTUSDT-1d-2021-06.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, csv_text)
    return buf.getvalue()


def test_parses_headerless_kline_csv_into_six_columns():
    rows = parse_kline_zip(_zip_bytes(_CSV))
    assert rows == [
        [1622505600000.0, 37.387, 39.76, 34.374, 35.927, 150312.989],
        [1622592000000.0, 35.9, 36.5, 35.0, 36.1, 90000.0],
    ]


def test_tolerates_a_leading_header_row():
    csv_with_header = "open_time,open,high,low,close,volume,x,x,x,x,x,x\n" + _CSV
    rows = parse_kline_zip(_zip_bytes(csv_with_header))
    assert len(rows) == 2
    assert rows[0][1] == 37.387


def test_normalizes_microsecond_timestamps_to_ms():
    # Binance's ~2025+ archive files ship open_time in MICROSECONDS (16 digits);
    # older files use milliseconds (13 digits). Both must land as ms so downstream
    # `fromtimestamp(ts/1000)` doesn't overflow (OSError [Errno 22]).
    micros = (
        "1704067200000000,42283.58,44184.10,42180.77,44179.55,27174.29,"
        "1704153599999999,1169995682.02,1114623,14331.73,617352094.56,0\n"
    )
    rows = parse_kline_zip(_zip_bytes(micros))
    assert rows[0][0] == 1704067200000.0  # µs -> ms, i.e. 2024-01-01
    # sanity: it must be convertible to a real date without overflow
    import datetime as _dt
    assert _dt.datetime.fromtimestamp(rows[0][0] / 1000, tz=_dt.timezone.utc).year == 2024


def test_pair_strips_the_ccxt_slash():
    assert _pair("BTCST/USDT") == "BTCSTUSDT"
    assert _pair("BTC/USDT") == "BTCUSDT"


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
