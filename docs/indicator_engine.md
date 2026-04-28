# Indicator Engine

## Purpose

This document explains how the moving-average indicators are calculated before signals are generated.

## Input

```text
data/processed/prices_adjusted.csv
```

The engine uses:

```text
adjusted_close
```

## ETF Universe

Indicators are calculated for the test ETFs only:

- `SPY`
- `QQQ`
- `IWM`
- `VGK`
- `EZU`

Execution ETFs such as `SSO`, `UPRO`, `QLD`, `TQQQ`, `UWM`, and `TNA` do not get signal indicators.

The signal always comes from the normal ETF.

`BIL` is not given trading indicators because it is only an optional risk-off comparison asset.

## Filters

Candidate filters:

- `SMA_200`
- `EMA_190`
- `EMA_195`
- `EMA_200`

Sensitivity filters:

- `EMA_180`
- `EMA_185`
- `EMA_205`
- `EMA_210`

The sensitivity list does not duplicate filters already in the candidate list.

## Calculation Rules

SMA:

```text
rolling mean over N adjusted closes
```

EMA:

```text
pandas ewm(span=N, adjust=False, min_periods=N).mean()
```

This means EMA values are hidden during warmup and become valid only after `N` observations.

## Outputs

```text
data/processed/indicators.csv
data/processed/indicator_quality_report.csv
```

`indicators.csv` is long-format:

```text
date,ticker,filter_id,filter_type,filter_length,filter_value,filter_is_valid
```

`indicator_quality_report.csv` summarizes:

- Total rows.
- Valid rows.
- Warmup rows.
- First valid date.
- Last valid date.

## Review Checklist

- Confirm each test ETF appears.
- Confirm leveraged execution ETFs do not appear.
- Confirm `BIL` does not appear.
- Confirm `SMA_200` first valid date occurs after 200 observations.
- Confirm EMA filters have consistent warmup behavior.
