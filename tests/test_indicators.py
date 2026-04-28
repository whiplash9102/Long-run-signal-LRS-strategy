from __future__ import annotations

import unittest

import pandas as pd

from src.strategy.indicators import (
    IndicatorFilter,
    build_indicator_quality_report,
    build_indicators,
    calculate_filter,
)


class IndicatorTest(unittest.TestCase):
    def test_sma_requires_full_window(self) -> None:
        series = pd.Series([1.0, 2.0, 3.0, 4.0])
        result = calculate_filter(series, IndicatorFilter(id="SMA_3", type="SMA", length=3))

        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertTrue(pd.isna(result.iloc[1]))
        self.assertEqual(result.iloc[2], 2.0)
        self.assertEqual(result.iloc[3], 3.0)

    def test_ema_uses_documented_convention(self) -> None:
        series = pd.Series([10.0, 20.0, 30.0, 40.0])
        result = calculate_filter(series, IndicatorFilter(id="EMA_3", type="EMA", length=3))

        self.assertTrue(pd.isna(result.iloc[0]))
        self.assertTrue(pd.isna(result.iloc[1]))
        self.assertAlmostEqual(result.iloc[2], 22.5)
        self.assertAlmostEqual(result.iloc[3], 31.25)

    def test_build_indicators_excludes_non_test_tickers(self) -> None:
        prices = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"],
                "ticker": ["SPY", "SPY", "BIL", "BIL"],
                "adjusted_close": [100.0, 101.0, 90.0, 90.1],
            }
        )

        indicators = build_indicators(
            prices=prices,
            tickers=["SPY"],
            filters=[IndicatorFilter(id="SMA_2", type="SMA", length=2)],
            price_field="adjusted_close",
        )

        self.assertEqual(indicators["ticker"].unique().tolist(), ["SPY"])
        self.assertEqual(len(indicators), 2)
        self.assertFalse(indicators.iloc[0]["filter_is_valid"])
        self.assertTrue(indicators.iloc[1]["filter_is_valid"])

    def test_quality_report_tracks_first_valid_date(self) -> None:
        indicators = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02"],
                "ticker": ["SPY", "SPY"],
                "filter_id": ["SMA_2", "SMA_2"],
                "filter_type": ["SMA", "SMA"],
                "filter_length": [2, 2],
                "filter_value": [None, 100.5],
                "filter_is_valid": [False, True],
            }
        )

        report = build_indicator_quality_report(indicators)
        self.assertEqual(report.loc[0, "first_valid_date"], "2024-01-02")
        self.assertEqual(report.loc[0, "invalid_warmup_rows"], 1)


if __name__ == "__main__":
    unittest.main()
