#!/usr/bin/env python3
"""Run EMA sensitivity review (Phase 8).

Usage
-----
# SPY only:
python scripts/run_sensitivity.py --tickers SPY

# All tickers:
python scripts/run_sensitivity.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.backtest.sensitivity import run_sensitivity_review, compute_stability
import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EMA sensitivity review for the Gayed LRS strategy."
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
        help="Signal tickers to review. Defaults to all.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    sens_cfg = config["strategy"]["sensitivity_filters"]
    print(f"Running EMA sensitivity review...")
    if args.tickers:
        print(f"  Signal tickers : {args.tickers}")
    else:
        print(f"  Signal tickers : all configured")
    print(
        f"  EMA range      : {sens_cfg['min_length']}–{sens_cfg['max_length']} "
        f"(step {sens_cfg['step']})"
    )
    print()

    outputs = run_sensitivity_review(config=config, signal_tickers=args.tickers)

    print("Done. Output files:")
    print(f"  Sensitivity metrics → {outputs.metrics}")
    print(f"  Sensitivity report  → {outputs.report}")

    # Print stability summary to console
    results = pd.read_csv(outputs.metrics)
    candidate_ids = [item["id"] for item in config["strategy"]["candidate_filters"]]
    stability = compute_stability(results)

    print()
    print("EMA Sensitivity — Stability Summary")
    print("=" * 60)
    print(stability.to_string(index=False))

    print()
    print("Per-ticker detail (sorted by EMA length):")
    print("-" * 60)
    for ticker, grp in results.groupby("signal_ticker"):
        print(f"\n  {ticker}:")
        print(f"  {'Filter':<12} {'CAGR':>8} {'Calmar':>8} {'Sharpe':>8}  Candidate?")
        print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8}  ----------")
        for _, row in grp.sort_values("ema_length").iterrows():
            marker = "  ← YES" if row["filter_id"] in candidate_ids else ""
            cagr_str = f"{row['CAGR']*100:.2f}%" if pd.notna(row["CAGR"]) else "n/a"
            calmar_str = f"{row['calmar_ratio']:.4f}" if pd.notna(row["calmar_ratio"]) else "n/a"
            sharpe_str = f"{row['sharpe_ratio']:.4f}" if pd.notna(row["sharpe_ratio"]) else "n/a"
            print(f"  {row['filter_id']:<12} {cagr_str:>8} {calmar_str:>8} {sharpe_str:>8}{marker}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
