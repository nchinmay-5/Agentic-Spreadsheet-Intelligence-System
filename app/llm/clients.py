"""Minimal HTTP clients; deterministic tools remain the source of truth."""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


class ModelRouter:
    def complete(self, prompt: str) -> str | None:
        return self._local(prompt) or self._online(prompt)

    def _local(self, prompt: str) -> str | None:
        url = os.getenv("LOCAL_LLM_URL")
        return _post_json(url, {"prompt": prompt}).get("text") if url else None

    def _online(self, prompt: str) -> str | None:
        url, key = os.getenv("ONLINE_LLM_URL"), os.getenv("ONLINE_LLM_API_KEY")
        return _post_json(url, {"prompt": prompt}, {"Authorization": f"Bearer {key}"}).get("text") if url and key else None


def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    request = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    with urlopen(request, timeout=15) as response:  # nosec - explicit environment configuration
        return json.loads(response.read())
