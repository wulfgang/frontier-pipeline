import httpx
import pytest

from frontier_pipeline.http_util import request_with_retries


def test_request_with_retries_succeeds_after_429s():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="rate limited")
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = request_with_retries(client, "GET", "https://example.com/api")
    assert response.status_code == 200
    assert response.text == "ok"
    assert calls["n"] == 3


def test_request_with_retries_raises_when_all_attempts_429():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, text="rate limited")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        request_with_retries(client, "GET", "https://example.com/api", max_attempts=3)
