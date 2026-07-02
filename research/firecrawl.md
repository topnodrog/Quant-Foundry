# Firecrawl.dev — Research Report

**Scope:** Evaluate Firecrawl.dev as the scraping layer for a free/open-data crypto
"alternative data" aggregator, under the constraint of the **free plan (1,000
pages/credits per month)**. Research-only — no signup performed, no code written.

**Researched:** 2026-07-02, via firecrawl.dev/docs.firecrawl.dev pages, GitHub docs
repo, and independent 2026 reviews. Firecrawl ships fast; treat exact numbers below
as a snapshot and re-verify against `docs.firecrawl.dev` before building.

---

## 1. What Firecrawl.dev Actually Does

Firecrawl is a "context API" that turns arbitrary web content into clean,
LLM-ready data. It's positioned for AI agents/RAG pipelines, not just generic
scraping — the differentiator is that it handles JS rendering, anti-bot/proxy
evasion, PDF/doc parsing, and markdown/HTML/JSON cleanup for you, behind one API.

Core products (all under REST endpoints at `https://api.firecrawl.dev/v2/`):

| Endpoint | What it does |
|---|---|
| **`/scrape`** | Fetch one URL, return markdown / clean HTML / raw HTML / links / screenshot / JSON (schema or prompt-based) / images / a structured "product" object / audio-video (e.g. YouTube) / page summary / query-answer / "highlights". |
| **`/crawl`** | Recursively discover and scrape every reachable page from a starting URL (sitemap + link traversal). Async job, delivered via polling, webhook, or WebSocket. |
| **`/map`** | Fast URL discovery for a whole site (sitemap + search index + prior crawls) without scraping content. Returns up to tens of thousands of URLs. |
| **`/search`** | Web search (optionally scraping full content of each result in the same call) across `web`, `news`, `images` sources, with category filters (github/research/pdf) and time filters. |
| **`/extract`** | Schema- or prompt-driven structured extraction across one or many URLs (supports wildcards like `example.com/*`); an LLM does the collation. Beta — not reliable for "get every item on a huge listing site" style queries. |
| **`/monitor`** (new, Jul 2026) | Always-on watch of search queries / pages; pings a webhook or email when new/changed content appears — "ping me the moment something new comes online." |
| **`/interact`** | Multi-step browser session on top of `/scrape` — click, fill forms, paginate, then extract. |
| **`/parse`** (new, May 2026) | Document parsing for PDFs/Word/spreadsheets up to 50MB. |

**API shape:** plain REST + JSON, bearer-token auth (`Authorization: Bearer fc-...`).
**SDKs:** official Python, Node/JS, Go, Ruby, PHP, .NET, plus a CLI and an MCP
server (so it can be wired directly into an agent's tool belt). Community SDKs
exist for other languages.

Notably, Firecrawl now supports **keyless usage** (no API key, no signup) for
`/scrape`, `/search`, and `/interact`, rate-limited per IP — useful for
prototyping calls before committing to an account, but you'd want a real API
key for anything production-shaped (per-team credit tracking, higher limits).

---

## 2. Free Tier Specifics

| Attribute | Free plan |
|---|---|
| Credits/month | **1,000**, refreshed every billing period — **do not roll over** (unused credits are lost) |
| Cost | $0, **no credit card required** |
| Concurrency | 2 concurrent requests |
| Rate limits | Described as "low"; documented per-minute caps: `/scrape` 10, `/map` 10, `/search` 5, `/extract` 10, **`/crawl` 1 req/min** (crawl is a job-submission endpoint, so this mostly limits how many crawl *jobs* you can kick off, not pages/min within a job) |
| Feature gating | No features are hard-blocked on free — markdown, JSON extraction, screenshots, actions/interactions, stealth/enhanced proxy, PDF parsing, etc. are all *available* on free. The limiter is credits, not plan tier. |
| Job result retention | Crawl/extract job output is retrievable via API for **24 hours**; after that it's only visible in dashboard activity logs — persist output to your own storage immediately |

**Credit system** — it is *not* flat "1 page = 1 credit" once you touch anything
beyond plain markdown/HTML. Baseline is 1 credit/page for `/scrape`, `/crawl`,
and `/map` (map is 1 credit *per request*, regardless of how many URLs it
returns — cheapest endpoint by far). On top of that:

| Add-on | Extra cost |
|---|---|
| JSON/schema extraction format | +4 credits/page (5 total) |
| Question / Highlights formats | +4 credits each |
| Enhanced ("stealth") proxy | +4 credits (5 total: `basic`=1, `enhanced`=5, `auto`=escalates only if needed) |
| PII auto-redaction | +4 credits |
| Audio/video extraction | +4 credits |
| PDF parsing | +1 credit/page |
| Zero Data Retention (ZDR) | +1 credit |
| `/search` | 2 credits per 10 results (5x cheaper than pre-Oct-2025 pricing); scraping the results adds normal per-page cost on top |
| `/extract` | As of Nov 2025, billed on a **unified token-credit system**: 15 tokens = 1 credit, so cost scales with page size/complexity rather than a flat per-page fee |
| `/monitor` | 1 credit per page per check |

Third-party reviews (e.g. costbench.com) claim free-tier accounts may show
Firecrawl branding/watermarks on certain outputs and have community-only
support — worth assuming for planning, though not something the primary docs
dwell on. JS rendering itself is **not** a paid-only feature — it's handled
automatically on every scrape at the base 1-credit rate.

---

## 3. Signup Requirements

Signing up (not performed — described only):

1. Go to firecrawl.dev signup — email + password, or "Continue with Google" /
   "Continue with GitHub" OAuth.
2. Accept Terms of Service / Privacy Policy.
3. **No credit card requested anywhere in the free-plan flow.**
4. After signup, generate an API key from the dashboard at
   `firecrawl.dev/app/api-keys` (key format `fc-...`). Multiple keys per team
   are supported; rate limits are enforced **per team**, so all keys on one
   account share the same credit/rate-limit pool.

There's also a documented **keyless path** (no signup at all) for quick
`/scrape`, `/search`, `/interact` calls via the official CLI/SDK/MCP client,
capped per-IP per-day on both request count and credit usage — fine for a
one-off test, not something to architect a pipeline around.

---

## 4. Best-Fit Use Cases for Crypto Data (1,000-page budget)

Checked each candidate category for "does a free API/RSS already exist" before
recommending Firecrawl spend on it — spending scrape budget where a free API
already exists is the single biggest way to waste this allowance.

### Good targets (no free API — worth spending credits)

- **VC / "smart money" portfolio pages.** a16z crypto's portfolio
  (`a16zcrypto.com/portfolio/`) and investment list (`a16z.com/investment-list/`,
  described by a16z itself as "updated monthly"), plus Paradigm, Multicoin
  Capital, Dragonfly, Pantera, Coinbase Ventures portfolio pages — these are
  plain web pages with **no public API**. Slow-changing (monthly-ish), so cheap
  to track: scrape/re-diff periodically to build a "which VCs are backing which
  token" signal.
- **Token unlock / vesting calendars.** Confirmed that DefiLlama — despite
  having an extensive **free** API — gates its emissions/unlock-schedule
  endpoints behind a **paid Pro API key**. CryptoRank and CoinMarketCap's
  token-unlock pages are similarly not exposed via free API. This is a strong
  Firecrawl candidate: scrape the overview/calendar pages plus individual
  project vesting pages for tokens you're actively tracking.
- **Exchange listing-announcement pages.** No official free API or RSS
  confirmed for Binance's announcement page (`binance.com/en/support/announcement`)
  — Binance Developer Community threads explicitly note there's no official
  endpoint/WebSocket for this. Same likely applies to Coinbase's asset listing
  blog, Upbit/OKX notices. Good `/monitor` candidate (cheap: 1 credit/check) to
  catch listing announcements — a classic short-term price-moving signal.
- **Project docs / whitepaper sites.** Many smaller/mid-cap protocols publish
  docs on GitBook/Notion/Mintlify with no API. `/map` a docs site for ~1 credit
  to see its shape, then `/crawl` selectively (not the whole thing) to build a
  tokenomics/roadmap knowledge base for classification.

### Bad targets — skip, use the free API/RSS instead

- **SEC press releases / litigation releases.** Confirmed the SEC publishes
  official RSS feeds for Press Releases, Litigation Releases, Administrative
  Proceedings, and Trading Suspensions (`sec.gov/about/rss-feeds`). No need to
  spend Firecrawl credits here.
- **CFTC press releases / enforcement actions.** Same — CFTC has RSS feeds for
  both general and enforcement press releases (`cftc.gov/RSS/index.htm`).
- **Major crypto news outlets** (CoinDesk, The Block, Decrypt) generally
  expose RSS. Reserve Firecrawl only for the long-tail of niche blogs/company
  blogs/Substacks that genuinely lack a feed — verify per-site before spending
  credits, since many "no API" assumptions turn out wrong on inspection.

---

## 5. Budget Math

Three illustrative patterns against the 1,000-credit/month cap:

**Pattern A — naive broad crawl (anti-pattern, for contrast).** Weekly crawl of
5 general crypto news sites at 50 pages each = 250 pages/week × 4 weeks =
**1,000 pages/month**, i.e. the entire budget on content that's mostly
available via RSS elsewhere. Illustrates why an unscoped crawl schedule burns
the whole allowance on low-marginal-value data.

**Pattern B — steady-state monitoring (recommended shape).** Mix of cheap,
high-signal, infrequent checks:
- 15 VC portfolio pages, re-scraped every 2 weeks → 15 × 2 = 30 pages/month
- 6 token-unlock aggregator/calendar pages, scraped weekly → 6 × 4 = 24
- 20 individual project unlock-schedule pages, scraped monthly (rotating
  through active watchlist) → 20
- 5 exchange announcement pages via `/monitor`, checked daily at 1 credit/check
  → 5 × 30 = 150
- Subtotal: ~224 credits/month, leaving ~776 for the rest of the budget.

**Pattern C — event-driven deep dives.** Use `/map` (1 credit) to scope a site
before committing, then spend a burst of 100–150 credits `/crawl`-ing one
protocol's full docs site right after a funding round or major announcement
(reconnaissance-then-commit keeps you from crawling sites that turn out to be
1 relevant page deep in a 500-page docs tree).

---

## 6. Recent Changes, Gotchas, Long-Term-Reliance Notes

- **v1 → v2 migration (Aug 2025):** new API version with different defaults
  and smarter crawling; if any tutorial/example code references v1 endpoints,
  it's stale.
- **Unified credit/token billing (Nov 2025):** credits and LLM tokens merged
  into one system, `15 tokens = 1 credit`. `/extract` cost now scales with
  content size/complexity rather than a flat per-page number — budget for it
  less predictably than plain `/scrape`.
- **Enhanced/"stealth" proxy repriced (May 2025):** now costs 5 credits per
  request (was bundled into standard pricing before). This is a real gotcha
  for a free-tier budget: hitting a handful of Cloudflare-protected pages with
  `proxy: "enhanced"` can burn 5x the credits you'd expect. Default to
  `proxy: "basic"` or `"auto"` and only force `"enhanced"` when a site is
  known to block the basic proxy.
- **`/search` got 5x cheaper (Oct 2025).**
- **v2.10 (May 2026):** new `/parse` endpoint for documents; "Lockdown Mode"
  (cache-only, no live fetch — useful for staying inside budget by serving
  from cache); Question/Highlights formats claiming up to 100x fewer tokens
  per call for targeted Q&A against a page.
- **v2.11 (Jun 2026):** "Firecrawl Research Index" (pre-indexed arXiv corpus,
  probably not relevant to crypto data); expanded keyless access; automatic
  PII redaction; a "deterministic JSON" format specifically aimed at making
  **repeat scrapes cheaper** (worth using for pages you re-check often, like
  unlock calendars).
- **`/monitor` launched Jul 1, 2026** — brand new at time of writing; useful
  primitive for this project (watch a fixed set of pages, pay only 1
  credit/check, get pushed a webhook instead of polling) but new enough that
  reliability/behavior over months is unproven — treat as experimental in any
  design that depends on it.
- **Credits do not roll over** — unused monthly credits are lost, so there's
  no benefit to under-spending "to save up."
- **`/crawl` defaults to `limit: 10,000` pages** — the single biggest way to
  accidentally blow the entire monthly budget in one call. Always pass an
  explicit low `limit` (e.g. 20–50) on this free tier.
- **Job results expire after 24 hours** — crawl/extract output must be pulled
  and persisted into your own storage immediately; don't rely on Firecrawl as
  a data store.
- Free-tier concurrency is capped at 2 and rate limits are "low" (crawl job
  submission itself is throttled to 1/min) — design the collector to be
  patient/sequential rather than assuming parallel throughput.

---

## 7. Recommended Usage Plan

Given the free 1,000-credit/month budget, allocate roughly as follows (not
rigid — leave slack for ad hoc research pulls):

| Category | Sources (examples) | Cadence | Est. credits/month |
|---|---|---|---|
| VC / smart-money portfolio tracking | a16z crypto (`a16zcrypto.com/portfolio/`, `a16z.com/investment-list/`), Paradigm, Multicoin, Dragonfly, Pantera, Coinbase Ventures — ~10-15 pages | Bi-weekly scrape | ~150 |
| Token unlock / vesting tracking | CryptoRank token-unlock overview, CoinMarketCap token-unlocks page, plus per-project vesting pages for active watchlist tokens | Overview weekly, per-project monthly | ~150 |
| Exchange listing announcements | Binance, Coinbase, Upbit, OKX announcement/notice pages | Daily via `/monitor` (1 credit/check × ~4-5 exchanges) | ~150 |
| Non-RSS regulatory pages (state regulators, foreign bodies — *not* SEC/CFTC, which have RSS) | Case-by-case, verified individually before committing | Weekly | ~50 |
| Project docs / whitepaper ingestion | `/map` first (cheap), then selective `/crawl` of 2–4 new/interesting protocols per month | Monthly, event-driven | ~250-300 |
| Buffer for ad hoc `/search` + one-off deep dives | — | As needed | ~200-250 |

This intentionally leaves the news-aggregation and general "crypto blog"
category **off the primary budget** — check each candidate site for an
existing RSS feed first (most legitimate crypto news outlets have one), and
only spend Firecrawl credits on the specific niche blogs/VC pages/unlock
calendars/listing pages confirmed to lack a free API. The `/map` endpoint
(1 credit regardless of site size) should be the default first move on any
new source to scope it before committing crawl budget.
