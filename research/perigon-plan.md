# Perigon — best use of a 150-call/month news API

**Date:** 2026-07-06. **Constraint:** the plan gives **150 API calls/month** (~5/day).
This doc is the spending strategy. Perigon is the **news/sentiment** source — the
PLAN.md §2 category we're weakest in (today only the coarse market-wide Alternative.me
Fear & Greed index; CryptoPanic was dropped for having no free tier).

## What Perigon offers (grounded)

- **`GET /v1/all`** — article search. Filters confirmed from the docs: keyword `q`
  (boolean), publish-date `from`/`to` (yyyy-mm-dd) and ingestion-date `addDateFrom/To`,
  `source`/`sourceGroup`, `category`/`topic`, **sentiment** (`positiveSentimentFrom/To`,
  `negativeSentimentFrom/To`, 0-1), and entity filters (`companySymbol`, `companyDomain`,
  `personName`, `personWikidataId`, `journalistId`). `size` up to **100 articles/call**,
  `page` for pagination, `sortBy` (date/relevance/addDate).
- Article records carry **per-article sentiment**, entities, companies (with tickers),
  topics, categories, keywords, source, publish date, and a summary.
- Other endpoints: `stories` (clustered/deduped events), `journalists`, `sources`,
  `people`, `companies`, and a vector/semantic search. A Python SDK (`perigon`) and an
  MCP server exist.

## The scarce resource is CALLS, not articles

Each call returns up to 100 articles. So the rule is: **few, broad, dated batch
queries — never per-token daily polling.** 150 calls/month is generous *if* each call
does heavy lifting (a month-wide window at size=100), and trivial to blow *if* we poll.

## The one unknown that decides everything: history lookback

News APIs gate historical depth by tier. We do **not** know how far back this plan
reaches, and it changes the whole strategy. So the **first call** is the probe
(`quiverquant perigon-probe`), which queries a narrow 2022 window: if it returns
articles, backfill is viable; if not, history is shallow (recent-only) and Perigon
can only accumulate a series **forward**.

## Two high-value uses (both need the probe result first)

**Use A — a crypto news-sentiment index (feeds the Phase-4 gates).** Unlike the VC
graph data (cross-sectional), a dated sentiment series is a genuine **market-timing**
signal we can run through walk-forward/significance beside Fear & Greed and TVL. Build
it cheaply by *sampling*: one call per month, size=100, the month's top crypto articles
with sentiment → a monthly aggregate sentiment/coverage index.
- If history is deep: backfill ~2-4 years ≈ **24-48 calls one-time**, then **1/month**.
- If shallow: skip backfill, accumulate **1/month** forward.

**Use B — funding-announcement mining (point-in-time VC backing, survivorship-proof).**
This directly complements **path 2**: news archives include rounds for projects that
later *died*, with real announcement **dates** — exactly what the current-holdings
portfolio scrape lacks. A handful of targeted queries (`"a16z crypto" Series`,
`Paradigm led`, etc.) over history → `(project, investor, date, amount)` events.
- One-time: **~10-20 calls** if history is deep. Otherwise defer to forward capture.

## Recommended monthly budget (assuming the probe shows usable history)

| Item | Cadence | Calls |
|---|---|---|
| Probe (verify key + lookback) | once | 1 |
| Sentiment index backfill (~2-3 yrs, monthly windows) | once | ~30 |
| Funding-event mining (targeted historical queries) | once | ~15 |
| Sentiment index refresh | monthly | ~2 |
| Funding-event refresh | monthly | ~2 |
| Ad-hoc / reserve | — | rest |

That's a ~45-call one-time spend and ~4/month ongoing — comfortably inside 150/month
with large headroom. **Do not** wire Perigon into any per-token or per-day loop.

## Status

Key plumbing is in (`PERIGON_API_KEY` in config/.env/.env.example; client +
`perigon-probe` in `collectors/perigon.py`). Next action for the user: paste the key
into `.env`, run `quiverquant perigon-probe`, and we branch on the lookback result.
The response shape is parsed defensively and will be confirmed against that first call.
