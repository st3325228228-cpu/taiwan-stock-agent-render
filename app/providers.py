"""Read-only market data providers.

The default provider uses yfinance for research-level Taiwan stock data. The
agent records provider, retrieval time, and data-as-of information so each
report exposes the source and freshness limitations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

import pandas as pd

from .models import ToolResult, json_safe, now_utc_iso


def normalize_tw_symbol(symbol: str) -> str:
    """Normalize a Taiwan listed/OTC code to a Yahoo-style symbol."""
    value = symbol.strip().upper()
    if not value:
        raise ValueError("股票代號不可為空")
    if value.isdigit():
        return f"{value}.TW"
    if value.endswith(".TW") or value.endswith(".TWO"):
        return value
    return value


class MarketDataProvider(Protocol):
    """Minimal provider contract used by the tools and tests."""

    name: str

    def fetch_history(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        ...

    def fetch_snapshot(self, symbol: str) -> ToolResult:
        ...

    def fetch_fundamentals(self, symbol: str) -> ToolResult:
        ...

    def fetch_news(self, symbol: str, limit: int = 8) -> ToolResult:
        ...


class YFinanceProvider:
    """Yahoo Finance adapter through the public yfinance Python package."""

    name = "Yahoo Finance via yfinance"

    def __init__(self) -> None:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError(
                "找不到 yfinance，請先執行 pip install -r requirements.txt"
            ) from exc
        self._yf = yf

    def _ticker(self, symbol: str) -> Any:
        return self._yf.Ticker(normalize_tw_symbol(symbol))

    def fetch_history(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        ticker = self._ticker(symbol)
        frame = ticker.history(period=period, interval="1d", auto_adjust=False)
        if frame is None or frame.empty:
            raise ValueError(f"找不到 {symbol} 的歷史行情資料")
        frame = frame.copy()
        frame.columns = [str(column).title() for column in frame.columns]
        return frame.sort_index()

    def fetch_snapshot(self, symbol: str) -> ToolResult:
        normalized = normalize_tw_symbol(symbol)
        ticker = self._ticker(normalized)
        frame = self.fetch_history(normalized, period="5d")
        last_row = frame.iloc[-1]
        timestamp = frame.index[-1]
        fast_info = getattr(ticker, "fast_info", {}) or {}
        last_price = fast_info.get("last_price") or last_row.get("Close")
        previous_close = fast_info.get("previous_close")
        if previous_close is None and len(frame) > 1:
            previous_close = frame.iloc[-2].get("Close")
        change_pct = None
        if last_price is not None and previous_close not in (None, 0):
            change_pct = (float(last_price) / float(previous_close) - 1) * 100
        data = {
            "symbol": normalized,
            "price": last_price,
            "previous_close": previous_close,
            "change_pct": change_pct,
            "open": last_row.get("Open"),
            "high": last_row.get("High"),
            "low": last_row.get("Low"),
            "close": last_row.get("Close"),
            "volume": last_row.get("Volume"),
            "currency": fast_info.get("currency", "TWD"),
            "market_state": fast_info.get("market_state"),
            "price_timestamp": str(timestamp),
            "adjustment": "raw OHLC; auto_adjust=False",
        }
        return ToolResult(
            tool="price",
            data=json_safe(data),
            source=self.name,
            data_as_of=str(timestamp),
        )

    def fetch_fundamentals(self, symbol: str) -> ToolResult:
        normalized = normalize_tw_symbol(symbol)
        ticker = self._ticker(normalized)
        info = getattr(ticker, "info", {}) or {}
        keys = [
            "symbol",
            "longName",
            "sector",
            "industry",
            "currency",
            "marketCap",
            "trailingPE",
            "forwardPE",
            "priceToBook",
            "returnOnEquity",
            "returnOnAssets",
            "profitMargins",
            "operatingMargins",
            "revenueGrowth",
            "earningsGrowth",
            "totalCash",
            "totalDebt",
            "freeCashflow",
            "dividendYield",
            "fullTimeEmployees",
        ]
        data = {key: info.get(key) for key in keys if info.get(key) is not None}
        data["symbol"] = normalized
        data["source_note"] = (
            "Provider profile/summary fields; verify valuation-critical values against filings."
        )
        return ToolResult(
            tool="fundamentals",
            data=json_safe(data),
            source=self.name,
            data_as_of=now_utc_iso(),
        )

    def fetch_news(self, symbol: str, limit: int = 8) -> ToolResult:
        normalized = normalize_tw_symbol(symbol)
        ticker = self._ticker(normalized)
        raw_items = getattr(ticker, "news", []) or []
        items: list[dict[str, Any]] = []
        for item in raw_items[:limit]:
            content = item.get("content", item) if isinstance(item, dict) else {}
            provider_publish = content.get("providerPublishTime") or item.get(
                "providerPublishTime"
            )
            if isinstance(provider_publish, (int, float)):
                published_at = datetime.fromtimestamp(
                    provider_publish, tz=timezone.utc
                ).isoformat()
            else:
                published_at = content.get("pubDate") or item.get("pubDate")
            items.append(
                {
                    "title": content.get("title") or item.get("title"),
                    "publisher": (
                        (content.get("provider") or {}).get("displayName")
                        if isinstance(content.get("provider"), dict)
                        else content.get("publisher") or item.get("publisher")
                    ),
                    "published_at": published_at,
                    "link": content.get("canonicalUrl", {}).get("url")
                    if isinstance(content.get("canonicalUrl"), dict)
                    else content.get("link") or item.get("link"),
                    "summary": content.get("summary") or item.get("summary"),
                }
            )
        return ToolResult(
            tool="news",
            data={"symbol": normalized, "items": json_safe(items)},
            source=self.name,
            data_as_of=now_utc_iso(),
        )


class MockDataProvider:
    """Deterministic provider for tests and offline development."""

    name = "Mock provider"

    def __init__(self, frame: pd.DataFrame | None = None) -> None:
        if frame is None:
            dates = pd.date_range("2024-01-01", periods=140, freq="D")
            close = pd.Series(range(100, 240), index=dates, dtype=float)
            frame = pd.DataFrame(
                {
                    "Open": close - 1,
                    "High": close + 2,
                    "Low": close - 2,
                    "Close": close,
                    "Volume": 100_000,
                },
                index=dates,
            )
        self.frame = frame

    def fetch_history(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        return self.frame.copy()

    def fetch_snapshot(self, symbol: str) -> ToolResult:
        row = self.frame.iloc[-1]
        return ToolResult(
            tool="price",
            data={
                "symbol": normalize_tw_symbol(symbol),
                "price": float(row["Close"]),
                "previous_close": float(self.frame.iloc[-2]["Close"]),
                "change_pct": float(row["Close"] / self.frame.iloc[-2]["Close"] - 1) * 100,
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
                "currency": "TWD",
                "price_timestamp": str(self.frame.index[-1]),
            },
            source=self.name,
            data_as_of=str(self.frame.index[-1]),
        )

    def fetch_fundamentals(self, symbol: str) -> ToolResult:
        return ToolResult(
            tool="fundamentals",
            data={
                "symbol": normalize_tw_symbol(symbol),
                "longName": "Mock Taiwan Company",
                "sector": "Technology",
                "trailingPE": 20.0,
                "priceToBook": 3.0,
                "returnOnEquity": 0.18,
                "revenueGrowth": 0.12,
                "profitMargins": 0.22,
                "currency": "TWD",
            },
            source=self.name,
            data_as_of=str(self.frame.index[-1]),
        )

    def fetch_news(self, symbol: str, limit: int = 8) -> ToolResult:
        return ToolResult(
            tool="news",
            data={"symbol": normalize_tw_symbol(symbol), "items": []},
            source=self.name,
            data_as_of=str(self.frame.index[-1]),
        )
