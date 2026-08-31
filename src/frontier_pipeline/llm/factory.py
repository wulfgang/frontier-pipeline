from __future__ import annotations

import os
from typing import Any

from frontier_pipeline.llm.anthropic_provider import AnthropicProvider
from frontier_pipeline.llm.fake import FakeLLMProvider
from frontier_pipeline.llm.openai_compatible import (
    DEFAULT_DASHSCOPE_BASE_URL,
    DEFAULT_DASHSCOPE_MODEL,
    OpenAICompatibleProvider,
)

_DASHSCOPE_ALIASES = {"dashscope", "alibaba", "qwen", "openai"}


def get_provider(name: str | None = None) -> Any:
    chosen = (name or os.getenv("FRONTIER_LLM_PROVIDER") or "dashscope").lower()
    if chosen == "fake":
        return FakeLLMProvider()
    if chosen == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for anthropic provider")
        return AnthropicProvider(api_key=key)
    if chosen in _DASHSCOPE_ALIASES:
        key = (
            os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        if not key:
            raise RuntimeError(
                "DASHSCOPE_API_KEY (or API_KEY) is required for dashscope provider"
            )
        base_url = (
            os.getenv("FRONTIER_LLM_BASE_URL")
            or os.getenv("BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or DEFAULT_DASHSCOPE_BASE_URL
        )
        model = os.getenv("FRONTIER_LLM_MODEL") or DEFAULT_DASHSCOPE_MODEL
        return OpenAICompatibleProvider(api_key=key, base_url=base_url, model=model)
    raise RuntimeError(f"unknown provider: {chosen}")
