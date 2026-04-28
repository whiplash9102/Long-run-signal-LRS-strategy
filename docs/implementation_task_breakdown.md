# Implementation Task Breakdown

## Purpose

This document answers one question:

What needs to be built, in what order, and what proves each step is done?

## Phase 0: Documentation And Config

Build:

- Keep the strategy rule clear.
- Keep the config complete.
- Keep the implementation checklist short.

Inputs:

- `Gayed Bilello 2016.pdf`
- `config/gayed_lrs_parameters.yaml`
- `docs/gayed_lrs_rule_and_backtest_spec.md`

Done when:

- Docs state the rule in plain language.
- Config has no missing required values.
- Phase 1 is clearly long-only and unlevered.
- Test universe is clearly listed.

Status:

- Complete.

## Phase 1: Config Loader

Build:

- Load `config/gayed_lrs_parameters.yaml`.
- Validate required fields.
- Fail early on invalid settings.

Outputs:

- Parsed config object.
- Clear validation errors.

Done when:

- Valid config loads.
- Missing required fields fail.
- Candidate filters require `id`, `type`, and `length`.
- Test universe entries require `id`, `ticker`, `region`, and `exposure`.
- `allow_short: false` is enforced.
- Score weights sum to `1.0`.

## Phase 2: Data Layer

Build:

- Download or load daily market data.
- Clean and align data.
- Build return series.

ETF universe:

- `SPY`
- `QQQ`
- `IWM`
- `VGK`
- `EZU`

Leveraged execution assets:

- `SSO`
- `UPRO`
- `QLD`
- `TQQQ`
- `UWM`
- `TNA`

Risk-off:

- Primary: `CASH`
- Optional comparison: `BIL`

Outputs:

- `data/processed/prices_adjusted.csv`
- `data/processed/returns_daily.csv`
- `data/processed/data_quality_report.csv`

Done when:

- All test ETFs have clean adjusted close data after warmup.
- Leveraged ETFs with shorter histories do not break the run.
- BIL is downloaded for optional comparison.
- Data quality issues are reported.
- No future data is introduced.

## Phase 3: Indicator Engine

Build:

- Calculate moving-average filters for each ETF.

Required filters:

- `SMA 200`
- `EMA 190`
- `EMA 195`
- `EMA 200`
- EMA sensitivity range `180` to `210`, step `5`

Output:

- `data/processed/indicators.csv`

Done when:

- SMA 200 equals the 200-day simple average.
- EMA calculation is consistent and reproducible.
- Indicators are date-aligned with prices.
- No future prices are used.

## Phase 4: Signal Engine

Build:

- Convert indicators into regime states and alerts for each ETF.

Rules:

- Close above filter: `LONG`.
- Close at or below filter: `RISK_OFF`.
- Cross into `LONG`: `BUY_ALERT`.
- Cross into `RISK_OFF`: `EXIT_ALERT`.
- No state change: `NO_CHANGE`.

Output:

- `data/processed/signals.csv`

Done when:

- Buy alerts fire once per valid upward cross.
- Exit alerts fire once per valid downward/equal cross.
- Repeated days in the same regime do not repeat alerts.
- No short signal exists anywhere.

## Phase 5: Alert System

Build:

- Generate the latest actionable daily alert.

Output:

- `outputs/alerts/gayed_lrs_alerts.csv`

Done when:

- Alert is based on confirmed daily close.
- Alert includes ETF ticker and next-session action.
- No alert is sent when the signal is unchanged.
- Email and webhook remain disabled in phase 1.

## Phase 6: Fixed-Rule Backtest

Build:

- Backtest each ETF and candidate filter with identical assumptions.

Candidates:

- `SMA 200`
- `EMA 190`
- `EMA 195`
- `EMA 200`

Outputs:

- `outputs/backtests/fixed_rule_equity_curves.csv`
- `outputs/backtests/fixed_rule_trades.csv`
- `reports/tables/fixed_rule_metrics.csv`

Done when:

- Trades execute after the signal date.
- No short positions appear.
- All ETFs and filters use the same costs and execution rules.
- Buy-and-hold benchmark is included for each ETF.

## Phase 7: Walk-Forward Validation

Build:

- Test whether parameter choices work out of sample.

Settings:

- Train: `10 years`
- Test: `2 years`
- Step: `6 months`

Outputs:

- `outputs/backtests/walk_forward_results.csv`
- `reports/tables/walk_forward_summary.csv`

Done when:

- Test data is never used to choose the filter.
- Every window records ETF, train dates, test dates, selected filter, and test result.
- In-sample and out-of-sample results are reported separately.

## Phase 8: False-Breakout Audit

Build:

- Measure how often buy alerts fail quickly.
- Record entry context for each buy alert.
- Summarize whipsaw rate by ETF and filter.

Inputs:

- `data/processed/prices_adjusted.csv`
- `data/processed/signals.csv`
- `data/processed/indicators.csv`

Outputs:

- `reports/tables/false_breakout_audit_entries.csv`
- `reports/tables/false_breakout_audit_summary.csv`
- `reports/false_breakout_review.md`

Done when:

- Every buy alert is paired with the next exit when available.
- Whipsaw counts are reported for the configured session window.
- Entry distance, slope, return strength, and volatility are recorded.
- The output stays diagnostic only and does not change the trading rule yet.

## Phase 9: False-Breakout Gate Scan

Build:

- Test a small set of simple entry gates on top of the audit rows.
- Compare sample retention against whipsaw reduction.

Inputs:

- `reports/tables/false_breakout_audit_entries.csv`
- `reports/tables/false_breakout_audit_summary.csv`

Outputs:

- `reports/tables/false_breakout_gate_candidates.csv`
- `reports/false_breakout_gate_review.md`

Done when:

- The scan ranks a few simple thresholds on entry distance and filter slope.
- The report clearly states whether any gate is worth carrying forward.
- The gate remains diagnostic unless it improves whipsaw rate without cutting most of the sample.

## Phase 10: EMA Sensitivity Review

Build:

- Check whether EMA performance is stable or overfit.

Filters:

- `EMA 180`
- `EMA 185`
- `EMA 190`
- `EMA 195`
- `EMA 200`
- `EMA 205`
- `EMA 210`

Output:

- `reports/tables/parameter_sensitivity.csv`

Done when:

- EMA 190 and EMA 195 are tested directly.
- Nearby values are compared.
- Final note says whether EMA results look stable or fragile.

## Phase 11: Final Report

Build:

- Produce a decision report.

Output:

- `reports/final_strategy_review.md`

The report must answer:

- Does the SMA 200 baseline work correctly on SPY?
- Which ETF has the best risk-adjusted result under the same rule?
- Do EMA 190 or EMA 195 beat SMA 200 out of sample?
- Is the winning result stable across nearby parameters?
- What is the drawdown tradeoff?
- Should phase 2 leverage testing start?

Done when:

- The conclusion is readable without opening the code.
- Full-sample and out-of-sample results are separated.
- The recommendation is based on evidence, not a single optimized number.

## Phase 12: Later Extensions

Only after the leveraged baseline is understood:

- Test ATR stops.
- Test trailing stops.
- Test fixed stop-loss overlays.
- Build a combined multi-ETF portfolio.

These must remain separate from the core baseline.
