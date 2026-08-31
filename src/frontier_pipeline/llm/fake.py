from __future__ import annotations

from typing import Any


class FakeLLMProvider:
    def __init__(
        self,
        text_responses: list[str] | None = None,
        json_responses: list[dict[str, Any]] | None = None,
    ) -> None:
        self._text = list(text_responses or ["fake-response"])
        self._json = list(json_responses or [{"ok": True}])

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        return self._text.pop(0) if len(self._text) > 1 else self._text[0]

    def complete_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        data = self._json.pop(0) if len(self._json) > 1 else self._json[0]
        return dict(data)
