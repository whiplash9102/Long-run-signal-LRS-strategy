# False-Breakout Gate Scan

## Purpose

This step takes the false-breakout audit and tests a few simple gate candidates.

It does not change the trading rule yet. It only ranks simple entry gates by their effect on whipsaw rate and sample retention.

## Gate Definition

A gate accepts a buy alert only when both conditions are true:

- entry distance from filter is above a threshold
- filter slope is above a threshold

## Outputs

```text
reports/tables/false_breakout_gate_candidates.csv
reports/false_breakout_gate_review.md
```

## Reading Rule

- Prefer gates that reduce whipsaws without cutting too many entries.
- Use the recommended gate only if it is materially better than the baseline and still leaves enough sample size for validation.
