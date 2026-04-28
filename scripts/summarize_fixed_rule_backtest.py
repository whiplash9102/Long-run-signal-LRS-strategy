#!/usr/bin/env python3
"""Build reader-friendly review outputs for the fixed-rule backtest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.reporting.fixed_rule_summary import run_fixed_rule_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/gayed_lrs_parameters.yaml",
        help="Path to YAML config.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    outputs = run_fixed_rule_summary(config)

    print("Built fixed-rule review outputs.")
    print(f"- Strategy rankings: {outputs.strategy_rankings}")
    print(f"- Observed leveraged rankings: {outputs.observed_leveraged_rankings}")
    print(f"- Best by signal: {outputs.best_by_signal}")
    print(f"- Strategy versus buy-and-hold: {outputs.strategy_vs_buy_hold}")
    print(f"- Review report: {outputs.review_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

