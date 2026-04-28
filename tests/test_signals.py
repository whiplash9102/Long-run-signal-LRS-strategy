from __future__ import annotations

import unittest

import pandas as pd

from src.strategy.signals import (
    BUY_ALERT,
    EXIT_ALERT,
    LONG,
    NO_CHANGE,
    RISK_OFF,
    WARMUP,
    build_signal_quality_report,
    build_signals,
)


class SignalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.prices = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
                "ticker": ["SPY", "SPY", "SPY", "SPY"],
                "adjusted_close": [99.0, 101.0, 100.0, 98.0],
                "adjusted_open": [98.0, 100.0, 101.0, 99.0],
            }
        )
        self.indicators = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
                "ticker": ["SPY", "SPY", "SPY", "SPY"],
                "filter_id": ["SMA_2", "SMA_2", "SMA_2", "SMA_2"],
                "filter_type": ["SMA", "SMA", "SMA", "SMA"],
                "filter_length": [2, 2, 2, 2],
                "filter_value": [None, 100.0, 100.0, 100.0],
                "filter_is_valid": [False, True, True, True],
            }
        )

    def test_signal_events_and_equality_rule(self) -> None:
        signals = build_signals(
            prices=self.prices,
            indicators=self.indicators,
            tickers=["SPY"],
            signal_price_field="adjusted_close",
            execution_price_field="adjusted_open",
            initial_state=RISK_OFF,
            execution_timing="next_session_open",
            risk_off_asset="BIL",
        )

        self.assertEqual(signals.loc[0, "current_state"], WARMUP)
        self.assertEqual(signals.loc[0, "signal_event"], NO_CHANGE)
        self.assertEqual(signals.loc[1, "current_state"], LONG)
        self.assertEqual(signals.loc[1, "signal_event"], BUY_ALERT)
        self.assertEqual(signals.loc[2, "current_state"], RISK_OFF)
        self.assertEqual(signals.loc[2, "signal_event"], EXIT_ALERT)
        self.assertEqual(signals.loc[3, "current_state"], RISK_OFF)
        self.assertEqual(signals.loc[3, "signal_event"], NO_CHANGE)

    def test_next_execution_fields_are_shifted(self) -> None:
        signals = build_signals(
            prices=self.prices,
            indicators=self.indicators,
            tickers=["SPY"],
            signal_price_field="adjusted_close",
            execution_price_field="adjusted_open",
            initial_state=RISK_OFF,
            execution_timing="next_session_open",
            risk_off_asset="BIL",
        )

        self.assertEqual(signals.loc[1, "next_execution_date"], "2024-01-03")
        self.assertEqual(signals.loc[1, "next_execution_open"], 101.0)
        self.assertFalse(signals.loc[3, "signal_is_tradable"])

    def test_quality_report_counts_alerts(self) -> None:
        signals = build_signals(
            prices=self.prices,
            indicators=self.indicators,
            tickers=["SPY"],
            signal_price_field="adjusted_close",
            execution_price_field="adjusted_open",
            initial_state=RISK_OFF,
            execution_timing="next_session_open",
            risk_off_asset="BIL",
        )
        report = build_signal_quality_report(signals)

        self.assertEqual(report.loc[0, "warmup_rows"], 1)
        self.assertEqual(report.loc[0, "buy_alerts"], 1)
        self.assertEqual(report.loc[0, "exit_alerts"], 1)


if __name__ == "__main__":
    unittest.main()
