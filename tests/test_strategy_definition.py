from __future__ import annotations

import unittest

from src.config_loader import ConfigValidationError, load_config, validate_config
from src.strategy.definition import StrategyDefinition


class StrategyDefinitionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config("config/gayed_lrs_parameters.yaml")

    def test_strategy_declaration_contains_expected_universe(self) -> None:
        strategy = StrategyDefinition.from_config(self.config)
        self.assertEqual(
            [asset.ticker for asset in strategy.test_universe],
            ["SPY", "QQQ", "IWM", "VGK", "EZU"],
        )

    def test_phase_1_false_breakout_filter_is_disabled(self) -> None:
        strategy = StrategyDefinition.from_config(self.config)
        self.assertFalse(strategy.false_breakout.trading_filter_enabled)
        self.assertTrue(strategy.false_breakout.diagnostics_enabled)

    def test_strategy_declaration_contains_leveraged_execution_map(self) -> None:
        strategy = StrategyDefinition.from_config(self.config)
        mapping = {
            item.signal_ticker: [asset.id for asset in item.execution_assets]
            for item in strategy.leveraged_execution
        }

        self.assertEqual(mapping["SPY"], ["SPY_1X", "SSO_2X", "UPRO_3X"])
        self.assertEqual(mapping["QQQ"], ["QQQ_1X", "QLD_2X", "TQQQ_3X"])
        self.assertEqual(mapping["IWM"], ["IWM_1X", "UWM_2X", "TNA_3X"])
        self.assertIn("VGK_SYNTHETIC_3X", mapping["VGK"])

    def test_config_rejects_short_selling(self) -> None:
        bad_config = dict(self.config)
        bad_config["strategy"] = dict(self.config["strategy"])
        bad_config["strategy"]["allow_short"] = True
        with self.assertRaises(ConfigValidationError):
            validate_config(bad_config)


if __name__ == "__main__":
    unittest.main()
