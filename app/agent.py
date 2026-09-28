"""Question routing and orchestration for the Taiwan stock agent."""

from __future__ import annotations

from typing import Callable

from .llm import LLMAnalyzer
from .models import AgentResponse, AnalysisBundle, AnalysisRequest, ToolResult
from .providers import MarketDataProvider, normalize_tw_symbol
from .tools import (
    DatabaseTool,
    FundamentalTool,
    NewsSearchTool,
    PriceTool,
    TechnicalAnalysisTool,
)


class ToolPlanner:
    """Lightweight intent router; deterministic routing is easy to inspect and test."""

    _technical_terms = ("技術", "均線", "RSI", "MACD", "趨勢", "支撐", "壓力", "布林")
    _fundamental_terms = ("基本面", "財報", "營收", "獲利", "本益比", "估值", "毛利", "ROE", "公司")
    _news_terms = ("新聞", "消息", "事件", "法說", "公告", "近期", "產業")
    _history_terms = ("歷史", "上次", "過往", "資料庫", "比較")

    def plan(self, question: str) -> dict[str, bool]:
        text = question.upper()
        price_only = any(phrase in text for phrase in ("只看股價", "只看價格", "僅看股價", "僅看價格"))
        if price_only:
            return {
                "price": True,
                "technical": False,
                "fundamentals": False,
                "news": False,
                "database": True,
                "include_history_context": any(
                    term.upper() in text for term in self._history_terms
                ),
            }
        generic = not any(
            any(term.upper() in text for term in terms)
            for terms in (self._technical_terms, self._fundamental_terms, self._news_terms)
        )
        return {
            "price": True,
            "technical": generic or any(term.upper() in text for term in self._technical_terms),
            "fundamentals": generic
            or any(term.upper() in text for term in self._fundamental_terms),
            "news": generic or any(term.upper() in text for term in self._news_terms),
            "database": True,
            "include_history_context": any(
                term.upper() in text for term in self._history_terms
            ),
        }


class StockAgent:
    """Orchestrate data tools, synthesis, and local persistence."""

    def __init__(
        self,
        provider: MarketDataProvider,
        store,
        llm: LLMAnalyzer,
        news_limit: int = 8,
    ) -> None:
        self.provider = provider
        self.price_tool = PriceTool(provider)
        self.technical_tool = TechnicalAnalysisTool()
        self.fundamental_tool = FundamentalTool(provider)
        self.news_tool = NewsSearchTool(provider, limit=news_limit)
        self.database_tool = DatabaseTool(store)
        self.llm = llm
        self.planner = ToolPlanner()

    @staticmethod
    def _capture(
        tool_name: str, action: Callable[[], ToolResult], gaps: list[str]
    ) -> ToolResult:
        try:
            result = action()
            if result.status != "ok":
                gaps.append(f"{tool_name} 狀態為 {result.status}：{result.error or '未知原因'}")
            return result
        except Exception as exc:
            message = f"{tool_name} 失敗：{type(exc).__name__}: {exc}"
            gaps.append(message)
            return ToolResult(tool=tool_name, status="failed", error=str(exc), source="unavailable")

    def analyze(self, request: AnalysisRequest) -> AgentResponse:
        symbol = normalize_tw_symbol(request.symbol)
        plan = self.planner.plan(request.question)
        bundle = AnalysisBundle(symbol=symbol, question=request.question, plan=plan)
        gaps = bundle.data_gaps

        database_context = self._capture(
            "database",
            lambda: self.database_tool.load_context(symbol),
            gaps,
        )
        bundle.sections["database"] = database_context.to_dict()

        price_result: ToolResult
        history = None
        try:
            price_result, history = self.price_tool.run(symbol)
        except Exception as exc:
            gaps.append(f"股價 Tool 失敗：{type(exc).__name__}: {exc}")
            price_result = ToolResult(
                tool="price", status="failed", error=str(exc), source="unavailable"
            )
        bundle.sections["price"] = price_result.to_dict()
        bundle.source_manifest.append(
            {
                "source": price_result.source,
                "retrieved_at": price_result.retrieved_at,
                "data_as_of": price_result.data_as_of,
                "tool": price_result.tool,
                "status": price_result.status,
            }
        )
        try:
            self.database_tool.save_snapshot(symbol, price_result)
        except Exception as exc:
            gaps.append(f"資料庫 Tool 保存股價失敗：{type(exc).__name__}: {exc}")

        if plan["technical"] and history is not None:
            technical_result = self._capture(
                "technical",
                lambda: self.technical_tool.run(history),
                gaps,
            )
        else:
            technical_result = ToolResult(
                tool="technical", status="skipped", data={"reason": "問題未要求技術分析"}
            )
        bundle.sections["technical"] = technical_result.to_dict()
        bundle.source_manifest.append(
            {
                "source": technical_result.source,
                "retrieved_at": technical_result.retrieved_at,
                "data_as_of": technical_result.data_as_of,
                "tool": technical_result.tool,
                "status": technical_result.status,
            }
        )

        if plan["fundamentals"] and request.include_fundamentals:
            fundamentals_result = self._capture(
                "fundamentals", lambda: self.fundamental_tool.run(symbol), gaps
            )
        else:
            fundamentals_result = ToolResult(
                tool="fundamentals", status="skipped", data={"reason": "問題未要求基本面"}
            )
        bundle.sections["fundamentals"] = fundamentals_result.to_dict()
        bundle.source_manifest.append(
            {
                "source": fundamentals_result.source,
                "retrieved_at": fundamentals_result.retrieved_at,
                "data_as_of": fundamentals_result.data_as_of,
                "tool": fundamentals_result.tool,
                "status": fundamentals_result.status,
            }
        )

        if plan["news"] and request.include_news:
            news_result = self._capture("news", lambda: self.news_tool.run(symbol), gaps)
        else:
            news_result = ToolResult(
                tool="news", status="skipped", data={"items": [], "reason": "問題未要求新聞"}
            )
        bundle.sections["news"] = news_result.to_dict()
        bundle.source_manifest.append(
            {
                "source": news_result.source,
                "retrieved_at": news_result.retrieved_at,
                "data_as_of": news_result.data_as_of,
                "tool": news_result.tool,
                "status": news_result.status,
            }
        )

        report = self.llm.generate(bundle)
        try:
            analysis_id = self.database_tool.save_analysis(bundle, report)
        except Exception as exc:
            gaps.append(f"資料庫 Tool 保存分析失敗：{type(exc).__name__}: {exc}")
            analysis_id = None
        return AgentResponse(report=report, bundle=bundle, analysis_id=analysis_id)
