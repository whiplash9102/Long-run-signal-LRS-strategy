#!/usr/bin/env python3
"""Run walk-forward validation for one or more signal tickers.

Usage
-----
# SPY only (default for Phase 7 baseline):
python scripts/run_walk_forward.py --tickers SPY

# All configured tickers:
python scripts/run_walk_forward.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.backtest.walk_forward import run_walk_forward


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Walk-forward validation for the Gayed LRS strategy."
    )
    parser.add_argument(
        "--config",
        default="config/gayed_lrs_parameters.yaml",
        help="Path to YAML config file.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        metavar="TICKER",
        help="Signal tickers to validate (e.g. SPY QQQ). Defaults to all.",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    print(f"Running walk-forward validation...")
    if args.tickers:
        print(f"  Signal tickers : {args.tickers}")
    else:
        print(f"  Signal tickers : all configured")

    wf_cfg = config["backtest"]["walk_forward"]
    print(f"  Train window   : {wf_cfg['training_window_years']} years")
    print(f"  Test window    : {wf_cfg['test_window_years']} years")
    print(f"  Step           : {wf_cfg['step_months']} months")
    print()

    outputs = run_walk_forward(config=config, signal_tickers=args.tickers)

    print("Done. Output files:")
    print(f"  Results       → {outputs.results}")
    print(f"  Filter scores → {outputs.filter_scores}")
    print(f"  Summary       → {outputs.summary}")

    # Print summary to console
    import pandas as pd
    summary = pd.read_csv(outputs.summary)
    if not summary.empty:
        print()
        print("Walk-Forward Summary")
        print("=" * 70)
        print(summary.to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
