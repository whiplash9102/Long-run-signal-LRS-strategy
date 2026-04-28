from __future__ import annotations

import unittest

import pandas as pd

from src.data.market_data import build_adjusted_prices, build_daily_returns, build_risk_off_returns


class MarketDataTest(unittest.TestCase):
    def test_adjusted_open_uses_close_adjustment_ratio(self) -> None:
        raw = pd.DataFrame(
            {
                "date": ["2024-01-02"],
                "ticker": ["SPY"],
                "open": [100.0],
                "high": [110.0],
                "low": [90.0],
                "close": [100.0],
                "adjusted_close": [50.0],
                "volume": [1000],
            }
        )
        adjusted = build_adjusted_prices(raw)
        self.assertEqual(adjusted.loc[0, "adjusted_open"], 50.0)
        self.assertEqual(adjusted.loc[0, "adjustment_ratio"], 0.5)

    def test_daily_returns_are_grouped_by_ticker(self) -> None:
        adjusted = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03", "2024-01-02", "2024-01-03"],
                "ticker": ["A", "A", "B", "B"],
                "adjusted_close": [100.0, 110.0, 50.0, 55.0],
            }
        )
        returns = build_daily_returns(adjusted)
        second_rows = returns.groupby("ticker").nth(1).set_index("ticker")
        self.assertAlmostEqual(second_rows.loc["A", "daily_return"], 0.10)
        self.assertAlmostEqual(second_rows.loc["B", "daily_return"], 0.10)

    def test_risk_off_uses_cash_fallback_before_primary_exists(self) -> None:
        adjusted = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
                "ticker": ["SPY", "BIL", "BIL"],
                "adjusted_close": [100.0, 90.0, 99.0],
            }
        )
        risk_off = build_risk_off_returns(
            adjusted_prices=adjusted,
            primary_asset="BIL",
            fallback_asset="CASH",
            cash_daily_return=0.0,
        )
        self.assertEqual(risk_off.loc[0, "risk_off_asset"], "CASH")
        self.assertTrue(risk_off.loc[0, "fallback_used"])
        self.assertEqual(risk_off.loc[1, "risk_off_asset"], "BIL")
        self.assertFalse(risk_off.loc[1, "fallback_used"])
        self.assertAlmostEqual(risk_off.loc[1, "risk_off_return"], 0.0)
        self.assertAlmostEqual(risk_off.loc[2, "risk_off_return"], 0.10)

    def test_risk_off_cash_primary_uses_cash_for_all_dates(self) -> None:
        adjusted = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03"],
                "ticker": ["SPY", "BIL"],
                "adjusted_close": [100.0, 90.0],
            }
        )
        risk_off = build_risk_off_returns(
            adjusted_prices=adjusted,
            primary_asset="CASH",
            fallback_asset="CASH",
            cash_daily_return=0.0,
        )

        self.assertEqual(risk_off["risk_off_asset"].unique().tolist(), ["CASH"])
        self.assertFalse(risk_off["fallback_used"].any())
        self.assertEqual(risk_off["risk_off_return"].sum(), 0.0)


if __name__ == "__main__":
    unittest.main()
