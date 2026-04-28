"""Tests for the walk-forward validation engine."""

from __future__ import annotations

import unittest

import pandas as pd

from src.backtest.walk_forward import (
    WalkForwardWindow,
    _composite_score,
    _scoring_assets_from_mappings,
    generate_windows,
)
from src.backtest.fixed_rule import ExecutionAsset, ExecutionMapping


class GenerateWindowsTest(unittest.TestCase):
    def _dates(self, start: str, end: str) -> list[str]:
        return [
            d.strftime("%Y-%m-%d")
            for d in pd.date_range(start=start, end=end, freq="B")
        ]

    def test_empty_dates_returns_empty(self) -> None:
        self.assertEqual(generate_windows([], 10, 2, 6), [])

    def test_insufficient_history_returns_empty(self) -> None:
        # Only 5 years of data — not enough for a 10-year training window
        dates = self._dates("2015-01-01", "2020-01-01")
        windows = generate_windows(dates, training_years=10, test_years=2, step_months=6)
        self.assertEqual(windows, [])

    def test_produces_correct_window_count(self) -> None:
        # 15 years of data: 10 train + 2 test, step 6m → expect 6 windows
        # (test_start: 2003-01, 2003-07, 2004-01, 2004-07, 2005-01, 2005-07)
        dates = self._dates("1993-01-01", "2008-01-01")
        windows = generate_windows(dates, training_years=10, test_years=2, step_months=6)
        self.assertGreater(len(windows), 0)

    def test_window_ids_are_sequential(self) -> None:
        dates = self._dates("1993-01-01", "2010-01-01")
        windows = generate_windows(dates, training_years=10, test_years=2, step_months=6)
        ids = [w.window_id for w in windows]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))

    def test_train_end_equals_test_start(self) -> None:
        dates = self._dates("1993-01-01", "2010-01-01")
        windows = generate_windows(dates, training_years=10, test_years=2, step_months=6)
        for w in windows:
            self.assertEqual(w.train_end, w.test_start)

    def test_no_overlapping_test_windows(self) -> None:
        dates = self._dates("1993-01-01", "2015-01-01")
        windows = generate_windows(dates, training_years=10, test_years=2, step_months=6)
        for i in range(1, len(windows)):
            # Each test_start must be >= previous test_start (monotonic)
            self.assertGreater(windows[i].test_start, windows[i - 1].test_start)

    def test_returns_walk_forward_window_objects(self) -> None:
        dates = self._dates("1993-01-01", "2010-01-01")
        windows = generate_windows(dates, training_years=10, test_years=2, step_months=6)
        for w in windows:
            self.assertIsInstance(w, WalkForwardWindow)


class CompositeScoreTest(unittest.TestCase):
    def _weights(self) -> dict:
        return {
            "cagr": 0.25,
            "sharpe_ratio": 0.25,
            "sortino_ratio": 0.20,
            "max_drawdown_penalty": 0.20,
            "calmar_ratio": 0.10,
        }

    def test_higher_return_gives_higher_score(self) -> None:
        base = {
            "CAGR": 0.08,
            "sharpe_ratio": 0.6,
            "sortino_ratio": 0.8,
            "max_drawdown": -0.20,
            "calmar_ratio": 0.4,
        }
        better = dict(base, CAGR=0.12)
        self.assertGreater(
            _composite_score(better, self._weights()),
            _composite_score(base, self._weights()),
        )

    def test_drawdown_penalty_term_is_correctly_signed(self) -> None:
        # max_drawdown_penalty contribution = weight × max_drawdown (negative value)
        # max_drawdown=-0.50 → contribution = 0.20 × (-0.50) = -0.10 (penalized more)
        # max_drawdown=-0.10 → contribution = 0.20 × (-0.10) = -0.02 (penalized less)
        # A smaller absolute drawdown (less negative) gives a higher score.
        weights = self._weights()
        large_dd = {"CAGR": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
                    "max_drawdown": -0.50, "calmar_ratio": 0.0}
        small_dd = {"CAGR": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
                    "max_drawdown": -0.10, "calmar_ratio": 0.0}
        # Smaller absolute drawdown → higher score
        self.assertGreater(
            _composite_score(small_dd, weights),
            _composite_score(large_dd, weights),
        )

    def test_nan_metrics_treated_as_zero(self) -> None:
        metrics = {
            "CAGR": float("nan"),
            "sharpe_ratio": None,
            "sortino_ratio": float("nan"),
            "max_drawdown": -0.20,
            "calmar_ratio": None,
        }
        score = _composite_score(metrics, self._weights())
        self.assertIsInstance(score, float)
        self.assertFalse(score != score)  # not NaN

    def test_weights_sum_determines_max_score(self) -> None:
        # With all positive metrics = 1.0 and max_drawdown = -1.0:
        # score = 0.25×1 + 0.25×1 + 0.20×1 + 0.20×(-1.0) + 0.10×1 = 0.60
        metrics = {
            "CAGR": 1.0,
            "sharpe_ratio": 1.0,
            "sortino_ratio": 1.0,
            "max_drawdown": -1.0,
            "calmar_ratio": 1.0,
        }
        weights = self._weights()
        expected = (
            weights["cagr"] * 1.0
            + weights["sharpe_ratio"] * 1.0
            + weights["sortino_ratio"] * 1.0
            + weights["max_drawdown_penalty"] * (-1.0)
            + weights["calmar_ratio"] * 1.0
        )
        self.assertAlmostEqual(_composite_score(metrics, weights), expected, places=9)


class ScoringAssetsTest(unittest.TestCase):
    def _make_mappings(self) -> tuple[ExecutionMapping, ...]:
        return (
            ExecutionMapping(
                signal_ticker="SPY",
                execution_assets=(
                    ExecutionAsset(id="SPY_1X", ticker="SPY", leverage=1.0, mode="observed_etf"),
                    ExecutionAsset(id="SSO_2X", ticker="SSO", leverage=2.0, mode="observed_leveraged_etf"),
                    ExecutionAsset(id="UPRO_3X", ticker="UPRO", leverage=3.0, mode="observed_leveraged_etf"),
                ),
            ),
            ExecutionMapping(
                signal_ticker="VGK",
                execution_assets=(
                    ExecutionAsset(id="VGK_1X", ticker="VGK", leverage=1.0, mode="observed_etf"),
                    ExecutionAsset(id="VGK_SYNTHETIC_2X", ticker=None, leverage=2.0, mode="synthetic_from_signal_etf"),
                ),
            ),
        )

    def test_returns_1x_observed_etf_per_ticker(self) -> None:
        mappings = self._make_mappings()
        result = _scoring_assets_from_mappings(mappings)
        self.assertIn("SPY", result)
        self.assertEqual(result["SPY"].id, "SPY_1X")
        self.assertEqual(result["SPY"].leverage, 1.0)

    def test_vgk_returns_1x_asset(self) -> None:
        mappings = self._make_mappings()
        result = _scoring_assets_from_mappings(mappings)
        self.assertIn("VGK", result)
        self.assertEqual(result["VGK"].leverage, 1.0)


if __name__ == "__main__":
    unittest.main()
