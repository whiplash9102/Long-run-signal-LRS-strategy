# Project Structure And Workflow

## Purpose

This document answers one question:

Where does everything live, and what is the working process?

## 1. Documentation Map

The docs are intentionally split so they do not repeat each other.

| File | Owns | Does Not Own |
| --- | --- | --- |
| `gayed_lrs_rule_and_backtest_spec.md` | Strategy rule and validation logic | Folder layout or coding tasks |
| `project_structure_and_workflow.md` | Project layout and workflow | Trading rule detail |
| `implementation_task_breakdown.md` | Build checklist and acceptance checks | Long explanations of the paper |
| `config/gayed_lrs_parameters.yaml` | Exact parameter values | Narrative explanation |

## 2. Current State

Current files:

- `Gayed Bilello 2016.pdf`
- `config/gayed_lrs_parameters.yaml`
- `docs/gayed_lrs_rule_and_backtest_spec.md`
- `docs/project_structure_and_workflow.md`
- `docs/implementation_task_breakdown.md`

Current status:

- Requirements are documented.
- Config is filled.
- Signal, backtest, and reporting code now exist.

## 3. Target Layout

```text
personal_trade/
  config/
    gayed_lrs_parameters.yaml
  data/
    raw/
    processed/
  docs/
  outputs/
    alerts/
    backtests/
  reports/
    charts/
    tables/
  src/
    data/
    strategy/
    backtest/
    alerts/
    reporting/
  tests/
```

## 4. Folder Responsibilities

`config/`

- One canonical YAML file for strategy settings.

`data/raw/`

- Downloaded market data before cleaning.

`data/processed/`

- Clean aligned price, return, indicator, and signal files.

`src/data/`

- Downloading, loading, cleaning, and validating data.

`src/strategy/`

- Moving averages, regime states, and signal events.

`src/backtest/`

- Portfolio simulation, metrics, fixed-rule tests, and walk-forward validation.

`src/alerts/`

- Daily alert generation.

`src/reporting/`

- Tables, charts, diagnostics, and final review.

`outputs/`

- Machine-readable outputs from alerts and backtests.

`reports/`

- Human-readable decision outputs.

`tests/`

- Tests for each implementation module.

## 5. Workflow

The project should move in this order:

1. Validate config.
2. Load and clean data for the ETF test universe.
3. Generate indicators for each ETF.
4. Generate signals for each ETF.
5. Generate daily alerts.
6. Run fixed-rule backtests by ETF and filter.
7. Run false-breakout diagnostics on buy alerts.
8. Scan simple false-breakout gate candidates.
9. Run walk-forward validation.
10. Run EMA sensitivity review.
11. Produce final strategy report.
12. Decide whether phase 2 leverage testing should start.

ETF test universe:

- `SPY`: US large-cap baseline.
- `QQQ`: US Nasdaq-100 growth/technology-heavy exposure.
- `IWM`: US small-cap exposure.
- `VGK`: developed Europe exposure.
- `EZU`: Eurozone exposure.

## 6. Clear Outputs

The first complete implementation should produce:

```text
data/processed/prices_adjusted.csv
data/processed/returns_daily.csv
data/processed/indicators.csv
data/processed/signals.csv
outputs/alerts/gayed_lrs_alerts.csv
outputs/backtests/fixed_rule_equity_curves.csv
outputs/backtests/fixed_rule_trades.csv
reports/tables/false_breakout_audit_entries.csv
reports/tables/false_breakout_audit_summary.csv
reports/false_breakout_review.md
reports/tables/false_breakout_gate_candidates.csv
reports/false_breakout_gate_review.md
outputs/backtests/walk_forward_results.csv
reports/tables/fixed_rule_metrics.csv
reports/tables/walk_forward_summary.csv
reports/tables/parameter_sensitivity.csv
reports/final_strategy_review.md
```

## 7. Operating Model

The user acts as the business middle man.

The assistant is responsible for:

- Keeping the trading logic disciplined.
- Avoiding overfitting.
- Writing the implementation.
- Running validation.
- Producing clear decision outputs.

The user is responsible for:

- Confirming strategic preferences.
- Reviewing final outputs.
- Deciding whether to proceed to leverage testing.
