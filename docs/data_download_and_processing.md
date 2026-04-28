# Data Download And Processing

## Purpose

This document explains the first data layer output so it can be reviewed before we build indicators or signals.

## Universe

The downloader reads signal, execution, and comparison assets from `config/gayed_lrs_parameters.yaml`.

Signal ETFs:

- `SPY`
- `QQQ`
- `IWM`
- `VGK`
- `EZU`

Observed leveraged execution ETFs:

- `SSO`
- `UPRO`
- `QLD`
- `TQQQ`
- `UWM`
- `TNA`

Risk-off comparison asset:

- `BIL`

Primary risk-off for the profitability experiment is `CASH`, which does not need market data.

## Source

Configured source:

```text
yfinance
```

The raw data is daily OHLCV data.

## Adjusted Prices

The strategy uses adjusted close for signals and returns.

Because execution is configured as `next_session_open`, the data layer also creates an adjusted open:

```text
adjusted_open = open * (adjusted_close / close)
```

The same adjustment ratio is applied to high and low for consistency.

## Outputs

```text
data/raw/prices_raw.csv
data/processed/prices_adjusted.csv
data/processed/returns_daily.csv
data/processed/risk_off_returns.csv
data/processed/data_quality_report.csv
```

## File Meanings

`prices_raw.csv`

- Long-format raw OHLCV data from the source.
- One row per date and ticker.

`prices_adjusted.csv`

- Raw OHLCV plus adjusted open, high, low, close, and adjustment ratio.
- This is the main input for indicators and backtests.

`returns_daily.csv`

- Close-to-close adjusted daily return per ticker.

`risk_off_returns.csv`

- Uses `CASH` with `0.0` daily return for the primary profitability experiment.
- `BIL` data is still downloaded so a later comparison can be run.

`data_quality_report.csv`

- First and last available date per ticker.
- Row counts.
- Missing field counts.
- Date where each ticker has enough warmup bars.

## Review Checklist

- Confirm every expected ticker appears.
- Confirm first dates make sense because ETFs launched at different times.
- Confirm missing values are limited and visible in the quality report.
- Confirm leveraged ETFs have shorter histories than the normal signal ETFs.
- Confirm `BIL` is available for optional comparison, not primary evaluation.
