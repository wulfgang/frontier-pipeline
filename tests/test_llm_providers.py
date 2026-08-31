import httpx

from frontier_pipeline.llm.fake import FakeLLMProvider
from frontier_pipeline.llm.factory import get_provider
from frontier_pipeline.llm.openai_compatible import OpenAICompatibleProvider


def test_fake_complete_json():
    fake = FakeLLMProvider(json_responses=[{"ok": True}])
    assert fake.complete_json("hi") == {"ok": True}


def test_factory_defaults_to_fake_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("FRONTIER_LLM_PROVIDER", "fake")
    provider = get_provider()
    assert provider.complete("x") == "fake-response"


def test_factory_dashscope_uses_env(monkeypatch):
    monkeypatch.setenv("FRONTIER_LLM_PROVIDER", "dashscope")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setenv(
        "FRONTIER_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    monkeypatch.setenv("FRONTIER_LLM_MODEL", "qwen-plus")
    provider = get_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.api_key == "sk-test"
    assert provider.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert provider.model == "qwen-plus"


def test_openai_compatible_complete_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer sk-test"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": '{"ok": true}'}}
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        api_key="sk-test",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        client=client,
    )
    assert provider.complete_json("hi") == {"ok": True}


def test_factory_dashscope_requires_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("FRONTIER_LLM_PROVIDER", "dashscope")
    try:
        get_provider()
    except RuntimeError as exc:
        assert "DASHSCOPE_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
