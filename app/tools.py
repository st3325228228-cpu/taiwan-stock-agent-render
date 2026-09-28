"""Tool wrappers used by the planner and orchestration layer."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .models import ToolResult
from .providers import MarketDataProvider
from .technical import calculate_indicators


class PriceTool:
    """Read-only latest price and daily OHLCV history tool."""

    name = "股價 Tool"

    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def run(self, symbol: str) -> tuple[ToolResult, pd.DataFrame]:
        result = self.provider.fetch_snapshot(symbol)
        history = self.provider.fetch_history(symbol)
        return result, history


class TechnicalAnalysisTool:
    """Compute transparent, reproducible daily technical indicators."""

    name = "技術分析 Tool"

    def run(self, history: pd.DataFrame) -> ToolResult:
        result = calculate_indicators(history)
        return ToolResult(tool="technical", data=result, source="local calculation")


class FundamentalTool:
    """Read-only company profile and provider fundamental fields."""

    name = "基本面 Tool"

    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def run(self, symbol: str) -> ToolResult:
        return self.provider.fetch_fundamentals(symbol)


class NewsSearchTool:
    """Read-only recent news search tool."""

    name = "新聞搜尋 Tool"

    def __init__(self, provider: MarketDataProvider, limit: int = 8) -> None:
        self.provider = provider
        self.limit = limit

    def run(self, symbol: str) -> ToolResult:
        return self.provider.fetch_news(symbol, limit=self.limit)


class DatabaseTool:
    """Persistence tool for prior analyses and evidence snapshots."""

    name = "資料庫 Tool"

    def __init__(self, store: Any) -> None:
        self.store = store

    def load_context(self, symbol: str, limit: int = 3) -> ToolResult:
        return ToolResult(
            tool="database",
            data={"recent_analyses": self.store.recent_analyses(symbol, limit)},
            source="local SQLite",
        )

    def save_snapshot(self, symbol: str, result: ToolResult) -> None:
        self.store.save_snapshot(symbol, result.tool, result.to_dict())

    def save_analysis(self, bundle: Any, report: str) -> int:
        return self.store.save_analysis(bundle, report)
