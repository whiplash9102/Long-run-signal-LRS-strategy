from __future__ import annotations

import unittest

import pandas as pd

from src.reporting.false_breakout_gate_scan import scan_false_breakout_gates


class FalseBreakoutGateScanTest(unittest.TestCase):
    def test_scan_ranks_simple_gate_candidates(self) -> None:
        entries = pd.DataFrame(
            {
                "whipsaw": [True, True, False, False],
                "exit_date": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
                "entry_distance_pct": [0.001, 0.006, 0.010, 0.014],
                "filter_slope_pct": [-0.001, 0.0006, 0.0008, 0.0012],
                "trade_return_pct": [-0.01, -0.02, 0.05, 0.08],
            }
        )

        candidates = scan_false_breakout_gates(entries, min_acceptance_rate=0.5)

        self.assertFalse(candidates.empty)
        self.assertIn("recommended", candidates.columns)
        self.assertTrue(candidates.iloc[0]["acceptance_rate"] <= 1.0)
        self.assertGreaterEqual(candidates.iloc[0]["whipsaw_reduction"], 0.0)


if __name__ == "__main__":
    unittest.main()

