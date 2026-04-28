#!/usr/bin/env python3
"""Build moving-average indicators from processed adjusted prices."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.strategy.indicators import run_indicator_pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/gayed_lrs_parameters.yaml",
        help="Path to YAML config.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    outputs = run_indicator_pipeline(config)

    print("Built moving-average indicators.")
    print(f"- Indicators: {outputs.indicators}")
    print(f"- Indicator quality report: {outputs.quality_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
