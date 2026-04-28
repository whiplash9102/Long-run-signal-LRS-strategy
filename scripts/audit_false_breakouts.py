#!/usr/bin/env python3
"""Build false-breakout diagnostics from the existing signal layer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.reporting.false_breakout_audit import run_false_breakout_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/gayed_lrs_parameters.yaml",
        help="Path to YAML config.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    outputs = run_false_breakout_audit(config)

    print("Built false-breakout audit outputs.")
    print(f"- Entry audit: {outputs.entries}")
    print(f"- Summary: {outputs.summary}")
    print(f"- Report: {outputs.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

