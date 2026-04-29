"""Market data download and processing for the Gayed LRS project."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf


RAW_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adjusted_close",
    "Volume": "volume",
}


@dataclass(frozen=True)
class DataOutputs:
    raw_prices: Path
    adjusted_prices: Path
    daily_returns: Path
    risk_off_returns: Path
    quality_report: Path


def run_data_pipeline(config: dict[str, Any]) -> DataOutputs:
    data_config = config["data"]
    tickers = _tickers_from_config(config)
    start_date = data_config["start_date"]
    end_date = None if data_config["end_date"] == "latest_available" else data_config["end_date"]

    raw_prices = download_ohlcv(tickers=tickers, start=start_date, end=end_date)
    adjusted_prices = build_adjusted_prices(raw_prices)
    daily_returns = build_daily_returns(adjusted_prices)
    risk_off_returns = build_risk_off_returns(
        adjusted_prices=adjusted_prices,
        primary_asset=data_config["risk_off"]["primary_asset"],
        fallback_asset=data_config["risk_off"]["fallback_asset"],
        cash_daily_return=float(data_config["risk_off"]["cash_daily_return"]),
    )
    quality_report = build_data_quality_report(
        raw_prices=raw_prices,
        adjusted_prices=adjusted_prices,
        tickers=tickers,
        warmup_bars=int(data_config["warmup_bars"]),
    )

    outputs = DataOutputs(
        raw_prices=Path("data/raw/prices_raw.csv"),
        adjusted_prices=Path("data/processed/prices_adjusted.csv"),
        daily_returns=Path("data/processed/returns_daily.csv"),
        risk_off_returns=Path("data/processed/risk_off_returns.csv"),
        quality_report=Path("data/processed/data_quality_report.csv"),
    )
    write_data_outputs(
        outputs=outputs,
        raw_prices=raw_prices,
        adjusted_prices=adjusted_prices,
        daily_returns=daily_returns,
        risk_off_returns=risk_off_returns,
        quality_report=quality_report,
    )
    return outputs


def download_ohlcv(tickers: list[str], start: str, end: str | None = None) -> pd.DataFrame:
    """Download daily OHLCV data and return a long-format dataframe."""
    downloaded = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=False,
        actions=False,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    if downloaded.empty:
        raise ValueError("Downloaded market data is empty")

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        if isinstance(downloaded.columns, pd.MultiIndex):
            if ticker not in downloaded.columns.get_level_values(0):
                frames.append(_empty_raw_frame(ticker))
                continue
            ticker_frame = downloaded[ticker].copy()
        else:
            ticker_frame = downloaded.copy()

        ticker_frame = ticker_frame.rename(columns=RAW_COLUMNS)
        ticker_frame = ticker_frame[[column for column in RAW_COLUMNS.values() if column in ticker_frame]]
        ticker_frame = ticker_frame.dropna(how="all", subset=ticker_frame.columns)
        ticker_frame.index.name = "date"
        ticker_frame = ticker_frame.reset_index()
        ticker_frame.insert(1, "ticker", ticker)
        frames.append(ticker_frame)

    result = pd.concat(frames, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"]).dt.date
    return result.sort_values(["ticker", "date"]).reset_index(drop=True)


def build_adjusted_prices(raw_prices: pd.DataFrame) -> pd.DataFrame:
    """Create adjusted open/high/low/close fields from raw OHLCV data."""
    prices = raw_prices.dropna(subset=["open", "close", "adjusted_close"]).copy()
    adjustment_ratio = prices["adjusted_close"] / prices["close"]

    prices["adjustment_ratio"] = adjustment_ratio
    prices["adjusted_open"] = prices["open"] * adjustment_ratio
    prices["adjusted_high"] = prices["high"] * adjustment_ratio
    prices["adjusted_low"] = prices["low"] * adjustment_ratio

    columns = [
        "date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "adjusted_open",
        "adjusted_high",
        "adjusted_low",
        "adjusted_close",
        "volume",
        "adjustment_ratio",
    ]
    return prices[columns].sort_values(["ticker", "date"]).reset_index(drop=True)


def build_daily_returns(adjusted_prices: pd.DataFrame) -> pd.DataFrame:
    """Build close-to-close daily returns per ticker."""
    returns = adjusted_prices[["date", "ticker", "adjusted_close"]].copy()
    returns["daily_return"] = returns.groupby("ticker")["adjusted_close"].pct_change()
    return returns[["date", "ticker", "daily_return"]].sort_values(
        ["ticker", "date"]
    ).reset_index(drop=True)


def build_risk_off_returns(
    adjusted_prices: pd.DataFrame,
    primary_asset: str,
    fallback_asset: str,
    cash_daily_return: float,
) -> pd.DataFrame:
    """Build risk-off return series with CASH fallback before BIL exists."""
    all_dates = pd.DataFrame({"date": sorted(adjusted_prices["date"].unique())})
    if primary_asset == "CASH":
        result = all_dates.copy()
        result["risk_off_asset"] = "CASH"
        result["risk_off_return"] = cash_daily_return
        result["fallback_used"] = False
        return result[["date", "risk_off_asset", "risk_off_return", "fallback_used"]]

    primary = adjusted_prices.loc[
        adjusted_prices["ticker"] == primary_asset, ["date", "adjusted_close"]
    ].copy()
    primary["risk_off_return"] = primary["adjusted_close"].pct_change()
    primary["risk_off_return"] = primary["risk_off_return"].fillna(cash_daily_return)
    primary["risk_off_asset"] = primary_asset

    result = all_dates.merge(primary[["date", "risk_off_asset", "risk_off_return"]], on="date", how="left")

    missing = result["risk_off_return"].isna()
    result.loc[missing, "risk_off_asset"] = fallback_asset
    result.loc[missing, "risk_off_return"] = cash_daily_return
    result["fallback_used"] = result["risk_off_asset"].eq(fallback_asset)
    return result[["date", "risk_off_asset", "risk_off_return", "fallback_used"]]


def build_data_quality_report(
    raw_prices: pd.DataFrame,
    adjusted_prices: pd.DataFrame,
    tickers: list[str],
    warmup_bars: int,
) -> pd.DataFrame:
    """Summarize availability and missing data by ticker."""
    rows: list[dict[str, Any]] = []
    expected_dates = sorted(raw_prices["date"].dropna().unique())
    expected_rows = len(expected_dates)
    for ticker in tickers:
        raw = raw_prices[raw_prices["ticker"] == ticker]
        adjusted = adjusted_prices[adjusted_prices["ticker"] == ticker]
        valid_signal = adjusted.dropna(subset=["adjusted_close"])
        warmup_ready_date = (
            valid_signal.iloc[warmup_bars - 1]["date"]
            if len(valid_signal) >= warmup_bars
            else None
        )
        rows.append(
            {
                "ticker": ticker,
                "first_date": valid_signal["date"].min() if not valid_signal.empty else None,
                "last_date": valid_signal["date"].max() if not valid_signal.empty else None,
                "expected_rows_from_project_start": expected_rows,
                "raw_rows": len(raw),
                "valid_adjusted_close_rows": len(valid_signal),
                "unavailable_or_missing_rows": expected_rows - len(valid_signal),
                "missing_open": int(raw["open"].isna().sum()) if "open" in raw else len(raw),
                "missing_close": int(raw["close"].isna().sum()) if "close" in raw else len(raw),
                "missing_adjusted_close": int(raw["adjusted_close"].isna().sum())
                if "adjusted_close" in raw
                else len(raw),
                "warmup_bars": warmup_bars,
                "warmup_ready_date": warmup_ready_date,
            }
        )
    return pd.DataFrame(rows)


def write_data_outputs(
    outputs: DataOutputs,
    raw_prices: pd.DataFrame,
    adjusted_prices: pd.DataFrame,
    daily_returns: pd.DataFrame,
    risk_off_returns: pd.DataFrame,
    quality_report: pd.DataFrame,
) -> None:
    for path in (
        outputs.raw_prices,
        outputs.adjusted_prices,
        outputs.daily_returns,
        outputs.risk_off_returns,
        outputs.quality_report,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    raw_prices.to_csv(outputs.raw_prices, index=False)
    adjusted_prices.to_csv(outputs.adjusted_prices, index=False)
    daily_returns.to_csv(outputs.daily_returns, index=False)
    risk_off_returns.to_csv(outputs.risk_off_returns, index=False)
    quality_report.to_csv(outputs.quality_report, index=False)


def run_data_pipeline_incremental(config: dict[str, Any]) -> DataOutputs:
    """Incremental update: only download data newer than what's already saved.

    Falls back to a full download if no existing raw CSV is found.
    Uses a 7-day overlap window to capture dividend adjustments and weekend gaps.
    """
    raw_path = Path("data/raw/prices_raw.csv")
    if not raw_path.exists():
        return run_data_pipeline(config)

    existing_raw = pd.read_csv(raw_path)
    existing_raw["date"] = pd.to_datetime(existing_raw["date"]).dt.date
    last_date = existing_raw["date"].max()
    download_start = last_date - timedelta(days=7)

    data_config = config["data"]
    tickers = _tickers_from_config(config)
    end_date = None if data_config["end_date"] == "latest_available" else data_config["end_date"]

    new_raw = download_ohlcv(tickers=tickers, start=str(download_start), end=end_date)

    old_data = existing_raw[existing_raw["date"] < download_start]
    merged_raw = (
        pd.concat([old_data, new_raw], ignore_index=True)
        .sort_values(["ticker", "date"])
        .drop_duplicates(subset=["ticker", "date"], keep="last")
        .reset_index(drop=True)
    )

    adjusted_prices = build_adjusted_prices(merged_raw)
    daily_returns = build_daily_returns(adjusted_prices)
    risk_off_returns = build_risk_off_returns(
        adjusted_prices=adjusted_prices,
        primary_asset=data_config["risk_off"]["primary_asset"],
        fallback_asset=data_config["risk_off"]["fallback_asset"],
        cash_daily_return=float(data_config["risk_off"]["cash_daily_return"]),
    )
    quality_report = build_data_quality_report(
        raw_prices=merged_raw,
        adjusted_prices=adjusted_prices,
        tickers=tickers,
        warmup_bars=int(data_config["warmup_bars"]),
    )

    outputs = DataOutputs(
        raw_prices=Path("data/raw/prices_raw.csv"),
        adjusted_prices=Path("data/processed/prices_adjusted.csv"),
        daily_returns=Path("data/processed/returns_daily.csv"),
        risk_off_returns=Path("data/processed/risk_off_returns.csv"),
        quality_report=Path("data/processed/data_quality_report.csv"),
    )
    write_data_outputs(
        outputs=outputs,
        raw_prices=merged_raw,
        adjusted_prices=adjusted_prices,
        daily_returns=daily_returns,
        risk_off_returns=risk_off_returns,
        quality_report=quality_report,
    )
    return outputs


def _tickers_from_config(config: dict[str, Any]) -> list[str]:
    universe = [item["ticker"] for item in config["data"]["test_universe"]]
    execution_tickers = [
        asset["ticker"]
        for mapping in config["data"].get("leveraged_execution", [])
        for asset in mapping.get("execution_assets", [])
        if asset.get("ticker")
    ]
    risk_off_config = config["data"]["risk_off"]
    risk_off_tickers = [
        ticker
        for ticker in [
            risk_off_config.get("primary_asset"),
            *risk_off_config.get("comparison_assets", []),
        ]
        if ticker and ticker != "CASH"
    ]
    return list(dict.fromkeys([*universe, *execution_tickers, *risk_off_tickers]))


def _empty_raw_frame(ticker: str) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "ticker",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "volume",
        ]
    ).assign(ticker=ticker)
