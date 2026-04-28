# False-Breakout Audit

## Purpose

This diagnostic layer measures how often a buy alert fails quickly.

It does not change the strategy. It only helps decide whether a false-breakout filter is worth adding later.

## Inputs

```text
data/processed/prices_adjusted.csv
data/processed/signals.csv
data/processed/indicators.csv
```

## Entry Label

Each `BUY_ALERT` is paired with the next `EXIT_ALERT` for the same `ticker` and `filter_id`.

A whipsaw is defined as a completed round trip that exits within the configured session window.

## Entry Features

The audit records these entry conditions:

- distance from filter
- filter slope
- recent return
- recent annualized volatility

## Outputs

```text
reports/tables/false_breakout_audit_entries.csv
reports/tables/false_breakout_audit_summary.csv
reports/false_breakout_review.md
```

## Reading Rule

- High whipsaw rate with flat or negative slope suggests a filter could help.
- High whipsaw rate with small entry distance suggests the breakouts are weak.
- High whipsaw rate with high volatility suggests a regime filter may be useful.
- This is signal-level diagnostics only; it does not validate the leveraged execution layer yet.
