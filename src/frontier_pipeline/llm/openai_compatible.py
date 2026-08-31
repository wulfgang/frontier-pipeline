from __future__ import annotations

import json
import re
from typing import Any

import httpx

from frontier_pipeline.http_util import request_with_retries

DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_DASHSCOPE_MODEL = "qwen-plus"


class OpenAICompatibleProvider:
    """Chat Completions client for OpenAI-compatible APIs (DashScope, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_DASHSCOPE_BASE_URL,
        model: str = DEFAULT_DASHSCOPE_MODEL,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = client

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        owns_client = self._client is None
        client = self._client or httpx.Client(timeout=httpx.Timeout(120.0))
        try:
            response = request_with_retries(
                client, "POST", url, headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if owns_client:
                client.close()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("unexpected chat completions response") from exc
        if not isinstance(content, str):
            raise ValueError("chat completions content is not a string")
        return content

    def complete_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        text = self.complete(
            prompt + "\n\nRespond with a single JSON object only.",
            system=system,
        )
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("no JSON object in model response")
        return json.loads(match.group(0))
