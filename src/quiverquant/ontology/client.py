"""Thin Open Foundry REST client for posting governed actions.

Open Foundry is action-oriented: objects are created/mutated by POSTing to
`/api/v1/actions/{Name}`, not via generic CRUD. This wraps that one call plus a
`dry_run` mode that records instead of sending.

Two behaviours matter for bulk ingestion:
  * Params are the request body directly (route-generator.ts: ``input = req.body``),
    and every declared param is sent — optional ones as explicit JSON ``null``,
    never omitted, because the CEL evaluator errors ("no such key") when a
    precondition/effect references an absent key.
  * The gateway rate-limits a principal (200/min by default), so the client
    paces itself (``min_interval``) and retries HTTP 429 honouring ``Retry-After``.

Config (env):
  OPENFOUNDRY_URL           base URL (default http://localhost:4000)
  OPENFOUNDRY_TOKEN         bearer token for the ingestor principal (OIDC)
  OPENFOUNDRY_MIN_INTERVAL  seconds between requests (default 0.34 -> ~176/min)
"""

from __future__ import annotations

import os
import time
from typing import Any

try:
    import requests
except ImportError:  # requests is a project dep; guard only so --dry-run works bare
    requests = None  # type: ignore

DEFAULT_URL = "http://localhost:4000"
DEFAULT_MIN_INTERVAL = 0.34  # ~176 req/min, safely under the 200/min principal cap


class OpenFoundryClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        dry_run: bool = False,
        timeout: int = 30,
        min_interval: float | None = None,
        max_retries: int = 5,
    ):
        self.base_url = (base_url or os.getenv("OPENFOUNDRY_URL", DEFAULT_URL)).rstrip("/")
        self.token = token or os.getenv("OPENFOUNDRY_TOKEN")
        self.dry_run = dry_run
        self.timeout = timeout
        self.min_interval = (
            min_interval
            if min_interval is not None
            else float(os.getenv("OPENFOUNDRY_MIN_INTERVAL", DEFAULT_MIN_INTERVAL))
        )
        self.max_retries = max_retries
        self._last_request = 0.0

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def call_action(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """POST /api/v1/actions/{name}. Params are the body directly; optional
        ones are sent as explicit ``null``. Paces under the rate limit and
        retries 429s. In dry_run, returns a rendered plan entry without network
        I/O. Raises on transport errors, exhausted retries, or an action-level
        failure (``data.success == false``)."""
        body = dict(params)  # send all declared params, Nones included as JSON null
        if self.dry_run:
            return {"dry_run": True, "action": name, "body": body}
        if requests is None:  # pragma: no cover - only if requests missing at runtime
            raise RuntimeError("requests is required for live ingestion")
        url = f"{self.base_url}/api/v1/actions/{name}"

        for attempt in range(self.max_retries + 1):
            self._throttle()
            resp = requests.post(url, json=body, headers=self._headers(), timeout=self.timeout)
            if resp.status_code == 429 and attempt < self.max_retries:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 30)
                time.sleep(delay)
                continue
            resp.raise_for_status()
            payload = resp.json() if resp.content else {}
            # The gateway returns HTTP 200 with {"data": {"success": bool, "errors": [...]}}
            # even for action-level failures — surface those as errors, not silent successes.
            data = payload.get("data", payload) if isinstance(payload, dict) else {}
            if isinstance(data, dict) and data.get("success") is False:
                raise RuntimeError(f"action {name} failed: {data.get('errors')}")
            return payload
        raise RuntimeError(f"action {name} still rate-limited after {self.max_retries} retries")
