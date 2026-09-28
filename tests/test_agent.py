from pathlib import Path

from app.agent import StockAgent
from app.database import AnalysisStore
from app.llm import LLMAnalyzer
from app.models import AnalysisRequest
from app.providers import MockDataProvider


def test_agent_runs_all_default_tools_and_persists(tmp_path: Path):
    store = AnalysisStore(str(tmp_path / "agent.db"))
    agent = StockAgent(
        provider=MockDataProvider(),
        store=store,
        llm=LLMAnalyzer(enabled=False),
        news_limit=3,
    )
    response = agent.analyze(
        AnalysisRequest(symbol="2330", question="請綜合分析價格、技術面、基本面與新聞")
    )

    assert response.analysis_id is not None
    assert "Important Notice" in response.report
    assert response.bundle.symbol == "2330.TW"
    assert response.bundle.sections["price"]["status"] == "ok"
    assert response.bundle.sections["technical"]["status"] == "ok"
    assert response.bundle.sections["fundamentals"]["status"] == "ok"
    assert response.bundle.sections["news"]["status"] == "ok"
    assert len(store.recent_analyses("2330.TW")) == 1


def test_planner_skips_unrequested_sections(tmp_path: Path):
    store = AnalysisStore(str(tmp_path / "agent.db"))
    agent = StockAgent(MockDataProvider(), store, LLMAnalyzer(enabled=False))
    response = agent.analyze(AnalysisRequest(symbol="2330", question="只看股價"))

    assert response.bundle.plan["price"] is True
    assert response.bundle.plan["technical"] is False
    assert response.bundle.sections["technical"]["status"] == "skipped"
    assert response.bundle.sections["fundamentals"]["status"] == "skipped"
    assert response.bundle.sections["news"]["status"] == "skipped"
