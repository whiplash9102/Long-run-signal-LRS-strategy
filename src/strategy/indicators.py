"""Moving-average indicator engine for the Gayed LRS project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class IndicatorFilter:
    id: str
    type: str
    length: int


@dataclass(frozen=True)
class IndicatorOutputs:
    indicators: Path
    quality_report: Path


def run_indicator_pipeline(config: dict[str, Any]) -> IndicatorOutputs:
    prices_path = Path("data/processed/prices_adjusted.csv")
    if not prices_path.exists():
        raise FileNotFoundError(f"Missing adjusted prices file: {prices_path}")

    prices = pd.read_csv(prices_path)
    tickers = [item["ticker"] for item in config["data"]["test_universe"]]
    filters = filters_from_config(config)
    price_field = config["data"]["signal_price_field"]

    indicators = build_indicators(
        prices=prices,
        tickers=tickers,
        filters=filters,
        price_field=price_field,
    )
    quality_report = build_indicator_quality_report(indicators)

    outputs = IndicatorOutputs(
        indicators=Path("data/processed/indicators.csv"),
        quality_report=Path("data/processed/indicator_quality_report.csv"),
    )
    outputs.indicators.parent.mkdir(parents=True, exist_ok=True)
    outputs.quality_report.parent.mkdir(parents=True, exist_ok=True)
    indicators.to_csv(outputs.indicators, index=False)
    quality_report.to_csv(outputs.quality_report, index=False)
    return outputs


def filters_from_config(config: dict[str, Any]) -> list[IndicatorFilter]:
    """Return unique configured filters, including EMA sensitivity checks."""
    filters: list[IndicatorFilter] = []
    seen_ids: set[str] = set()

    for item in config["strategy"]["candidate_filters"]:
        filter_spec = IndicatorFilter(
            id=item["id"],
            type=item["type"],
            length=int(item["length"]),
        )
        filters.append(filter_spec)
        seen_ids.add(filter_spec.id)

    sensitivity = config["strategy"]["sensitivity_filters"]
    sensitivity_type = sensitivity["type"]
    for length in range(
        int(sensitivity["min_length"]),
        int(sensitivity["max_length"]) + 1,
        int(sensitivity["step"]),
    ):
        filter_id = f"{sensitivity_type}_{length}"
        if filter_id in seen_ids:
            continue
        filters.append(IndicatorFilter(id=filter_id, type=sensitivity_type, length=length))
        seen_ids.add(filter_id)

    return filters


def build_indicators(
    prices: pd.DataFrame,
    tickers: list[str],
    filters: list[IndicatorFilter],
    price_field: str,
) -> pd.DataFrame:
    """Calculate all configured moving averages for each test ETF."""
    missing_columns = {"date", "ticker", price_field}.difference(prices.columns)
    if missing_columns:
        raise ValueError(f"Missing price columns: {sorted(missing_columns)}")

    clean_prices = prices.loc[prices["ticker"].isin(tickers), ["date", "ticker", price_field]].copy()
    clean_prices = clean_prices.dropna(subset=[price_field])
    clean_prices = clean_prices.sort_values(["ticker", "date"]).reset_index(drop=True)

    frames: list[pd.DataFrame] = []
    for ticker, ticker_prices in clean_prices.groupby("ticker", sort=True):
        close = ticker_prices[price_field].astype(float)
        for filter_spec in filters:
            values = calculate_filter(close, filter_spec)
            frame = ticker_prices[["date", "ticker"]].copy()
            frame["filter_id"] = filter_spec.id
            frame["filter_type"] = filter_spec.type
            frame["filter_length"] = filter_spec.length
            frame["filter_value"] = values
            frame["filter_is_valid"] = frame["filter_value"].notna()
            frames.append(frame)

    if not frames:
        raise ValueError("No indicator rows were generated")

    return pd.concat(frames, ignore_index=True).sort_values(
        ["ticker", "filter_id", "date"]
    ).reset_index(drop=True)


def calculate_filter(series: pd.Series, filter_spec: IndicatorFilter) -> pd.Series:
    if filter_spec.type == "SMA":
        return series.rolling(window=filter_spec.length, min_periods=filter_spec.length).mean()
    if filter_spec.type == "EMA":
        return series.ewm(
            span=filter_spec.length,
            adjust=False,
            min_periods=filter_spec.length,
        ).mean()
    raise ValueError(f"Unsupported filter type: {filter_spec.type}")


def build_indicator_quality_report(indicators: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = indicators.groupby(["ticker", "filter_id", "filter_type", "filter_length"], sort=True)
    for (ticker, filter_id, filter_type, filter_length), group in grouped:
        valid = group[group["filter_is_valid"]]
        rows.append(
            {
                "ticker": ticker,
                "filter_id": filter_id,
                "filter_type": filter_type,
                "filter_length": filter_length,
                "total_rows": len(group),
                "valid_rows": len(valid),
                "invalid_warmup_rows": len(group) - len(valid),
                "first_valid_date": valid["date"].min() if not valid.empty else None,
                "last_valid_date": valid["date"].max() if not valid.empty else None,
            }
        )
    return pd.DataFrame(rows)
