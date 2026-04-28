"""Signal engine for the Gayed LRS project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


LONG = "LONG"
RISK_OFF = "RISK_OFF"
WARMUP = "WARMUP"
BUY_ALERT = "BUY_ALERT"
EXIT_ALERT = "EXIT_ALERT"
NO_CHANGE = "NO_CHANGE"


@dataclass(frozen=True)
class SignalOutputs:
    signals: Path
    quality_report: Path


def run_signal_pipeline(config: dict[str, Any]) -> SignalOutputs:
    prices_path = Path("data/processed/prices_adjusted.csv")
    indicators_path = Path("data/processed/indicators.csv")
    if not prices_path.exists():
        raise FileNotFoundError(f"Missing adjusted prices file: {prices_path}")
    if not indicators_path.exists():
        raise FileNotFoundError(f"Missing indicators file: {indicators_path}")

    prices = pd.read_csv(prices_path)
    indicators = pd.read_csv(indicators_path)
    tickers = [item["ticker"] for item in config["data"]["test_universe"]]

    signals = build_signals(
        prices=prices,
        indicators=indicators,
        tickers=tickers,
        signal_price_field=config["data"]["signal_price_field"],
        execution_price_field=config["data"]["execution_price_field"],
        initial_state=config["strategy"]["initial_state_before_first_valid_signal"].upper(),
        execution_timing=config["execution"]["execution_timing"],
        risk_off_asset=config["data"]["risk_off"]["primary_asset"],
    )
    quality_report = build_signal_quality_report(signals)

    outputs = SignalOutputs(
        signals=Path("data/processed/signals.csv"),
        quality_report=Path("data/processed/signal_quality_report.csv"),
    )
    outputs.signals.parent.mkdir(parents=True, exist_ok=True)
    outputs.quality_report.parent.mkdir(parents=True, exist_ok=True)
    signals.to_csv(outputs.signals, index=False)
    quality_report.to_csv(outputs.quality_report, index=False)
    return outputs


def build_signals(
    prices: pd.DataFrame,
    indicators: pd.DataFrame,
    tickers: list[str],
    signal_price_field: str,
    execution_price_field: str,
    initial_state: str,
    execution_timing: str,
    risk_off_asset: str,
) -> pd.DataFrame:
    """Convert indicator rows into regime states and trade events."""
    _require_columns(
        prices,
        ["date", "ticker", signal_price_field, execution_price_field],
        "prices",
    )
    _require_columns(
        indicators,
        ["date", "ticker", "filter_id", "filter_value", "filter_is_valid"],
        "indicators",
    )

    price_frame = _build_price_frame(
        prices=prices,
        tickers=tickers,
        signal_price_field=signal_price_field,
        execution_price_field=execution_price_field,
    )
    merged = indicators.merge(price_frame, on=["date", "ticker"], how="inner")
    merged = merged[merged["ticker"].isin(tickers)].copy()
    merged = merged.sort_values(["ticker", "filter_id", "date"]).reset_index(drop=True)

    frames: list[pd.DataFrame] = []
    for (_, _), group in merged.groupby(["ticker", "filter_id"], sort=True):
        frames.append(_build_group_signals(group, initial_state=initial_state))

    if not frames:
        raise ValueError("No signal rows were generated")

    signals = pd.concat(frames, ignore_index=True).sort_values(
        ["ticker", "filter_id", "date"]
    ).reset_index(drop=True)
    signals["execution_timing"] = execution_timing
    signals["execution_asset"] = signals["ticker"]
    signals["risk_off_asset"] = risk_off_asset

    columns = [
        "date",
        "ticker",
        "filter_id",
        "filter_type",
        "filter_length",
        "signal_price",
        "filter_value",
        "previous_state",
        "current_state",
        "signal_event",
        "signal_is_tradable",
        "next_execution_date",
        "next_execution_open",
        "execution_timing",
        "execution_asset",
        "risk_off_asset",
    ]
    return signals[columns]


def build_signal_quality_report(signals: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = signals.groupby(["ticker", "filter_id"], sort=True)
    for (ticker, filter_id), group in grouped:
        tradable = group[group["signal_is_tradable"]]
        rows.append(
            {
                "ticker": ticker,
                "filter_id": filter_id,
                "total_rows": len(group),
                "tradable_rows": int(group["signal_is_tradable"].sum()),
                "warmup_rows": int((group["current_state"] == WARMUP).sum()),
                "buy_alerts": int((group["signal_event"] == BUY_ALERT).sum()),
                "exit_alerts": int((group["signal_event"] == EXIT_ALERT).sum()),
                "no_change_rows": int((group["signal_event"] == NO_CHANGE).sum()),
                "first_tradable_date": tradable["date"].min() if not tradable.empty else None,
                "last_tradable_date": tradable["date"].max() if not tradable.empty else None,
            }
        )
    return pd.DataFrame(rows)


def _build_price_frame(
    prices: pd.DataFrame,
    tickers: list[str],
    signal_price_field: str,
    execution_price_field: str,
) -> pd.DataFrame:
    price_frame = prices.loc[
        prices["ticker"].isin(tickers),
        ["date", "ticker", signal_price_field, execution_price_field],
    ].copy()
    price_frame = price_frame.dropna(subset=[signal_price_field, execution_price_field])
    price_frame = price_frame.sort_values(["ticker", "date"]).reset_index(drop=True)
    price_frame["next_execution_date"] = price_frame.groupby("ticker")["date"].shift(-1)
    price_frame["next_execution_open"] = price_frame.groupby("ticker")[execution_price_field].shift(-1)
    price_frame = price_frame.rename(columns={signal_price_field: "signal_price"})
    return price_frame[[
        "date",
        "ticker",
        "signal_price",
        "next_execution_date",
        "next_execution_open",
    ]]


def _build_group_signals(group: pd.DataFrame, initial_state: str) -> pd.DataFrame:
    result = group.copy()
    result["current_state"] = WARMUP
    valid = result["filter_is_valid"].astype(bool)
    result.loc[valid & (result["signal_price"] > result["filter_value"]), "current_state"] = LONG
    result.loc[valid & (result["signal_price"] <= result["filter_value"]), "current_state"] = RISK_OFF

    previous_states: list[str] = []
    events: list[str] = []
    prior_valid_state: str | None = None

    for row in result.itertuples(index=False):
        current_state = row.current_state
        if current_state == WARMUP:
            previous_states.append(WARMUP)
            events.append(NO_CHANGE)
            continue

        previous_state = prior_valid_state or initial_state
        previous_states.append(previous_state)
        events.append(_event_from_states(previous_state, current_state))
        prior_valid_state = current_state

    result["previous_state"] = previous_states
    result["signal_event"] = events
    result["signal_is_tradable"] = valid & result["next_execution_date"].notna()
    return result


def _event_from_states(previous_state: str, current_state: str) -> str:
    if previous_state == RISK_OFF and current_state == LONG:
        return BUY_ALERT
    if previous_state == LONG and current_state == RISK_OFF:
        return EXIT_ALERT
    return NO_CHANGE


def _require_columns(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")
