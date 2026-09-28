import sys
import types

from app.llm import LLMAnalyzer


def test_explicit_empty_key_does_not_fall_back_to_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "server-side-key-that-must-not-be-used")

    analyzer = LLMAnalyzer(enabled=True, api_key="")

    assert analyzer._get_client() is None


def test_explicit_key_is_passed_to_openai_client(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeOpenAI))
    analyzer = LLMAnalyzer(
        enabled=True,
        api_key="request-only-key",
        api_base="https://example.test/v1",
    )

    assert analyzer._get_client() is not None
    assert captured == {
        "api_key": "request-only-key",
        "base_url": "https://example.test/v1",
    }
