from types import SimpleNamespace

import pandas as pd

from app.providers import YFinanceProvider


class StatementTicker:
    info = {}
    fast_info = {"market_cap": 1000.0, "currency": "TWD"}

    @staticmethod
    def get_income_stmt(freq="yearly"):
        return pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): [1000.0, 100.0, 180.0],
                pd.Timestamp("2024-12-31"): [800.0, 80.0, 140.0],
            },
            index=["Total Revenue", "Net Income", "Operating Income"],
        )

    @staticmethod
    def get_balance_sheet(freq="yearly"):
        return pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [200.0, 500.0, 1200.0, 300.0]},
            index=[
                "Cash And Cash Equivalents",
                "Stockholders Equity",
                "Total Assets",
                "Total Debt",
            ],
        )

    @staticmethod
    def get_cash_flow(freq="yearly"):
        return pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [120.0]},
            index=["Free Cash Flow"],
        )


def test_fundamentals_fall_back_to_annual_statements():
    provider = YFinanceProvider.__new__(YFinanceProvider)
    provider._yf = SimpleNamespace(Ticker=lambda symbol: StatementTicker())

    result = provider.fetch_fundamentals("2330")

    assert result.status == "ok"
    assert result.data["symbol"] == "2330.TW"
    assert result.data["revenue"] == 1000.0
    assert result.data["revenueGrowth"] == 0.25
    assert result.data["returnOnEquity"] == 0.2
    assert result.data["profitMargins"] == 0.1
    assert result.data["operatingMargins"] == 0.18
    assert result.data["totalCash"] == 200.0
    assert result.data["freeCashflow"] == 120.0
    assert result.data["trailingPE"] == 10.0
    assert result.data["priceToBook"] == 2.0
    assert result.data["financials_as_of"] == "2025-12-31 00:00:00"
