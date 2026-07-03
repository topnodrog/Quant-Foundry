# Crypto Domain Pack (`crypto`, v0.1.0)

Phase 2 of the crypto alt-data engine (see repo `PLAN.md` §4). An **external**
[Open Foundry](https://github.com/syzygyhack/open-foundry) domain pack that
models the 8 Phase 1 free-data collectors as one queryable ontology — the
UNIFY layer between the collectors and the (Phase 3) nautilus_trader strategy
engine.

It lives in this repo (not the Open Foundry monorepo) and is loaded at runtime
via `DOMAIN_PACKS_EXTRA_DIRS` so the platform clone stays pristine and our
ontology is versioned with our code. See `../../deploy/README.md` for how the
stack mounts it.

## Model

**Entities (nouns)** — the six slowly-changing objects from PLAN.md §4, plus
`Chain` (grouping key the on-chain collector needs):

| Object | Natural key | Populated from |
|--------|-------------|----------------|
| `Chain` | `key` (`"ethereum"`) | onchain, defillama |
| `Token` | `geckoId` / `contractAddress` / `symbol` | defillama, ccxt, whale_alert, nansen |
| `Protocol` | `slug` | defillama, github |
| `Wallet` | `address` | whale_alert, dune, nansen |
| `Exchange` | `exchangeKey` (`"binance"`) | ccxt |
| `Fund` | `name` | nansen; Firecrawl VC pages (later) |

**Signals (append-only facts)** — one type per collector `signal_type`, each
carrying `observedAt` / `tier` / `source` provenance:

| Object | Collector `signal_type` | Source module |
|--------|-------------------------|---------------|
| `PriceObservation` | `ticker_snapshot` | `ccxt_collector.py` |
| `TvlObservation` | `tvl_snapshot` | `defillama.py` |
| `UnlockEvent` | `token_unlock_schedule` | `defillama.py` |
| `WhaleTransfer` | `whale_transfer`, `dune_query_row` | `whale_alert.py`, `smart_money.py` |
| `Holding` | `smart_money_holding` | `smart_money.py` |
| `DevActivityObservation` | `repo_activity` | `dev_activity.py` |
| `RegulatoryFiling` | `fulltext_filing_match` + RSS | `sec_edgar.py` |
| `SentimentObservation` | `fear_greed_index`, `sentiment_post` | `fear_greed.py`, `cryptopanic.py` |
| `ChainMetric` | `chain_stats`, `chain_supply` | `onchain.py` |

**Links (graph edges)** — the traversal-worthy relationships (PLAN.md §4:
`Wallet→transferred_to→Wallet`, `Fund→holds→Token`, `Fund→backs→Protocol`),
plus `TokenOnChain` / `ProtocolOnChain` / `ExchangeListsToken` / `ProtocolToken`.
Reference-only FKs stay as indexed fields on the signal objects (the AML pack's
pattern); only relations we actually traverse in the AGE graph become links.

## Ingestion status

Open Foundry is action-oriented — objects are created through governed actions,
not generic CRUD. The migration bridge (`src/quiverquant/ontology/`, next
increment) dedupes an entity on its natural key, then calls the `Register*`
action if new, and appends signals via `Record*` actions.

| Action | Status |
|--------|--------|
| `RegisterChain/Token/Protocol/Wallet/Exchange/Fund` | authored |
| `RecordWhaleTransfer` (flagship, emits `crypto.whale.transfer` event) | authored |
| `RecordUnlockEvent`, `RecordTvlObservation` | authored |
| `RecordPrice/Holding/DevActivity/RegulatoryFiling/Sentiment/ChainMetric` | **pending** — identical single-`createObject` manifests, added as each collector is wired and integration-tested against the running stack |

The remaining recorders are deliberately not shipped as unvalidated YAML; they
follow the exact shape of `record-tvl-observation.yaml`.

## Roles

Flat ReBAC model (`permissions/crypto-roles.fga`), suited to public market data:

- `admin` — manages reference entities, full control
- `analyst` — human researcher: reads all, records signals
- `ingestor` — the migration-bridge service account: reads + records signals
- `viewer` — read-only

## Validating the schema

Requires the Open Foundry toolchain (Node ≥20, pnpm). From the platform clone,
the ODL CLI compiles/validates a pack's schema without a running stack:

```
pnpm --filter @openfoundry/odl build
node packages/odl/dist/cli/index.js validate \
  --pack C:/dev/api.quiverquant.com/ontology/crypto-pack
```

Full boot-time validation happens when the api-gateway loads the pack (see
deploy README). `GET /admin/packs` then reports `crypto` with 15 object types.
