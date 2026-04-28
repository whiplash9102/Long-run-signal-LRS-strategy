# Gayed LRS Strategy Spec

## Purpose

This document answers one question:

What exactly are we trading, and how do we decide whether it is good enough?

The detailed parameter values live in:

```text
config/gayed_lrs_parameters.yaml
```

## 1. Strategy Idea

The source paper is `Gayed Bilello 2016.pdf`.

The paper's idea:

- Leverage works better when the market is above a moving average.
- Leverage works worse when the market is below a moving average.
- The paper uses simple moving averages, especially the `200-day SMA`.
- When the S&P 500 is below the moving average, the paper rotates to Treasury bills.

Our experiment is focused:

- Long-only.
- No shorting.
- Use normal ETFs as signal assets.
- Trade configured 1x, 2x, 3x, or synthetic execution assets when risk-on.
- Exit to `CASH` when the signal turns off.

## 2. Phase 1 Trading Rule

Baseline filter:

- `SMA 200`

Signal assets:

- `SPY`
- `QQQ`
- `IWM`
- `VGK`
- `EZU`

Execution assets:

- `SPY` signal: `SPY`, `SSO`, `UPRO`
- `QQQ` signal: `QQQ`, `QLD`, `TQQQ`
- `IWM` signal: `IWM`, `UWM`, `TNA`
- `VGK` signal: `VGK`, synthetic `2x`, synthetic `3x`
- `EZU` signal: `EZU`, synthetic `2x`, synthetic `3x`

Risk-off asset:

- Primary experiment: `CASH`
- Optional comparison later: `BIL`

Daily regime:

- `LONG` when the tested ETF closes above the selected moving average.
- `RISK_OFF` when the tested ETF closes at or below the selected moving average.

Design decision — signal source:

- Each ETF uses **its own price** versus **its own moving average** as the signal.
- Example: QQQ uses QQQ's close vs QQQ's 200-day SMA. IWM uses IWM's close vs IWM's SMA.
- This differs from the original Gayed-Bilello paper, which uses SPY as a single universal
  market regime indicator for all assets.
- Rationale: testing each ETF independently reveals which markets the trend-following rule
  works for, rather than assuming all markets are driven by the US S&P 500 regime.
- The SPY-as-universal-signal approach may be added as a comparison in a future phase.

Trade events:

- `BUY_ALERT`: previous regime was `RISK_OFF`, current regime is `LONG`.
- `EXIT_ALERT`: previous regime was `LONG`, current regime is `RISK_OFF`.
- `NO_CHANGE`: regime did not change.

Timing:

- Signal is confirmed only after the daily close.
- Trade executes on the next session.
- Do not trade on the same close that created the signal.

## 3. Filters To Test

The baseline stays fixed:

- `SMA 200`

Candidate variants:

- `EMA 190`
- `EMA 195`
- `EMA 200`

Sensitivity check:

- EMA `180` to `210`, step `5`.

Decision rule:

- Do not choose the best full-sample result blindly.
- Prefer a filter that performs consistently out of sample.
- If EMA does not clearly beat `SMA 200`, keep `SMA 200`.

## 4. ETF Universe To Test

`SPY` remains the paper baseline.

We will also test the same rule on a small ETF universe:

| Region | ETF | Exposure | Role |
| --- | --- | --- | --- |
| US | `SPY` | S&P 500 large-cap equities | Paper baseline |
| US | `QQQ` | Nasdaq-100 growth / technology-heavy equities | US variant |
| US | `IWM` | Russell 2000 small-cap equities | US variant |
| Europe | `VGK` | Developed Europe equities | Europe variant |
| Europe | `EZU` | Eurozone large- and mid-cap equities | Europe variant |

Important:

- Each ETF is tested independently first.
- We are not building a combined portfolio yet.
- The goal is to see whether the leveraged execution assets are profitable and risk-acceptable under the same moving-average rule.

## 5. Backtest Requirements

All filters must use the same:

- Data.
- Entry and exit rules.
- Execution timing.
- Cost assumptions.
- Risk-off rule.
- Position size.

Required outputs:

- Equity curve.
- Trade log.
- Daily returns.
- Daily exposure.
- Metrics table.
- Benchmark comparison versus buy-and-hold for the same execution asset where available.

Required metrics:

- CAGR.
- Annualized volatility.
- Sharpe.
- Sortino.
- Calmar.
- Max drawdown.
- Trades per year.
- Exposure percent.

## 6. Anti-Overfitting Requirements

We need two views:

- Fixed-rule test: each filter is tested over the full available period.
- Walk-forward test: choose the best filter on a training window, then test it on the next unseen window.

Walk-forward settings:

- Training window: `10 years`.
- Test window: `2 years`.
- Step size: `6 months`.

The final recommendation must answer:

- Did `SMA 200` work as expected?
- Did `EMA 190` or `EMA 195` improve results out of sample?
- Are EMA results stable across nearby values?
- Which signal/execution pair produces the best risk-adjusted result?
- Is real leveraged ETF exposure worth the drawdown?

## 7. What Is Not In Phase 1

This experiment does not include:

- Short selling.
- ATR stops.
- Trailing stops.
- Fixed stop-loss overlays.
- Intraday signals.

Those are later tests only after the leveraged baseline is understood.
