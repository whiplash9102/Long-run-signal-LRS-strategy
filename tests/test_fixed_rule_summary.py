from __future__ import annotations

import unittest

import pandas as pd

from src.reporting.fixed_rule_summary import (
    build_strategy_vs_buy_hold,
    classify_drawdown,
    classify_recovery,
    enrich_metrics,
    rank_strategy_rows,
    render_review_report,
    select_best_by_signal,
)


class FixedRuleSummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.metrics = pd.DataFrame(
            [
                self._row("SPY", "SMA_200", "UPRO_3X", "strategy", 0.20, -0.55, 0.36),
                self._row("SPY", "SMA_200", "UPRO_3X", "buy_hold", 0.25, -0.80, 0.31),
                self._row("SPY", "EMA_200", "SSO_2X", "strategy", 0.12, -0.30, 0.40),
                self._row("SPY", "EMA_200", "SSO_2X", "buy_hold", 0.10, -0.45, 0.22),
                self._row("QQQ", "EMA_200", "TQQQ_3X", "strategy", 0.32, -0.58, 0.55),
                self._row("QQQ", "EMA_200", "TQQQ_3X", "buy_hold", 0.42, -0.82, 0.51),
            ]
        )

    def test_risk_buckets_are_clear(self) -> None:
        self.assertEqual(classify_drawdown(-0.71), "severe")
        self.assertEqual(classify_drawdown(-0.55), "high")
        self.assertEqual(classify_drawdown(-0.31), "moderate")
        self.assertEqual(classify_drawdown(-0.20), "lower")
        self.assertEqual(classify_recovery(1200), "severe")
        self.assertEqual(classify_recovery(800), "high")
        self.assertEqual(classify_recovery(400), "moderate")
        self.assertEqual(classify_recovery(100), "lower")

    def test_rankings_prioritize_calmar_then_growth(self) -> None:
        enriched = enrich_metrics(self.metrics, initial_capital=100000.0)
        rankings = rank_strategy_rows(enriched)

        self.assertEqual(rankings.iloc[0]["execution_id"], "TQQQ_3X")
        self.assertTrue(rankings.iloc[0]["profitable"])
        self.assertEqual(rankings.iloc[0]["risk_bucket"], "high")

    def test_best_by_signal_keeps_one_candidate_per_signal(self) -> None:
        enriched = enrich_metrics(self.metrics, initial_capital=100000.0)
        rankings = rank_strategy_rows(enriched)
        best = select_best_by_signal(rankings)

        self.assertEqual(set(best["signal_ticker"]), {"SPY", "QQQ"})
        spy = best[best["signal_ticker"].eq("SPY")].iloc[0]
        self.assertEqual(spy["execution_id"], "SSO_2X")

    def test_strategy_vs_buy_hold_uses_same_execution_asset(self) -> None:
        enriched = enrich_metrics(self.metrics, initial_capital=100000.0)
        comparison = build_strategy_vs_buy_hold(enriched)
        top = comparison[comparison["execution_id"].eq("TQQQ_3X")].iloc[0]

        self.assertAlmostEqual(top["CAGR_gap"], -0.10)
        self.assertAlmostEqual(top["drawdown_improvement"], 0.24)
        self.assertAlmostEqual(top["calmar_gap"], 0.04)

    def test_report_renders_core_sections(self) -> None:
        enriched = enrich_metrics(self.metrics, initial_capital=100000.0)
        rankings = rank_strategy_rows(enriched)
        observed = rankings[rankings["execution_mode"].eq("observed_leveraged_etf")]
        best = select_best_by_signal(rankings)
        comparison = build_strategy_vs_buy_hold(enriched)

        report = render_review_report(
            metrics=enriched,
            strategy_rankings=rankings,
            observed_rankings=observed,
            best_by_signal=best,
            strategy_vs_buy_hold=comparison,
            initial_capital=100000.0,
        )

        self.assertIn("# Fixed-Rule Backtest Review", report)
        self.assertIn("Best By Signal ETF", report)
        self.assertIn("fixed-rule research only", report)
        self.assertIn("| QQQ | EMA_200 | TQQQ_3X | yes | 32.00% | -58.00% | 0.5500 |", report)

    @staticmethod
    def _row(
        signal_ticker: str,
        filter_id: str,
        execution_id: str,
        result_type: str,
        cagr: float,
        max_drawdown: float,
        calmar: float,
    ) -> dict[str, object]:
        ending_equity = 100000.0 * (1.0 + cagr) ** 10
        return {
            "signal_ticker": signal_ticker,
            "filter_id": filter_id,
            "execution_id": execution_id,
            "execution_ticker": execution_id.split("_")[0],
            "execution_mode": "observed_leveraged_etf",
            "leverage": 3.0 if "3X" in execution_id else 2.0,
            "result_type": result_type,
            "start_date": "2010-01-01",
            "end_date": "2020-01-01",
            "years": 10.0,
            "ending_equity": ending_equity,
            "total_return": ending_equity / 100000.0 - 1.0,
            "CAGR": cagr,
            "annualized_volatility": 0.25,
            "sharpe_ratio": 0.80,
            "sortino_ratio": 0.90,
            "calmar_ratio": calmar,
            "max_drawdown": max_drawdown,
            "max_recovery_days": 800,
            "exposure_pct": 0.75,
            "trades_per_year": 6.0,
            "trade_count": 60,
            "round_trip_count": 30,
            "average_hold_days": 50.0,
            "win_rate_by_trade": 0.35,
            "profit_factor": 2.0,
            "worst_year": -0.20,
        }


if __name__ == "__main__":
    unittest.main()
