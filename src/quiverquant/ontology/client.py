"""Thin Open Foundry REST client for posting governed actions.

Open Foundry is action-oriented: objects are created/mutated by POSTing to
`/api/v1/actions/{Name}`, not via generic CRUD. This wraps that one call plus a
`dry_run` mode that records instead of sending.

Config (env):
  OPENFOUNDRY_URL    base URL (default http://localhost:4000)
  OPENFOUNDRY_TOKEN  bearer token for the ingestor principal (OIDC)

The exact request body shape and auth handshake are confirmed against the
running stack in the deploy step; `ACTION_BODY_KEY` isolates the one assumption
(params nested under "params") so it is a one-line change if the stack differs.
"""

from __future__ import annotations

import os
from typing import Any

try:
    import requests
except ImportError:  # requests is a project dep; guard only so --dry-run works bare
    requests = None  # type: ignore

DEFAULT_URL = "http://localhost:4000"
ACTION_BODY_KEY = "params"  # POST body = {"params": {...}}; verified at deploy


class OpenFoundryClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        dry_run: bool = False,
        timeout: int = 30,
    ):
        self.base_url = (base_url or os.getenv("OPENFOUNDRY_URL", DEFAULT_URL)).rstrip("/")
        self.token = token or os.getenv("OPENFOUNDRY_TOKEN")
        self.dry_run = dry_run
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _prune(params: dict[str, Any]) -> dict[str, Any]:
        """Drop None-valued params so optional fields are omitted rather than
        sent as explicit nulls."""
        return {k: v for k, v in params.items() if v is not None}

    def call_action(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """POST /api/v1/actions/{name}. In dry_run, returns a rendered plan entry
        without any network I/O."""
        body = {ACTION_BODY_KEY: self._prune(params)}
        if self.dry_run:
            return {"dry_run": True, "action": name, "body": body}
        if requests is None:  # pragma: no cover - only if requests missing at runtime
            raise RuntimeError("requests is required for live ingestion")
        url = f"{self.base_url}/api/v1/actions/{name}"
        resp = requests.post(url, json=body, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json() if resp.content else {}
