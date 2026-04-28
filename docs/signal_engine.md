# Signal Engine

## Purpose

This document explains how moving-average indicators become trading states and alerts.

## Inputs

```text
data/processed/prices_adjusted.csv
data/processed/indicators.csv
```

## States

`WARMUP`

- The moving average is not valid yet.
- No trade can be taken.

`LONG`

- The ETF adjusted close is above the selected filter.

`RISK_OFF`

- The ETF adjusted close is at or below the selected filter.

## Events

`BUY_ALERT`

- Previous valid state was `RISK_OFF`.
- Current valid state is `LONG`.

`EXIT_ALERT`

- Previous valid state was `LONG`.
- Current valid state is `RISK_OFF`.

`NO_CHANGE`

- State did not change, or row is still in warmup.

## Initial State

Before the first valid filter value, the system assumes the previous valid state is:

```text
RISK_OFF
```

That means if the first valid row is already above the filter, the engine creates a `BUY_ALERT`.

## Execution Fields

The signal is confirmed on the current close.

Execution is configured as:

```text
next_session_open
```

So the output includes:

- `next_execution_date`
- `next_execution_open`

## Outputs

```text
data/processed/signals.csv
data/processed/signal_quality_report.csv
```

`signals.csv` is long-format:

```text
date,ticker,filter_id,signal_price,filter_value,previous_state,current_state,signal_event,next_execution_date,next_execution_open
```

`signal_quality_report.csv` summarizes:

- Warmup rows.
- Tradable rows.
- Buy alerts.
- Exit alerts.
- First tradable date.
- Last tradable date.

## Review Checklist

- Confirm warmup rows do not create trades.
- Confirm equality with the filter is `RISK_OFF`.
- Confirm buy alerts only occur when moving from risk-off to long.
- Confirm exit alerts only occur when moving from long to risk-off.
- Confirm each alert has a next execution date and open price.
