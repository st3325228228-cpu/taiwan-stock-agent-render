"""CLI entry point for the Taiwan stock AI agent."""

from __future__ import annotations

import argparse
import json

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - requirements.txt includes python-dotenv
    load_dotenv = lambda: None

from .agent import StockAgent
from .config import Settings
from .database import AnalysisStore
from .llm import LLMAnalyzer
from .models import AnalysisRequest
from .providers import MockDataProvider, YFinanceProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="台股 AI Agent：股價、技術分析、基本面、新聞與 SQLite 綜合分析"
    )
    parser.add_argument("symbol", help="台股代號，例如 2330、2330.TW、6488.TWO")
    parser.add_argument(
        "--question",
        default="請綜合分析這檔股票的價格、技術面、基本面與近期新聞。",
        help="使用者問題",
    )
    parser.add_argument("--lookback", type=int, default=365, help="分析回看天數（目前保留給擴充）")
    parser.add_argument("--no-llm", action="store_true", help="只使用本地模板，不呼叫 LLM")
    parser.add_argument("--mock", action="store_true", help="使用內建假資料驗證流程")
    parser.add_argument("--json", action="store_true", help="輸出完整 JSON 結果")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_dotenv()
    settings = Settings.from_env()
    provider = MockDataProvider() if args.mock else YFinanceProvider()
    store = AnalysisStore(settings.database_path)
    llm = LLMAnalyzer(
        model=settings.llm_model,
        enabled=settings.use_llm and not args.no_llm,
    )
    agent = StockAgent(provider, store, llm, news_limit=settings.news_limit)
    response = agent.analyze(
        AnalysisRequest(symbol=args.symbol, question=args.question, lookback_days=args.lookback)
    )
    if args.json:
        print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(response.report)
        print(f"\n[analysis_id={response.analysis_id or 'not_saved'}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
