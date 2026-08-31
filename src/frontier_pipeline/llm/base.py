from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    def complete(self, prompt: str, *, system: str | None = None) -> str: ...

    def complete_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]: ...
