"""Technical indicators for daily OHLCV data.

The formulas intentionally follow common public conventions: SMA, EMA, Wilder RSI,
MACD, and Bollinger Bands. Missing values remain missing instead of being filled
with zero.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _clean(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _series(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        raise ValueError(f"OHLCV 欄位缺少 {name}")
    return pd.to_numeric(frame[name], errors="coerce").dropna()


def sma(close: pd.Series, period: int) -> pd.Series:
    if period <= 0:
        raise ValueError("period 必須是正整數")
    return close.rolling(period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    if period <= 0:
        raise ValueError("period 必須是正整數")
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI with Wilder-style exponentially smoothed gains/losses."""
    if period <= 0:
        raise ValueError("period 必須是正整數")
    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    result = result.where(avg_loss.ne(0), 100.0)
    return result


def calculate_indicators(frame: pd.DataFrame) -> dict[str, Any]:
    """Return latest indicators and a compact trend interpretation."""
    close = _series(frame, "Close")
    if len(close) < 30:
        return {
            "status": "insufficient_data",
            "observations": int(len(close)),
            "required_observations": 30,
            "indicators": {},
        }

    sma20 = sma(close, 20)
    sma60 = sma(close, 60)
    sma120 = sma(close, 120)
    ema12 = ema(close, 12)
    ema26 = ema(close, 26)
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False, min_periods=9).mean()
    rsi14 = rsi_wilder(close, 14)
    bb_middle = sma20
    bb_std = close.rolling(20, min_periods=20).std(ddof=0)
    bb_upper = bb_middle + 2 * bb_std
    bb_lower = bb_middle - 2 * bb_std

    latest = float(close.iloc[-1])
    previous = float(close.iloc[-2])
    latest_sma20 = _clean(sma20.iloc[-1])
    latest_sma60 = _clean(sma60.iloc[-1])
    latest_sma120 = _clean(sma120.iloc[-1])
    latest_macd = _clean(macd_line.iloc[-1])
    latest_signal = _clean(signal.iloc[-1])

    if latest_sma20 is not None and latest_sma60 is not None:
        if latest > latest_sma20 > latest_sma60:
            trend = "偏多"
        elif latest < latest_sma20 < latest_sma60:
            trend = "偏空"
        else:
            trend = "震盪"
    else:
        trend = "資料不足"

    indicators = {
        "latest_close": latest,
        "change_1d_pct": (latest / previous - 1) * 100 if previous else None,
        "change_20d_pct": (
            (latest / float(close.iloc[-21]) - 1) * 100 if len(close) > 20 else None
        ),
        "sma20": latest_sma20,
        "sma60": latest_sma60,
        "sma120": latest_sma120,
        "ema12": _clean(ema12.iloc[-1]),
        "ema26": _clean(ema26.iloc[-1]),
        "rsi14": _clean(rsi14.iloc[-1]),
        "macd": latest_macd,
        "macd_signal": latest_signal,
        "macd_histogram": (
            latest_macd - latest_signal
            if latest_macd is not None and latest_signal is not None
            else None
        ),
        "bollinger_middle20": _clean(bb_middle.iloc[-1]),
        "bollinger_upper20": _clean(bb_upper.iloc[-1]),
        "bollinger_lower20": _clean(bb_lower.iloc[-1]),
        "trend": trend,
        "method": {
            "rsi": "Wilder smoothing, period=14",
            "macd": "EMA(12)-EMA(26), signal=EMA(9)",
            "bollinger": "SMA(20) +/- 2 * population std",
        },
        "data_window": {
            "start": str(close.index[0]),
            "end": str(close.index[-1]),
            "frequency": "daily",
            "observations": int(len(close)),
            "annualization_factor": 252,
        },
    }
    return {"status": "ok", "observations": int(len(close)), "indicators": indicators}
