#!/usr/bin/env python3
"""Run the fixed-rule leveraged ETF backtest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.fixed_rule import run_fixed_rule_backtest
from src.config_loader import load_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/gayed_lrs_parameters.yaml",
        help="Path to YAML config.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    outputs = run_fixed_rule_backtest(config)

    print("Ran fixed-rule leveraged backtest.")
    print(f"- Equity curves: {outputs.equity_curves}")
    print(f"- Trades: {outputs.trades}")
    print(f"- Metrics: {outputs.metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
