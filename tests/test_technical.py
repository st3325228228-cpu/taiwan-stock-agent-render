import numpy as np
import pandas as pd
import pytest

from app.technical import calculate_indicators, rsi_wilder, sma


def _fixed_close(periods: int = 40) -> pd.Series:
    """日期升冪、收盤價為 1～periods 的固定序列，供 SMA20 測試重複使用。"""
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    return pd.Series(range(1, periods + 1), index=dates, dtype=float)


def _fixed_frame(close: pd.Series) -> pd.DataFrame:
    """把固定收盤價包成 calculate_indicators() 需要的 OHLCV 欄位。"""
    return pd.DataFrame(
        {
            "Open": close - 1,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": 1000,
        }
    )


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


def test_sma20_on_fixed_series_has_warmup_nan_and_expected_values():
    """收盤價 1～40、週期 20：前 19 筆暖機期為 NaN，第 20 筆 10.5，第 40 筆 30.5。"""
    close = _fixed_close()
    result = sma(close, 20)

    assert len(result) == 40
    assert result.iloc[:19].isna().all()
    assert result.iloc[19:].notna().all()
    assert result.iloc[19] == pytest.approx(10.5)
    assert result.iloc[-1] == pytest.approx(30.5)


def test_sma20_is_all_nan_when_observations_are_insufficient():
    """只有 19 筆資料時，不足一個完整視窗，全部結果都必須是 NaN。"""
    result = sma(_fixed_close(periods=19), 20)

    assert len(result) == 19
    assert result.isna().all()


def test_sma20_is_nan_only_for_windows_containing_a_missing_value():
    """最新 20 筆中有一筆 NaN 時，最新 SMA20 為 NaN，未受影響的視窗仍保留原值。"""
    close = _fixed_close()
    close.iloc[35] = np.nan
    result = sma(close, 20)

    assert pd.isna(result.iloc[-1])
    # 視窗 20（索引 0～19）不含缺值，數值不受影響。
    assert result.iloc[19] == pytest.approx(10.5)


@pytest.mark.parametrize("period", [0, -1])
def test_sma_rejects_non_positive_period(period):
    with pytest.raises(ValueError):
        sma(_fixed_close(), period)


def test_sma20_of_existing_dates_is_unchanged_by_appended_prices():
    """在原資料後追加極大收盤價，不得改變原有 40 個日期的 SMA20 結果。"""
    close = _fixed_close()
    appended_index = pd.date_range("2024-02-10", periods=3, freq="D")
    extended = pd.concat(
        [close, pd.Series([10_000.0, 10_100.0, 10_200.0], index=appended_index)]
    )

    baseline = sma(close, 20)
    after_append = sma(extended, 20).iloc[: len(close)]

    np.testing.assert_allclose(
        after_append.to_numpy(dtype=float),
        baseline.to_numpy(dtype=float),
        equal_nan=True,
    )


def test_calculate_indicators_sma20_matches_direct_calculation():
    """40 筆固定資料送入 calculate_indicators()，sma20 須與直接計算一致（約 30.5）。"""
    close = _fixed_close()
    result = calculate_indicators(_fixed_frame(close))

    assert result["status"] == "ok"
    assert result["observations"] == 40
    assert result["indicators"]["sma20"] == pytest.approx(30.5)
    assert result["indicators"]["sma20"] == pytest.approx(float(sma(close, 20).iloc[-1]))
