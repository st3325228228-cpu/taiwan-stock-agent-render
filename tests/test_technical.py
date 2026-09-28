import pandas as pd

from app.technical import calculate_indicators, rsi_wilder, sma


def test_sma_and_rsi_on_monotonic_series():
    close = pd.Series(range(1, 81), dtype=float)
    assert sma(close, 5).iloc[-1] == 78.0
    assert rsi_wilder(close, 14).iloc[-1] == 100.0


def test_calculate_indicators_returns_trend():
    dates = pd.date_range("2024-01-01", periods=140, freq="D")
    close = pd.Series(range(100, 240), index=dates, dtype=float)
    frame = pd.DataFrame(
        {
            "Open": close - 1,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": 1000,
        }
    )
    result = calculate_indicators(frame)
    assert result["status"] == "ok"
    assert result["indicators"]["trend"] == "偏多"
    assert result["indicators"]["rsi14"] == 100.0
