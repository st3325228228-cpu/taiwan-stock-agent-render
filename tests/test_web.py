from pathlib import Path

import web


def test_index_serves_research_ui():
    client = web.app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert "台股 AI 研究助手" in response.get_data(as_text=True)
    assert "analysis-form" in response.get_data(as_text=True)


def test_analyze_api_still_returns_report(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STOCK_DATA_PROVIDER", "mock")
    monkeypatch.setenv("USE_LLM", "false")
    monkeypatch.setenv("STOCK_AGENT_DB", str(tmp_path / "agent.db"))
    client = web.app.test_client()

    response = client.post(
        "/analyze",
        json={"symbol": "2330", "question": "只看股價"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["bundle"]["symbol"] == "2330.TW"
    assert body["bundle"]["sections"]["price"]["status"] == "ok"
    assert "Important Notice" in body["report"]


def test_analyze_api_passes_key_only_to_current_request(monkeypatch):
    captured = {}

    class FakeResult:
        def to_dict(self):
            return {
                "report": "## Important Notice\nTest report",
                "bundle": {"symbol": "2330.TW", "sections": {}},
                "analysis_id": 7,
            }

    class FakeAgent:
        def analyze(self, request):
            captured["symbol"] = request.symbol
            return FakeResult()

    def fake_build_agent(api_key=""):
        captured["api_key"] = api_key
        return FakeAgent()

    monkeypatch.setattr(web, "build_agent", fake_build_agent)
    response = web.app.test_client().post(
        "/analyze",
        json={
            "symbol": "2330",
            "question": "只看股價",
            "openai_api_key": "request-only-key",
        },
    )

    assert response.status_code == 200
    assert captured == {"api_key": "request-only-key", "symbol": "2330"}
