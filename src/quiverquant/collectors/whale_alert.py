"""Whale Alert — real-time large-transaction alerts. PLAN.md §2 #7.

Telegram's Bot API can only deliver `channel_post` updates for channels a
bot administers — there's no way to add our own bot to Whale Alert's
channel, so a bot token doesn't actually solve this. The practical free
path instead: Telegram's public web preview at `t.me/s/<channel>`, a
no-auth HTML page Telegram serves for link-sharing/SEO that lists a
channel's latest posts. Confirmed live 2026-07-03 against `whale_alert_io`
— NOT `whale_alert` (that handle's last post was 2020-03-11; `whale_alert_io`
is the currently active one, matched by cross-referencing its "og:description"
and post recency).

This is an HTML scrape of an undocumented page with no SLA — acceptable for
a free-tier signal per PLAN.md's framing, but expect it to need repair if
Telegram changes their markup. Message text is free-form ("$X #TOKEN
(Y USD) transferred from A to B", "... minted/burned at C", or plain news
links with no transaction data at all), so parsing is best-effort: amount/
token/usd_value when the pattern matches, full raw text always kept in the
payload. Dedupes against already-stored Telegram post IDs (queries
raw_signals directly) so repeated runs don't reinsert the same ~20 posts
every time — unlike the snapshot-style collectors elsewhere in this repo,
re-fetching identical rows here would be pure waste, not a desired
time-series.
"""

from __future__ import annotations

import html as html_module
import re
from datetime import datetime, timezone
from typing import Any, Iterable

import requests

from quiverquant.collectors.base import Collector
from quiverquant.storage import get_connection

CHANNEL = "whale_alert_io"
PREVIEW_URL = f"https://t.me/s/{CHANNEL}"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_MESSAGE_BLOCK_RE = re.compile(
    r'data-post="%s/(\d+)".*?tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>.*?'
    r'<time[^>]*datetime="([^"]+)"' % re.escape(CHANNEL),
    re.S,
)
_TX_RE = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*[#$]([A-Za-z0-9]+)\s*\(([\d,]+(?:\.\d+)?)\s*USD\)\s*(.+)",
    re.S,
)
_TRAILING_LINK_LABEL_RE = re.compile(r"(Details|Read Analysis|Tx:\s*\S+)\s*$")


class WhaleAlertCollector(Collector):
    name = "whale_alert"

    def fetch(self, tier: str) -> Iterable[dict[str, Any]]:
        resp = requests.get(PREVIEW_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
        if resp.status_code != 200:
            return
        last_seen = _last_seen_post_id()
        for post_id, raw_text, ts_str in _MESSAGE_BLOCK_RE.findall(resp.text):
            post_id = int(post_id)
            if post_id <= last_seen:
                continue
            text = html_module.unescape(re.sub(r"<[^>]+>", "", raw_text)).strip()
            ts = datetime.fromisoformat(ts_str)
            yield _parse_message(post_id, text, ts)


def _parse_message(post_id: int, text: str, ts: datetime) -> dict[str, Any]:
    match = _TX_RE.search(text)
    if not match:
        return {
            "signal_type": "whale_alert_news",
            "entity": None,
            "ts": ts,
            "payload": {"post_id": post_id, "text": text},
        }
    amount, token, usd_value, rest = match.groups()
    description = _TRAILING_LINK_LABEL_RE.sub("", rest.strip()).strip()
    return {
        "signal_type": "whale_transfer",
        "entity": token.upper(),
        "ts": ts,
        "payload": {
            "post_id": post_id,
            "amount": float(amount.replace(",", "")),
            "token": token.upper(),
            "usd_value": float(usd_value.replace(",", "")),
            "description": description,
            "text": text,
        },
    }


def _last_seen_post_id() -> int:
    con = get_connection()
    try:
        row = con.execute(
            "SELECT max(CAST(json_extract_string(payload, '$.post_id') AS INTEGER)) "
            "FROM raw_signals WHERE source = 'whale_alert'"
        ).fetchone()
    finally:
        con.close()
    return row[0] if row and row[0] is not None else 0
