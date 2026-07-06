"""Tests for the Wayback VC extractor (pure HTML parsing, no network).

Runs under pytest, or standalone: ``python tests/test_wayback.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from quiverquant.features.wayback_vc import Snapshot, extract_companies  # noqa: E402

HTML = """
<div>
  <a target="_blank" rel="noopener noreferrer" href="https://uniswap.org/" class="x y">
    <span class="text-neutral-5">Uniswap</span></a>
  <a target="_blank" rel="noopener noreferrer" href="https://aztec.network/">Aztec</a>
  <a target="_blank" href="https://twitter.com/a16z">Follow us</a>
  <a target="_blank" href="https://a16zcrypto.com/team/">Our Team</a>
  <a href="/internal">no target</a>
</div>
"""


def test_extracts_external_portfolio_companies():
    got = extract_companies(HTML)
    assert set(got) == {"Uniswap", "Aztec"}
    assert got["Uniswap"] == "https://uniswap.org/"


def test_skips_social_and_own_domain_links():
    got = extract_companies(HTML)
    assert "Follow us" not in got  # twitter skipped
    assert "Our Team" not in got   # a16z own-domain skipped


def test_skips_non_target_blank_links():
    got = extract_companies('<a href="https://x.io">NoTarget</a>')
    assert got == {}


def test_strips_nested_tags_from_name():
    html = '<a target="_blank" href="https://foo.io/"><span><b>Foo</b> Labs</span></a>'
    assert extract_companies(html) == {"Foo Labs": "https://foo.io/"}


def test_snapshot_date_and_raw_url():
    s = Snapshot(timestamp="20260702172538", original="https://a16zcrypto.com/portfolio/", status="200")
    assert s.date == "2026-07-02"
    assert s.raw_url == "https://web.archive.org/web/20260702172538id_/https://a16zcrypto.com/portfolio/"


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
