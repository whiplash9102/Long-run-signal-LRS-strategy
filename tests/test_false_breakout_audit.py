from __future__ import annotations

import unittest

import pandas as pd

from src.reporting.false_breakout_audit import build_false_breakout_audit


class FalseBreakoutAuditTest(unittest.TestCase):
    def test_audit_pairs_buy_and_exit_and_labels_whipsaw(self) -> None:
        prices = pd.DataFrame(
            {
                "date": [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-04",
                    "2024-01-05",
                    "2024-01-06",
                ],
                "ticker": ["SPY"] * 6,
                "adjusted_close": [99.0, 101.0, 100.0, 98.0, 97.0, 96.0],
            }
        )
        indicators = pd.DataFrame(
            {
                "date": [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-04",
                    "2024-01-05",
                    "2024-01-06",
                ],
                "ticker": ["SPY"] * 6,
                "filter_id": ["SMA_2"] * 6,
                "filter_type": ["SMA"] * 6,
                "filter_length": [2] * 6,
                "filter_value": [None, 100.0, 100.0, 100.0, 99.5, 99.0],
                "filter_is_valid": [False, True, True, True, True, True],
            }
        )
        signals = pd.DataFrame(
            {
                "date": [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-04",
                    "2024-01-05",
                    "2024-01-06",
                ],
                "ticker": ["SPY"] * 6,
                "filter_id": ["SMA_2"] * 6,
                "filter_type": ["SMA"] * 6,
                "filter_length": [2] * 6,
                "signal_price": [99.0, 101.0, 100.0, 98.0, 97.0, 96.0],
                "filter_value": [None, 100.0, 100.0, 100.0, 99.5, 99.0],
                "previous_state": ["WARMUP", "RISK_OFF", "LONG", "LONG", "RISK_OFF", "RISK_OFF"],
                "current_state": ["WARMUP", "LONG", "LONG", "RISK_OFF", "RISK_OFF", "RISK_OFF"],
                "signal_event": ["NO_CHANGE", "BUY_ALERT", "NO_CHANGE", "EXIT_ALERT", "NO_CHANGE", "NO_CHANGE"],
                "signal_is_tradable": [False, True, True, True, True, False],
                "next_execution_date": [
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-04",
                    "2024-01-05",
                    "2024-01-06",
                    None,
                ],
            }
        )

        audit = build_false_breakout_audit(
            prices=prices,
            signals=signals,
            indicators=indicators,
            whipsaw_window_sessions=3,
            entry_vol_lookback=2,
            entry_slope_lookback=1,
        )

        entries = audit["entries"]
        summary = audit["summary"]

        self.assertEqual(len(entries), 1)
        self.assertTrue(entries.iloc[0]["whipsaw"])
        self.assertAlmostEqual(entries.iloc[0]["entry_distance_pct"], 0.01)
        self.assertEqual(summary.iloc[0]["whipsaws"], 1)
        self.assertEqual(summary.iloc[0]["buy_alerts"], 1)
        self.assertAlmostEqual(summary.iloc[0]["whipsaw_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()

