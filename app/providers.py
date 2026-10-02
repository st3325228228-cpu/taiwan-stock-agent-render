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

    @staticmethod
    def _clean_value(value: Any) -> Any:
        """Return None for provider NaN/NA values while preserving real values."""
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        return value

    @classmethod
    def _mapping_value(cls, mapping: Any, key: str) -> Any:
        """Read a value from yfinance dict-like and FastInfo objects safely."""
        try:
            getter = getattr(mapping, "get", None)
            if getter is not None:
                return cls._clean_value(getter(key))
            return cls._clean_value(getattr(mapping, key, None))
        except Exception:
            return None

    @classmethod
    def _statement_value(
        cls, frame: pd.DataFrame | None, keys: list[str], position: int = 0
    ) -> Any:
        """Read the newest or previous value from a yfinance statement frame."""
        if frame is None or frame.empty:
            return None
        for key in keys:
            if key not in frame.index:
                continue
            try:
                values = frame.loc[key].dropna()
                if len(values) > position:
                    return cls._clean_value(values.iloc[position])
            except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _ratio(numerator: Any, denominator: Any) -> float | None:
        """Calculate a ratio only when both financial statement values exist."""
        try:
            if numerator is None or denominator in (None, 0):
                return None
            return float(numerator) / float(denominator)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @staticmethod
    def _first_value(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None

    def fetch_fundamentals(self, symbol: str) -> ToolResult:
        normalized = normalize_tw_symbol(symbol)
        ticker = self._ticker(normalized)
        errors: list[str] = []
        try:
            info = getattr(ticker, "info", {}) or {}
        except Exception as exc:
            info = {}
            errors.append(f"summary: {type(exc).__name__}")
        try:
            fast_info = getattr(ticker, "fast_info", {}) or {}
        except Exception as exc:
            fast_info = {}
            errors.append(f"fast_info: {type(exc).__name__}")

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
        data = {
            key: self._mapping_value(info, key)
            for key in keys
            if self._mapping_value(info, key) is not None
        }
        data["symbol"] = normalized
        data["marketCap"] = self._first_value(
            data.get("marketCap"), self._mapping_value(fast_info, "market_cap")
        )
        data["currency"] = self._first_value(
            data.get("currency"), self._mapping_value(fast_info, "currency"), "TWD"
        )

        financial_keys = (
            "marketCap",
            "trailingPE",
            "priceToBook",
            "returnOnEquity",
            "profitMargins",
            "totalCash",
            "totalDebt",
            "freeCashflow",
            "revenue",
            "netIncome",
            "operatingIncome",
            "totalAssets",
            "totalEquity",
        )
        statement_dates: list[str] = []
        if any(data.get(key) is None for key in financial_keys):
            statements: dict[str, pd.DataFrame | None] = {}
            for name, getter_name in (
                ("income", "get_income_stmt"),
                ("balance", "get_balance_sheet"),
                ("cash", "get_cash_flow"),
            ):
                try:
                    frame = getattr(ticker, getter_name)(freq="yearly")
                    statements[name] = frame
                    if frame is not None and not frame.empty:
                        statement_dates.extend(str(column) for column in frame.columns[:1])
                except Exception as exc:
                    statements[name] = None
                    errors.append(f"{name}: {type(exc).__name__}")

            income = statements.get("income")
            balance = statements.get("balance")
            cash = statements.get("cash")
            revenue = self._statement_value(
                income, ["Total Revenue", "TotalRevenue", "Operating Revenue", "OperatingRevenue"]
            )
            previous_revenue = self._statement_value(
                income,
                ["Total Revenue", "TotalRevenue", "Operating Revenue", "OperatingRevenue"],
                position=1,
            )
            net_income = self._statement_value(
                income,
                [
                    "Net Income",
                    "NetIncome",
                    "Net Income Common Stockholders",
                    "NetIncomeCommonStockholders",
                ],
            )
            operating_income = self._statement_value(
                income, ["Operating Income", "OperatingIncome"]
            )
            total_assets = self._statement_value(balance, ["Total Assets", "TotalAssets"])
            total_equity = self._statement_value(
                balance,
                [
                    "Stockholders Equity",
                    "StockholdersEquity",
                    "Common Stock Equity",
                    "CommonStockEquity",
                    "Total Equity Gross Minority Interest",
                    "TotalEquityGrossMinorityInterest",
                ],
            )
            total_cash = self._statement_value(
                balance,
                [
                    "Cash Cash Equivalents And Short Term Investments",
                    "CashCashEquivalentsAndShortTermInvestments",
                    "Cash And Cash Equivalents",
                    "CashAndCashEquivalents",
                ],
            )
            total_debt = self._statement_value(
                balance,
                [
                    "Total Debt",
                    "TotalDebt",
                    "Long Term Debt And Capital Lease Obligation",
                    "LongTermDebtAndCapitalLeaseObligation",
                ],
            )
            free_cashflow = self._statement_value(cash, ["Free Cash Flow", "FreeCashFlow"])

            derived = {
                "revenue": revenue,
                "netIncome": net_income,
                "operatingIncome": operating_income,
                "totalAssets": total_assets,
                "totalEquity": total_equity,
                "totalCash": total_cash,
                "totalDebt": total_debt,
                "freeCashflow": free_cashflow,
                "revenueGrowth": self._ratio(
                    revenue - previous_revenue
                    if revenue is not None and previous_revenue is not None
                    else None,
                    previous_revenue,
                ),
                "returnOnEquity": self._ratio(net_income, total_equity),
                "returnOnAssets": self._ratio(net_income, total_assets),
                "profitMargins": self._ratio(net_income, revenue),
                "operatingMargins": self._ratio(operating_income, revenue),
            }
            for key, value in derived.items():
                if data.get(key) is None and value is not None:
                    data[key] = value

            if data.get("marketCap") is not None and data.get("netIncome") is not None:
                data.setdefault("trailingPE", self._ratio(data["marketCap"], data["netIncome"]))
            if data.get("marketCap") is not None and data.get("totalEquity") is not None:
                data.setdefault("priceToBook", self._ratio(data["marketCap"], data["totalEquity"]))

        if statement_dates:
            data["financials_as_of"] = statement_dates[0]
        data["data_sources"] = "Yahoo Finance summary/profile; financial statements fallback when available"
        data["source_note"] = (
            "Summary fields are supplemented by annual income statement, balance sheet, and cash-flow data when available; verify valuation-critical values against filings."
        )
        if errors:
            data["retrieval_notes"] = "；".join(errors)
        usable_fields = [
            key
            for key in (
                "longName",
                "industry",
                "marketCap",
                "trailingPE",
                "priceToBook",
                "returnOnEquity",
                "returnOnAssets",
                "revenue",
                "netIncome",
                "totalEquity",
                "totalCash",
                "totalDebt",
                "freeCashflow",
            )
            if data.get(key) is not None
        ]
        return ToolResult(
            tool="fundamentals",
            status="ok" if usable_fields else "partial",
            data=json_safe(data),
            source=self.name,
            data_as_of=data.get("financials_as_of", now_utc_iso()),
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
