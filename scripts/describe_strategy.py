#!/usr/bin/env python3
"""Print or write the strategy declaration for review."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_config
from src.strategy.definition import StrategyDefinition


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/gayed_lrs_parameters.yaml",
        help="Path to YAML config.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional markdown output path.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    declaration = StrategyDefinition.from_config(config).to_markdown()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(declaration, encoding="utf-8")
        print(f"Wrote strategy declaration: {output_path}")
    else:
        print(declaration)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
