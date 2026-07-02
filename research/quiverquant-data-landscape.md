# QuiverQuant-Style Alt-Data Landscape — Free Crypto Equivalents

**Status:** research only. No accounts created, no scraping performed, no code written.
**Scope:** for each QuiverQuant signal category, identify the closest FREE, crypto-native
data source(s), with concrete tier limits, auth requirements, format, and integration effort.

**How to read the effort rating:**
- **Trivial** — plain REST/GraphQL JSON endpoint, no key or free key via self-serve signup, stable schema.
- **Light SDK** — official client library (Python/JS) recommended but a bare HTTP client would also work.
- **Scraping (Firecrawl-class)** — no API; needs HTML scraping or a Twitter/X feed reader. Candidate for the
  project's Firecrawl free tier (1,000 pages/month) per the project README.
- **Heavy** — requires SQL/query-engine literacy (Dune/Flipside), a paid key for meaningful depth, or
  building your own aggregation/indexing layer.

---

## 1. "Insider" / Smart Money Tracking → Whale Wallets, VC/Fund Wallets, Exchange Flows

QuiverQuant's congressional/insider trading feed maps to on-chain wallet labeling and large-transaction
monitoring in crypto — the closest thing to "who's buying/selling before the news."

### Arkham Intelligence (Ultra API)
- URL: https://info.arkm.com/research (product), API portal at `arkm.com/api` (returned 403 to
  automated fetch — likely requires a logged-in session to view docs; product exists and is documented
  in third-party writeups).
- Free tier: yes — free individual signup gives wallet tagging, entity clustering (e.g. "a16z", "Lazarus
  Group", exchange treasuries), multi-chain coverage (BTC, ETH, SOL, AVAX, TRON, etc.), a fund-flow
  "Tracer," and free custom alerts. 3M+ registered users as of early 2026.
- API access: exists (Ultra engine, programmatic), but pricing/quota for API keys specifically was not
  confirmed from public docs — likely gated behind a request/paid tier for high-volume programmatic pulls,
  while the web UI + alerts are free.
- Auth: free account signup (email).
- Format: web UI primary; API JSON, exact rate limits undocumented publicly.
- Maps to: insider/entity-labeled wallet tracking (closest crypto analog to "who is this wallet").
- Integration effort: **Light SDK / possibly scraping** for the UI-only parts; API needs a follow-up
  signup + doc read before committing (do not do this yet per research-only phase).

### Whale Alert
- URL: https://whale-alert.io/ (product), https://developer.whale-alert.io/documentation/ (API docs).
- Free tier: **no free tier for the API.** Alerts API (WebSocket) is $29.95/mo (personal), Enterprise
  REST API is $699/mo. Only a 7-day free trial exists for the Alerts API.
- **But**: the public **X/Twitter account [@whale_alert](https://x.com/whale_alert)** posts the same
  large-transaction alerts (100+ BTC, 1,000+ ETH, 10,000+ USDT thresholds) completely free, and Whale
  Alert has released a **free downloadable archive of all historical Twitter/X alerts** for research use.
  Telegram channel (`t.me/s/whale_alert_io`) mirrors the same feed and is scrapeable without any API.
- Auth: none for Twitter/Telegram feed; API key + paid subscription for the real API.
- Format: tweets/Telegram messages (unstructured text, regex-parseable) for free tier; JSON for paid API.
- Maps to: large single-transaction whale alerts (a narrower, real-time-alert version of insider tracking).
- Integration effort: **Scraping (Firecrawl-class)** for Twitter/Telegram feed parsing; **Heavy/paid**
  for the real API.

### Nansen
- URL: https://nansen.ai/api, docs at https://docs.nansen.ai/, pricing at
  https://docs.nansen.ai/getting-started/credits.
- Free tier: **2,000 one-time starter API credits** + a **daily refresh of 10 credits** (never fully
  stuck at zero), but free-tier calls consume **10× more credits per call** than paid plans, so the
  free allotment goes fast. Web app free tier gives basic Wallet Profiler / Token God Mode without
  Smart Money sub-label breakdowns.
- Paid: Pro plan $49–69/mo includes 2,000 credits/month at 1x cost; API credits otherwise $10/1,000.
- Auth: API key via signup.
- Format: REST JSON (`api.nansen.ai`), endpoints for Smart Money, Wallet Profiler, Token Screener,
  exchange flows.
- Maps to: "Smart Money" labeled wallets (~12 behavioral labels: Smart Trader, Smart LP, Fund, etc.) —
  this is the single closest crypto analog to QuiverQuant's "smart money"/insider concept.
- Integration effort: **Trivial** to wire up, but the 10x-credit-cost free tier means very limited
  practical call volume (a few hundred calls before exhausting the daily 10-credit trickle) — usable for
  prototyping, not sustained polling.

### Etherscan (+ multichain via Etherscan V2 API)
- URL: https://docs.etherscan.io/
- Free tier: **5 calls/sec, 100,000 calls/day** per key, and a single V2 key now works across all
  Etherscan-family chains (Ethereum, BSC via BscScan, Polygon, Arbitrum, etc. — the 5 req/s cap is
  shared across chains).
- Auth: free API key via signup.
- Format: REST JSON.
- Maps to: raw address transaction history, token transfers, contract verification — the substrate
  labeling layers like Arkham/Nansen are built on. Etherscan also exposes some address name-tags in its
  UI (not fully exposed via free API, but useful for cross-referencing known exchange/fund addresses).
- Integration effort: **Trivial** — this should be a base-layer data source regardless of category.

### Blockchair (multi-chain explorer API)
- URL: https://blockchair.com/api, docs at https://blockchair.com/api/docs.
- Free tier: **1,000 calls/day, no API key required** (IP-based); covers 41 blockchains including
  Bitcoin, which Etherscan-family APIs don't reach.
- Auth: none for free tier.
- Format: REST JSON.
- Maps to: cross-chain whale/large-transaction lookups, especially for Bitcoin (Etherscan doesn't cover
  BTC).
- Integration effort: **Trivial**.

### DeBank
- URL: https://debank.com/ (product), https://docs.cloud.debank.com/ (Cloud API).
- Free tier: the consumer web app is fully free (search any wallet, no login required) for portfolio/DeFi
  position lookups across EVM chains. The **API (DeBank Cloud)** is paid-only in practice — no clear free
  API tier found; Pro plan referenced at up to 100 req/s (paid).
- Auth: free for web lookups; API key + payment for programmatic Cloud API.
- Format: REST JSON (API); HTML (web app).
- Maps to: wallet-level DeFi position aggregation — useful for manually verifying a labeled whale's
  current exposure.
- Integration effort: **Scraping (Firecrawl-class)** if avoiding the paid API, since the web UI is
  publicly viewable per-address without login.

### Lookonchain
- URL: https://www.lookonchain.com/ ; primarily active as **X account [@lookonchain](https://x.com/lookonchain)** (700K+ followers).
- Free tier: the X feed itself (curated, analyst-written whale/smart-money flow call-outs) is entirely
  free. Their own site has Standard ($29/mo, track 50 wallets) and Pro ($199/mo, API access + exports)
  tiers, but **no API on the free tier**.
- Auth: none for X feed.
- Format: unstructured text/images (tweets).
- Maps to: curated, human-analyzed whale-move narrative — high signal-to-noise but not machine-native.
- Integration effort: **Scraping (Firecrawl-class)** of the X feed (or an RSS/Nitter-style mirror).

---

## 2. Sentiment (WallStreetBets-equivalent) → Crypto Social Sentiment

### LunarCrush
- URL: https://lunarcrush.com/, API docs https://lunarcrush.com/developers/api/overview.
- Free tier: the **consumer web app free tier does NOT include API access** — free web users get basic
  Discover/market data only, no social API. Real API access (real-time social sentiment, creator
  metrics, Galaxy Score, AltRank across 4,000+ coins) requires a paid Individual/Builder plan.
- Workaround: an **unofficial community Python wrapper (`LunarCrushAPI` on GitHub, github.com/saizk/LunarCrushAPI)**
  wraps the older **LunarCrush v2 API, which needs no API key** — this is the most promising free path
  but is unofficial/unsupported and could break or be shut off at any time.
- Auth: none for the unofficial v2 route; paid key for official v4.
- Format: REST JSON.
- Maps to: closest 1:1 analog to WSB sentiment scoring in crypto (Galaxy Score/AltRank are explicitly
  designed as "social momentum" trading signals).
- Integration effort: **Light SDK** via the unofficial wrapper (higher risk), or **Heavy/paid** for the
  official, supported API.

### Santiment
- URL: https://api.santiment.net/, pricing at https://app.santiment.net/pricing.
- Free tier: a free Sanbase plan exists with **basic social volume / sentiment metrics but delayed and
  rate-limited data**; real-time, unrestricted API access requires "Sanbase Max" (paid, from $49/mo,
  14-day trial). Free plan is enough for periodic (non-real-time) polling.
- Auth: API key via free signup (GraphQL API, `sanpy` official Python client on GitHub).
- Format: GraphQL JSON.
- Maps to: social volume (mention counts), crowd sentiment (bullish/bearish parsed from 3M+ messages/
  month across crypto channels), and — notably — **developer activity metrics** (see Category 5) all
  from one source.
- Integration effort: **Light SDK** (`sanpy`), free tier usable for a daily/periodic pull.

### CryptoPanic
- URL: https://cryptopanic.com/developers/api/
- Free tier: yes — free API auth token gives access to the news feed with community **sentiment votes**
  (bullish/bearish/important/toxic → aggregated "Panic Score," 0–100 sentiment index with 5-level labels:
  Extremely Bullish → Extremely Bearish). Filterable by currency and by vote type. Pro tier ($9/mo) adds
  RSS/Atom customization, instant push alerts, and extended metadata — free tier is functional without it.
- Auth: free signup for an API token.
- Format: REST JSON.
- Maps to: a lightweight, purpose-built crypto sentiment index — arguably the single best "plug and play"
  sentiment source in this whole survey.
- Integration effort: **Trivial**.

### Alternative.me Crypto Fear & Greed Index
- URL: https://alternative.me/crypto/fear-and-greed-index/ ; API at https://alternative.me/crypto/api/.
- Free tier: **fully free, no API key, no rate limit documented**; aggregates 5 underlying sources
  (volatility, momentum/volume, social media, dominance, trends) into one daily 0–100 index.
- Auth: none.
- Format: REST JSON (`?limit=N`, `limit=0` for full history).
- Maps to: a blunt, market-wide sentiment gauge (not per-asset) — good as a macro overlay signal, not a
  per-coin replacement for LunarCrush/Santiment.
- Integration effort: **Trivial**. Commercial use allowed with attribution.

### Reddit API (r/CryptoCurrency, r/Bitcoin, etc.)
- URL: https://support.reddithelp.com/hc/en-us/articles/16160319875092
- Free tier: **100 requests/min (OAuth)**, 10 req/min unauthenticated; full access to public posts/
  comments/subreddits, but capped at ~1,000 posts/subreddit reachable and **no historical backfill**
  beyond that window on the free tier. Non-commercial use only — commercial use needs a paid agreement.
- Auth: free OAuth app registration.
- Format: REST JSON (or via PRAW Python wrapper).
- Maps to: direct crypto-community sentiment/attention, the truest crypto analog of r/WallStreetBets.
- Integration effort: **Light SDK** (PRAW), watch the non-commercial ToS restriction if this project is
  ever monetized.

### X (Twitter) API
- Free tier: **effectively dead for this use case in 2026** — ~1 read/15min, no search access, 1,500
  posts/month posting cap on the nominal free tier. Meaningful search access requires a paid tier
  ($200+/mo for Basic search).
- Verdict: **not viable as a free source.** Use curated accounts (@whale_alert, @lookonchain, key crypto
  KOLs) via scraping/RSS mirrors instead of the official API.
- Integration effort: **N/A (paid only)** for API; **Scraping** for specific accounts if needed.

### Google Trends (pytrends)
- URL: unofficial library https://github.com/GeneralMills/pytrends (1.2M+ downloads); official Google
  Trends API launched in 2025 but is **alpha, limited endpoints/quotas**.
- Free tier: pytrends is free but **unofficial** (queries the public Trends website, no key); throttles
  aggressively per (cookie, IP) — practical guidance is ~60s sleep between requests once rate-limited.
- Auth: none.
- Format: JSON via pytrends wrapper.
- Maps to: retail search-interest spikes for coin names/tickers — a leading indicator often used
  alongside social sentiment.
- Integration effort: **Light SDK**, but fragile/unofficial (Google can break it without notice); the
  new official alpha API is worth revisiting once it matures.

---

## 3. On-Chain Fundamentals (no equities equivalent — core to crypto alt-data)

### DefiLlama
- URL: https://api-docs.defillama.com/
- Free tier: **fully free, no API key, effectively no rate limit** for normal use (contact maintainers
  only if doing very heavy/sustained polling). TVL by protocol/chain, stablecoin supply, DEX/perp
  volumes, yields, prices, and — notably — a free **token unlock/vesting calendar** (defillama.com/unlocks).
  Pro tier ($300/mo) adds extra endpoints/support, not gated core data.
- Auth: none.
- Format: REST JSON.
- Maps to: protocol-level "fundamentals" (assets under management, capital flows) — the best free,
  zero-friction source in this entire survey.
- Integration effort: **Trivial**. Should be a foundational/first-built collector.

### Dune Analytics
- URL: https://dune.com/, API docs https://docs.dune.com/
- Free tier: **2,500 credits/month included**, and — per Dune's 2025/2026 pricing overhaul — the free
  plan **does include API access** (10 private queries, 1 private dashboard, CSV export, JSON query
  results via API, with a 250,000-datapoint safety cap per call). Overage beyond 2,500 credits is
  $5/100 credits. (Note: some older articles claim "no API on free tier" — that reflects pre-2025
  pricing; Dune's own blog post ["A New Chapter for Web3 Data"](https://dune.com/blog/new-paid-experience)
  confirms free-tier API access as of the rewrite.)
- Auth: free account + API key.
- Format: SQL query engine over decoded on-chain data; results as JSON/CSV via API.
- Maps to: the single most flexible free on-chain query layer — thousands of community dashboards
  already replicate paid analytics (e.g., CryptoQuant-style exchange netflow) that can be forked/queried
  directly instead of rebuilt.
- Integration effort: **Heavy** — requires SQL literacy and picking/adapting existing community queries,
  but pays off with the broadest coverage of any source here.

### The Graph (Subgraph Studio)
- URL: https://thegraph.com/docs/en/subgraphs/querying/introduction/
- Free tier: **100,000 queries/month, no credit card required**; overage is $4/100K queries or payable
  in GRT on Arbitrum.
- Auth: free API key.
- Format: GraphQL.
- Maps to: protocol-specific indexed data (DEX trades, lending positions, NFT activity) via existing
  public subgraphs — complements Dune for cases where a maintained subgraph already exists for the
  target protocol.
- Integration effort: **Light SDK** — trivial once a relevant existing subgraph is identified; building
  a custom subgraph is heavier.

### Etherscan / Blockchair
- Covered in Category 1 (address/transaction data underlies fundamentals too — gas usage, active
  addresses, contract calls). Same free tiers apply (5 req/s & 100K/day; 1,000/day respectively).

### Glassnode
- URL: https://docs.glassnode.com/
- Free tier: **no free API** — API access is an add-on exclusive to the Professional plan ($79+/mo).
  Free (Standard) web-tier users get daily-resolution, delayed metrics in the UI only, not via API.
- Auth: paid API key only.
- Verdict: **not usable in a free-only build** — note for future paid consideration, but out of scope now.
- Integration effort: **N/A (paid only)**; UI-only free tier would require scraping and violates
  reasonable ToS expectations for a paid-data product — not recommended.

### CryptoQuant
- URL: https://cryptoquant.com/docs, pricing at https://cryptoquant.com/pricing.
- Free tier: has a free "Basic" web plan, but **API access requires a paid tier** (Advanced $29/mo+).
  Free web dashboards exist for headline metrics (e.g., BTC exchange netflow) but aren't API-accessible.
- Auth: paid API key for programmatic access.
- Verdict: largely **not usable free via API**; however, many of CryptoQuant's flagship metrics
  (exchange in/outflow, netflow) have been **replicated by the community as public Dune dashboards**,
  which are free to query — this is the practical workaround.
- Integration effort: **N/A (paid) direct**; **Heavy** via Dune replication.

### Flipside Crypto
- URL: https://flipsidecrypto.xyz/, docs https://docs.flipsidecrypto.xyz/
- Free tier: historically **fully free** SQL-query platform + API/SDKs across 20+ chains, comparable to
  Dune. **Caveat found during research:** search results indicate Flipside's blockchain-data business was
  sold/transitioned (references to "SonarX" and a "Flipside platform available through June 17, 2026")
  — this needs a fresh check before relying on it, as the free-data product's future is uncertain as of
  this writing.
- Integration effort: **Heavy** (SQL-based, same profile as Dune) — deprioritize until platform status
  is confirmed.

---

## 4. Lobbying / Gov Contracts Equivalent → Crypto Regulatory Tracking

### SEC EDGAR Full-Text Search
- URL: https://www.sec.gov/edgar/search/ (UI), full-text search API surfaced via EDGAR's public search
  backend; third-party wrappers like sec-api.io exist but are paid convenience layers over the same free
  government data.
- Free tier: **fully free, public, no key required.** Full-text search covers filings since 2001;
  filterable by keyword (e.g., "bitcoin," "digital asset," "crypto asset"), company, date, filing type.
  New filings searchable within ~60 seconds of publication.
- Auth: none.
- Format: JSON (EDGAR's search backend returns JSON; bulk filing documents are HTML/XML/XBRL).
- Maps to: filter for crypto-related 8-Ks, S-1s, and disclosures — the closest crypto analog to
  QuiverQuant's SEC-filing-based signals.
- Integration effort: **Trivial** REST calls against the public search endpoint, filtered by
  crypto-specific keywords.

### SEC Litigation Releases + Enforcement (Cyber and Emerging Technologies Unit)
- URL: https://www.sec.gov/enforcement-litigation/litigation-releases ;
  https://www.sec.gov/about/divisions-offices/division-enforcement/cyber-crypto-assets-emerging-technology ;
  RSS feeds index at https://www.sec.gov/about/rss-feeds.
- Free tier: fully free, official **RSS feed for Litigation Releases** — filter/grep for crypto-related
  entries (case names, tickers) after ingesting.
- Auth: none.
- Format: RSS/XML → HTML release pages.
- Maps to: direct crypto enforcement-action tracking (an early/negative signal — e.g., exchange or
  project X is being sued).
- Integration effort: **Trivial** (RSS parsing).

### CFTC Enforcement Actions
- URL: https://www.cftc.gov/LawRegulation/EnforcementActions/index.htm
- Free tier: public list of enforcement actions, free. No first-party API/RSS confirmed in research —
  the page itself is a browsable index of orders/opinions.
- Alternative: **OpenSanctions** (https://www.opensanctions.org/datasets/us_cftc_enforcement_actions/)
  republishes CFTC enforcement data in structured JSON with a queryable API, free for non-commercial
  research use.
- Auth: none for the raw CFTC pages; OpenSanctions API has its own free-tier terms (not fully verified
  here — check before integrating).
- Format: HTML (CFTC direct) or structured JSON (OpenSanctions).
- Maps to: derivatives-side crypto regulatory actions, complementing the SEC's securities-side actions.
- Integration effort: **Scraping (Firecrawl-class)** for CFTC direct; **Trivial** via OpenSanctions if
  its free tier proves adequate (needs a follow-up check).

---

## 5. Patents Equivalent → Developer Activity as a Health Proxy

### Electric Capital Crypto Ecosystems / Developer Report
- URL: https://github.com/electric-capital/crypto-ecosystems (taxonomy + data),
  https://www.developerreport.com/ (published annual report/dashboard).
- Free tier: **fully free, open source** (MIT for code, CC BY 4.0 for data). Maps ecosystems →
  sub-ecosystems → GitHub repos, and can regenerate the full repo list for any ecosystem at a point in
  time. Bulk data available as downloadable Parquet files (~100GB working set if pulling everything —
  scope down to relevant ecosystems).
- Auth: none.
- Format: Parquet / CSV / TOML taxonomy files via GitHub.
- Maps to: this is a **direct, purpose-built analog to a "patents" signal** — which projects have real,
  sustained developer activity vs. which are all-marketing.
- Integration effort: **Light SDK** — clone/pull the repo, parse the taxonomy, optionally cross-reference
  with GitHub API for live activity deltas.

### GitHub REST/GraphQL API
- URL: https://docs.github.com/en/rest
- Free tier: **5,000 requests/hour authenticated** (personal access token), 60/hour unauthenticated;
  1,000/hour for `GITHUB_TOKEN` in Actions context.
- Auth: free personal access token.
- Format: REST JSON or GraphQL.
- Maps to: commit frequency, contributor counts, star/fork velocity, release cadence per repo — the raw
  feed that Electric Capital's dataset is built from; use directly for real-time deltas on repos already
  identified via the Electric Capital taxonomy.
- Integration effort: **Trivial**.

---

## 6. Exchange Listing / Flow Data

### CoinGecko API
- URL: https://docs.coingecko.com/ ; pricing at https://www.coingecko.com/en/api/pricing.
- Free tier: **Demo plan — 100 (Reports differ: ~30/min typical, up to ~100/min quoted in some places)
  calls/min, 10,000 calls/month**, no credit card required. Covers historical data, on-chain DEX data,
  NFT floor data, "crypto treasuries," and categories endpoints on the free Demo plan. (Legacy "Public
  API" without a Demo key is far more restricted, ~5–15 calls/min.)
- Auth: free Demo API key via signup.
- Format: REST JSON.
- Maps to: exchange listings, market data, new-coin detection, category/sector classification.
- Integration effort: **Trivial**.

### CoinMarketCap API
- URL: https://coinmarketcap.com/api/
- Free tier: **Basic plan, free forever — 15,000 call credits/month, 30+ endpoints, 50 requests/min**;
  no historical data on this tier, personal-use only.
- Auth: free API key via signup.
- Format: REST JSON.
- Maps to: same category as CoinGecko — redundant coverage is useful for cross-validation /
  fallback when one provider rate-limits.
- Integration effort: **Trivial**.

### CCXT (library, not a data provider itself)
- URL: https://github.com/ccxt/ccxt ; docs https://docs.ccxt.com/
- Free tier: **fully free, open-source (MIT), unified API across 100+ exchanges.** Public endpoints
  (tickers, order books, trades, OHLCV) require no account/API key at all — only private endpoints
  (placing orders, balances) need exchange-issued keys, which are irrelevant for a read-only signal
  pipeline.
- Auth: none for public market data.
- Format: REST + WebSocket, normalized across exchanges (Python/JS/PHP/C#/Go/Java).
- Maps to: direct cross-exchange order-book/trade/volume data — the infrastructure layer for detecting
  unusual volume spikes, spread anomalies, or new-listing price action across many venues at once,
  without needing each exchange's own bespoke API.
- Integration effort: **Trivial to Light SDK** — this is the standard tool for the job, not a scrape target.

### DEX Screener
- URL: https://docs.dexscreener.com/api/reference
- Free tier: **no API key required**; 60 req/min for token-profile endpoints, 300 req/min for
  pair/pool endpoints.
- Auth: none.
- Format: REST JSON.
- Maps to: real-time DEX pair listings/liquidity — good for catching new-token listings and liquidity
  events that CEX-centric CoinGecko/CMC data lags on.
- Integration effort: **Trivial**.

### CoinGlass (funding rates / open interest / liquidations)
- URL: https://www.coinglass.com/, API at https://docs.coinglass.com/
- Free tier: mostly a **paid API** for programmatic access (tick-level L2/L3 order books, funding-rate
  OHLC history, OI-weighted funding, liquidation heatmaps); the **website itself is free to browse**
  (funding rates, open interest, liquidation data pages) without a key.
- Auth: paid API key for programmatic pulls; none for web browsing.
- Format: REST JSON (paid); HTML (free web pages).
- Maps to: derivatives positioning (funding rate extremes, OI buildups) — a strong leading indicator of
  crowded trades/liquidation cascades, no equities QuiverQuant analog but high-value for crypto.
- Integration effort: **Scraping (Firecrawl-class)** for free web data; **paid** for the real API.

---

## 7. Other Useful Free Sources Found During Research

| Source | What it gives | Free tier note |
|---|---|---|
| **Token Unlocks (DefiLlama /unlocks, CoinGecko highlights, CoinMarketCap /token-unlocks)** | Vesting/unlock calendars — supply-shock early warning | DefiLlama's is fully free/API-backed already (see Cat. 3); CoinGecko/CMC versions are web-only free pages, Messari has a dedicated paid Token Unlocks API |
| **OpenSanctions** (`opensanctions.org`) | Structured, queryable sanctions + regulatory enforcement data (incl. CFTC) | Free for non-commercial research; verify commercial terms before production use |
| **Messari API** | Asset profiles, some on-chain metrics, news | Free tier: 20 requests/min — usable for light polling, no credit card needed for basic key |
| **Etherscan/Blockchair address/label data** | Base layer for wallet attribution | Already covered in Cat. 1/3 — foundational, should be built first regardless of category |
| **Nitter / RSS mirrors of crypto X accounts** | Free-of-API access to @whale_alert, @lookonchain, and crypto KOLs | Requires scraping (public Nitter instances are unreliable/frequently down — flag as fragile) |

---

## Comparison Table

| Source | Category | Free Tier Limits | Auth | Format | Effort |
|---|---|---|---|---|---|
| Arkham Intelligence | Whale/entity labels | Free web UI + alerts; API quota unconfirmed | Free signup | Web/JSON | Light SDK |
| Whale Alert (Twitter/Telegram) | Whale alerts | Unlimited (public feed) | None | Text | Scraping |
| Whale Alert (API) | Whale alerts | None — paid only ($29.95+/mo) | API key (paid) | JSON/WS | N/A (paid) |
| Nansen | Smart money labels | 2,000 starter + 10/day credits, 10x cost | API key | JSON | Trivial (limited volume) |
| Etherscan (V2) | Wallet/tx data | 5 req/s, 100K/day | Free API key | JSON | Trivial |
| Blockchair | Multi-chain tx data | 1,000 calls/day | None | JSON | Trivial |
| DeBank | Wallet DeFi positions | Free web, no free API | None (web) | HTML/JSON | Scraping |
| Lookonchain | Curated whale narrative | Free (X feed only) | None | Text | Scraping |
| LunarCrush | Social sentiment score | Official: none free; unofficial v2 wrapper: free | None (unofficial) | JSON | Light SDK (risky) |
| Santiment | Social + dev + on-chain | Free plan, delayed/rate-limited | Free API key | GraphQL | Light SDK |
| CryptoPanic | News sentiment votes | Free tier functional | Free API token | JSON | Trivial |
| Alternative.me F&G Index | Market-wide sentiment | Free, no documented limit | None | JSON | Trivial |
| Reddit API | Community sentiment | 100 req/min (OAuth) | Free OAuth app | JSON | Light SDK |
| X (Twitter) API | Social/sentiment | Effectively none | Paid | JSON | N/A (paid) |
| Google Trends (pytrends) | Search interest | Free, throttled, unofficial | None | JSON | Light SDK (fragile) |
| DefiLlama | TVL/flows/unlocks | Free, no key, no meaningful limit | None | JSON | Trivial |
| Dune Analytics | On-chain SQL queries | 2,500 credits/mo incl. API | Free API key | SQL→JSON/CSV | Heavy |
| The Graph | Indexed protocol data | 100,000 queries/mo | Free API key | GraphQL | Light SDK |
| Glassnode | On-chain metrics | None (API paid-only) | Paid | JSON | N/A (paid) |
| CryptoQuant | Exchange flows | None (API paid-only) | Paid | JSON | N/A (paid); Heavy via Dune |
| Flipside Crypto | On-chain SQL queries | Historically free; status uncertain 2026 | Free API key | SQL→JSON | Heavy (verify status first) |
| SEC EDGAR Full-Text Search | Regulatory filings | Free, unlimited | None | JSON/HTML | Trivial |
| SEC Litigation Releases (RSS) | Enforcement actions | Free | None | RSS/XML | Trivial |
| CFTC Enforcement Actions | Enforcement actions | Free (page); OpenSanctions API terms TBD | None / TBD | HTML/JSON | Scraping / Trivial via OpenSanctions |
| Electric Capital crypto-ecosystems | Dev activity taxonomy | Free, open source | None | Parquet/CSV | Light SDK |
| GitHub API | Dev activity | 5,000 req/hr authenticated | Free PAT | JSON | Trivial |
| CoinGecko API | Market/exchange data | 10,000 calls/mo, ~30-100/min | Free Demo key | JSON | Trivial |
| CoinMarketCap API | Market/exchange data | 15,000 credits/mo, 50 req/min | Free API key | JSON | Trivial |
| CCXT | Cross-exchange order books/trades | Free, unlimited (public endpoints) | None | JSON/WS | Trivial/Light SDK |
| DEX Screener API | DEX pairs/liquidity | 60-300 req/min | None | JSON | Trivial |
| CoinGlass | Funding/OI/liquidations | Free web only; API paid | None (web) / paid (API) | HTML / JSON | Scraping / N/A (paid) |
| Messari API | Asset profiles/news | 20 req/min | Free API key | JSON | Trivial |

---

## Recommended Starting Set (prioritized: signal quality vs. integration effort)

Build collectors for these first — they're all trivial-to-light-effort, need no scraping, and together
cover five of the seven QuiverQuant-style categories:

1. **DefiLlama API** — zero-friction, zero-limit, covers TVL/flows/unlocks. Build this first; it's the
   foundation for on-chain fundamentals and doubles as the token-unlock (gov-contract-analog) signal.
2. **CCXT** — the infrastructure layer for exchange listing/flow data across 100+ exchanges, entirely
   free for public market data. Build second; everything downstream (volume anomalies, new listings)
   depends on it.
3. **Etherscan V2 API + Blockchair** — base-layer wallet/transaction data (5 req/s/100K-day and
   1,000/day respectively), needed to cross-reference every whale/insider signal.
4. **CryptoPanic API** — best plug-and-play sentiment signal (community-voted Panic Score), free tier
   is fully functional, trivial REST integration.
5. **Electric Capital crypto-ecosystems + GitHub API** — the direct "patents" analog; combine the
   free taxonomy dataset with live GitHub API polling for commit/contributor deltas on tracked repos.
6. **SEC EDGAR Full-Text Search + Litigation Releases RSS** — the direct "lobbying/gov contracts"
   analog; both are free, unlimited, official government data, filterable by crypto keywords.
7. **Whale Alert (X/Telegram feed, not the paid API)** — cheapest path to real-time large-transaction
   alerts; requires basic feed scraping/parsing but no paid API and no Firecrawl budget needed for a
   simple text feed.
8. **Nansen (free credit tier) + Dune Analytics (free 2,500 credits/mo)** — once the trivial sources are
   running, add these for genuine "smart money" wallet labels and flexible on-chain SQL querying
   (including community-built replicas of paid CryptoQuant exchange-netflow dashboards). Budget these
   last since free quotas are small (Nansen) or require SQL investment (Dune).

**Explicitly deprioritized / not free:** Glassnode (API is paid-only), CryptoQuant API (paid-only, but
reachable indirectly via Dune community dashboards), Whale Alert's own API, X/Twitter API, Lookonchain's
API tier, LunarCrush's official API (the unofficial v2 wrapper is a fallback, not a foundation to build
on), CoinGlass API. Flipside Crypto's free-data future is uncertain as of this research and should be
re-verified before any integration work.
