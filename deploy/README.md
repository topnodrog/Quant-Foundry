# Standing up Open Foundry with the crypto pack

Phase 2 UNIFY layer (PLAN.md §4). Brings up the [Open Foundry](https://github.com/syzygyhack/open-foundry)
stack (PostgreSQL 17 + Apache AGE, OpenFGA, Keycloak, Redpanda, Redis, CEL
sidecar, api-gateway) with our external `crypto` domain pack
(`../ontology/crypto-pack`) mounted.

## Prerequisites

- **Docker Desktop for Windows** (WSL 2 backend). Confirm: `docker --version`,
  `docker compose version`.
- The Open Foundry platform clone at **`C:\dev\open-foundry`** (already cloned).
- A bash shell for `init-services.sh` — use WSL (`wsl`) or Git Bash. The script
  only calls `docker compose exec`, so it needs Docker on PATH (WSL integration
  provides this).

## Bring it up

From the **platform** deploy dir (`C:\dev\open-foundry\deploy`):

```powershell
cd C:\dev\open-foundry\deploy
Copy-Item .env.example .env            # first time only

# Append our crypto-pack settings (see ../api.quiverquant.com/deploy/crypto.env)
Get-Content C:\dev\api.quiverquant.com\deploy\crypto.env | Add-Content .env

docker compose up -d                   # pulls images, builds services (first run is slow)
```

Then initialise services (OpenFGA store, DB bootstrap) from a **bash** shell:

```bash
cd /mnt/c/dev/open-foundry/deploy      # WSL path; Git Bash: /c/dev/open-foundry/deploy
bash ./init-services.sh
```

## Verify the pack loaded

```bash
curl -s http://localhost:4000/admin/packs | jq '.packs[] | select(.name=="crypto")'
```

Expect `crypto` with `objectTypes: 15`, `linkTypes: 7`, `actionTypes: 9`,
`external: true`. Endpoints:

- GraphQL playground — http://localhost:4000/graphql
- REST — http://localhost:4000/api/v1/
- OpenAPI (for the Python client) — http://localhost:4000/api/v1/openapi.json

## Notes

- `DOMAIN_PACKS=core,crypto` deliberately excludes the bundled nhs-acute / aml /
  supply-chain packs, so their FHIR (`/fhir/*`) and FDP/CDM (`/api/v1/cdm/*`)
  facades are never mounted.
- Consent enforcement keys off action params typed as a consent-subject
  (default `Patient`). None of the crypto `Register*`/`Record*` actions take a
  `Patient`, so consent checks don't gate ingestion. If a future action needs a
  consent subject, set `CONSENT_SUBJECT_TYPES` in `.env` accordingly.
- Editing the pack? The mount is read-only and scanned at boot —
  `docker compose up -d api-gateway` reloads it.
- Tear down (keep data): `docker compose stop`. Wipe everything incl. volumes:
  `docker compose down -v`.
