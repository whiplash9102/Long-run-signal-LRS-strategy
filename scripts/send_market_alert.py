#!/usr/bin/env python3
"""Build and optionally send the daily market alert email."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alerts.market_alert import (  # noqa: E402
    EmailSettings,
    build_market_alert,
    is_us_market_open_now,
    send_email,
    write_alert_outputs,
)
from src.config_loader import load_config  # noqa: E402
from src.data.market_data import run_data_pipeline, run_data_pipeline_incremental  # noqa: E402
from src.strategy.indicators import run_indicator_pipeline  # noqa: E402
from src.strategy.signals import run_signal_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/gayed_lrs_parameters.yaml")
    parser.add_argument("--output-dir", default="outputs/alerts")
    parser.add_argument("--tickers", help="Comma-separated signal tickers. Defaults to config universe.")
    parser.add_argument("--filter-ids", help="Comma-separated filter IDs. Defaults to config candidates.")
    parser.add_argument("--market-date", help="Override market date as YYYY-MM-DD.")
    parser.add_argument("--force-market", action="store_true", help="Send/build even if market is closed.")
    parser.add_argument("--no-refresh", action="store_true", help="Use existing processed CSV files.")
    parser.add_argument("--full-refresh", action="store_true", help="Force full historical re-download (slow). Default is incremental.")
    parser.add_argument("--dry-run", action="store_true", help="Print and write output without sending email.")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    if not args.force_market and not is_us_market_open_now(now):
        print("US market is not open now; no alert email sent.")
        return 0

    config = load_config(args.config)
    if not args.no_refresh:
        if args.full_refresh:
            run_data_pipeline(config)
        else:
            run_data_pipeline_incremental(config)
        run_indicator_pipeline(config)
        run_signal_pipeline(config)

    prices = pd.read_csv("data/processed/prices_adjusted.csv")
    indicators = pd.read_csv("data/processed/indicators.csv")
    signals = pd.read_csv("data/processed/signals.csv")

    market_date = date.fromisoformat(args.market_date) if args.market_date else None
    tickers = _split_csv(args.tickers)
    filter_ids = _split_csv(args.filter_ids)

    alert = build_market_alert(
        config=config,
        prices=prices,
        indicators=indicators,
        signals=signals,
        generated_at=now,
        market_date=market_date,
        tickers=tickers,
        filter_ids=filter_ids,
    )
    json_path, text_path = write_alert_outputs(alert, args.output_dir)
    print(alert.text_body)
    print(f"\nWrote alert JSON: {json_path}")
    print(f"Wrote alert text: {text_path}")

    if args.dry_run:
        print("Dry run: email not sent.")
        return 0

    send_email(alert, EmailSettings.from_env())
    print("Alert email sent.")
    return 0


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())

