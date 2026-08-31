from pathlib import Path

from frontier_pipeline.env import load_dotenv


def test_load_dotenv_does_not_override_existing(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DASHSCOPE_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "from-env")
    load_dotenv(env_file)
    assert __import__("os").environ["DASHSCOPE_API_KEY"] == "from-env"


def test_load_dotenv_sets_missing(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FRONTIER_LLM_MODEL=qwen-plus\n", encoding="utf-8")
    monkeypatch.delenv("FRONTIER_LLM_MODEL", raising=False)
    load_dotenv(env_file)
    assert __import__("os").environ["FRONTIER_LLM_MODEL"] == "qwen-plus"
