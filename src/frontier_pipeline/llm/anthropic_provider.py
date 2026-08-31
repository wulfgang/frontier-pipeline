from __future__ import annotations

import json
import re
from typing import Any

from anthropic import Anthropic


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        msg = self.client.messages.create(**kwargs)
        return "".join(b.text for b in msg.content if hasattr(b, "text"))

    def complete_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        text = self.complete(
            prompt + "\n\nRespond with a single JSON object only.",
            system=system,
        )
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("no JSON object in model response")
        return json.loads(match.group(0))
