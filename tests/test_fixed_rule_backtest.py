from __future__ import annotations

import unittest

import pandas as pd

from src.backtest.fixed_rule import (
    ExecutionAsset,
    ExecutionMapping,
    build_fixed_rule_backtest,
    build_open_to_open_returns,
    calculate_metrics,
    run_single_combination,
)


class FixedRuleBacktestTest(unittest.TestCase):
    def test_open_to_open_returns_are_grouped_by_ticker(self) -> None:
        prices = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"],
                "ticker": ["A", "A", "B", "B"],
                "adjusted_open": [100.0, 110.0, 50.0, 55.0],
            }
        )
        returns = build_open_to_open_returns(prices)
        first_rows = returns.groupby("ticker").nth(0).set_index("ticker")

        self.assertAlmostEqual(first_rows.loc["A", "open_to_open_return"], 0.10)
        self.assertAlmostEqual(first_rows.loc["B", "open_to_open_return"], 0.10)

    def test_strategy_holds_cash_when_risk_off(self) -> None:
        prices = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
                "ticker": ["SSO", "SSO", "SSO"],
                "adjusted_open": [100.0, 110.0, 99.0],
            }
        )
        open_returns = build_open_to_open_returns(prices)
        signals = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02"],
                "ticker": ["SPY", "SPY"],
                "filter_id": ["SMA_200", "SMA_200"],
                "current_state": ["LONG", "RISK_OFF"],
                "signal_event": ["BUY_ALERT", "EXIT_ALERT"],
                "signal_is_tradable": [True, True],
                "next_execution_date": ["2024-01-02", "2024-01-03"],
            }
        )

        result = run_single_combination(
            signals=signals,
            open_returns=open_returns,
            signal_ticker="SPY",
            filter_id="SMA_200",
            execution_asset=ExecutionAsset(
                id="SSO_2X",
                ticker="SSO",
                leverage=2.0,
                mode="observed_leveraged_etf",
            ),
            cost_bps_per_side=0.0,
            synthetic_fee_bps_per_year=0.0,
            initial_capital=100.0,
        )
        strategy = result["equity_curve"][result["equity_curve"]["result_type"] == "strategy"]

        self.assertAlmostEqual(strategy.iloc[0]["daily_return"], 0.10)
        self.assertAlmostEqual(strategy.iloc[1]["daily_return"], 0.0)

    def test_synthetic_leverage_uses_signal_ticker_returns(self) -> None:
        prices = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03"],
                "ticker": ["VGK", "VGK"],
                "adjusted_open": [100.0, 110.0],
            }
        )
        open_returns = build_open_to_open_returns(prices)
        signals = pd.DataFrame(
            {
                "date": ["2024-01-01"],
                "ticker": ["VGK"],
                "filter_id": ["SMA_200"],
                "current_state": ["LONG"],
                "signal_event": ["BUY_ALERT"],
                "signal_is_tradable": [True],
                "next_execution_date": ["2024-01-02"],
            }
        )

        result = run_single_combination(
            signals=signals,
            open_returns=open_returns,
            signal_ticker="VGK",
            filter_id="SMA_200",
            execution_asset=ExecutionAsset(
                id="VGK_SYNTHETIC_2X",
                ticker=None,
                leverage=2.0,
                mode="synthetic_from_signal_etf",
            ),
            cost_bps_per_side=0.0,
            synthetic_fee_bps_per_year=0.0,
            initial_capital=100.0,
        )
        strategy = result["equity_curve"][result["equity_curve"]["result_type"] == "strategy"]

        self.assertAlmostEqual(strategy.iloc[0]["daily_return"], 0.20)

    def test_build_fixed_rule_backtest_creates_metrics(self) -> None:
        prices = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03"],
                "ticker": ["SPY", "SPY"],
                "adjusted_open": [100.0, 101.0],
            }
        )
        signals = pd.DataFrame(
            {
                "date": ["2024-01-01"],
                "ticker": ["SPY"],
                "filter_id": ["SMA_200"],
                "current_state": ["LONG"],
                "signal_event": ["BUY_ALERT"],
                "signal_is_tradable": [True],
                "next_execution_date": ["2024-01-02"],
            }
        )
        result = build_fixed_rule_backtest(
            prices=prices,
            signals=signals,
            mappings=(
                ExecutionMapping(
                    signal_ticker="SPY",
                    execution_assets=(
                        ExecutionAsset(
                            id="SPY_1X",
                            ticker="SPY",
                            leverage=1.0,
                            mode="observed_etf",
                        ),
                    ),
                ),
            ),
            candidate_filter_ids=["SMA_200"],
            cost_bps_per_side=0.0,
            synthetic_fee_bps_per_year=0.0,
            initial_capital=100.0,
        )

        self.assertFalse(result["metrics"].empty)

    def test_metrics_include_trade_quality_fields(self) -> None:
        curve = pd.DataFrame(
            {
                "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
                "signal_ticker": ["SPY", "SPY", "SPY"],
                "filter_id": ["SMA_200", "SMA_200", "SMA_200"],
                "execution_id": ["SPY_1X", "SPY_1X", "SPY_1X"],
                "execution_ticker": ["SPY", "SPY", "SPY"],
                "execution_mode": ["observed_etf", "observed_etf", "observed_etf"],
                "leverage": [1.0, 1.0, 1.0],
                "result_type": ["strategy", "strategy", "strategy"],
                "daily_return": [0.01, -0.02, 0.03],
                "equity": [101.0, 98.98, 101.9494],
                "exposure": [1.0, 1.0, 0.0],
            }
        )
        trades = pd.DataFrame(
            {
                "execution_date": ["2024-01-02", "2024-01-04"],
                "action": ["BUY", "EXIT"],
                "equity": [101.0, 101.9494],
            }
        )

        metrics = calculate_metrics(curve, trades)

        self.assertIn("max_recovery_days", metrics.columns)
        self.assertIn("average_hold_days", metrics.columns)
        self.assertIn("win_rate_by_trade", metrics.columns)
        self.assertIn("profit_factor", metrics.columns)
        self.assertEqual(metrics.loc[0, "round_trip_count"], 1)


if __name__ == "__main__":
    unittest.main()
