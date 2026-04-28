#!/usr/bin/env python3
"""Download and process market data for the configured ETF universe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.data.market_data import run_data_pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/gayed_lrs_parameters.yaml",
        help="Path to YAML config.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    outputs = run_data_pipeline(config)

    print("Downloaded and processed market data.")
    print(f"- Raw prices: {outputs.raw_prices}")
    print(f"- Adjusted prices: {outputs.adjusted_prices}")
    print(f"- Daily returns: {outputs.daily_returns}")
    print(f"- Risk-off returns: {outputs.risk_off_returns}")
    print(f"- Data quality report: {outputs.quality_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
