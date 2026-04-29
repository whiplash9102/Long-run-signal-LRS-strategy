from __future__ import annotations

from datetime import date, datetime
import unittest
from zoneinfo import ZoneInfo

import pandas as pd

from src.alerts.market_alert import build_market_alert, is_us_market_day, is_us_market_open_now


class MarketAlertTest(unittest.TestCase):
    def test_market_calendar_skips_weekends_and_holidays(self) -> None:
        self.assertFalse(is_us_market_day(date(2024, 1, 1)))
        self.assertFalse(is_us_market_day(date(2024, 1, 6)))
        self.assertTrue(is_us_market_day(date(2024, 1, 3)))

    def test_market_open_check_uses_eastern_hours(self) -> None:
        open_time = datetime(2024, 1, 3, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        before_open = datetime(2024, 1, 3, 8, 0, tzinfo=ZoneInfo("America/New_York"))

        self.assertTrue(is_us_market_open_now(open_time))
        self.assertFalse(is_us_market_open_now(before_open))

    def test_build_alert_uses_last_confirmed_close_before_market_date(self) -> None:
        config = {
            "data": {
                "test_universe": [
                    {"ticker": "SPY"},
                ],
                "leveraged_execution": [
                    {
                        "signal_ticker": "SPY",
                        "execution_assets": [
                            {"id": "SPY_1X"},
                            {"id": "UPRO_3X"},
                        ],
                    }
                ],
            },
            "strategy": {
                "candidate_filters": [{"id": "SMA_2"}],
                "false_breakout": {"whipsaw_window_sessions": 3},
            },
        }
        prices = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
                "ticker": ["SPY", "SPY", "SPY", "SPY"],
                "adjusted_close": [99.0, 98.0, 101.0, 102.0],
            }
        )
        indicators = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
                "ticker": ["SPY", "SPY", "SPY", "SPY"],
                "filter_id": ["SMA_2"] * 4,
                "filter_value": [100.0, 100.0, 100.0, 100.5],
            }
        )
        signals = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
                "ticker": ["SPY", "SPY", "SPY", "SPY"],
                "filter_id": ["SMA_2"] * 4,
                "signal_price": [99.0, 98.0, 101.0, 102.0],
                "filter_value": [100.0, 100.0, 100.0, 100.5],
                "current_state": ["RISK_OFF", "RISK_OFF", "LONG", "LONG"],
                "signal_event": ["NO_CHANGE", "NO_CHANGE", "BUY_ALERT", "NO_CHANGE"],
                "signal_is_tradable": [True, True, True, False],
                "next_execution_date": ["2024-01-03", "2024-01-04", "2024-01-05", None],
            }
        )

        alert = build_market_alert(
            config=config,
            prices=prices,
            indicators=indicators,
            signals=signals,
            generated_at=datetime(2024, 1, 5, 10, 0, tzinfo=ZoneInfo("America/New_York")),
            market_date=date(2024, 1, 5),
        )

        self.assertEqual(alert.rows[0].action, "INVEST")
        self.assertEqual(alert.rows[0].signal_date, "2024-01-04")
        self.assertIn("UPRO_3X", alert.rows[0].execution_assets)


if __name__ == "__main__":
    unittest.main()

