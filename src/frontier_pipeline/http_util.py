from __future__ import annotations

import time
from typing import Any

import httpx

_RETRYABLE_STATUS = {429, 503}


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(2.0 ** (attempt - 1), 30.0)


def request_with_retries(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_attempts: int = 3,
    **kwargs: Any,
) -> httpx.Response:
    """Perform an HTTP request with retries on 429/503 and transport errors."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_response: httpx.Response | None = None
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            last_error = exc
            last_response = None
            if attempt >= max_attempts:
                raise
            time.sleep(min(2.0 ** (attempt - 1), 30.0))
            continue

        if response.status_code in _RETRYABLE_STATUS and attempt < max_attempts:
            last_response = response
            time.sleep(_retry_delay_seconds(response, attempt))
            continue

        if response.status_code in _RETRYABLE_STATUS:
            response.raise_for_status()

        return response

    if last_response is not None:
        last_response.raise_for_status()
    if last_error is not None:
        raise last_error
    raise RuntimeError("request_with_retries exhausted without response")
