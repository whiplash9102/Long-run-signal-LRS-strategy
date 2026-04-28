# Fixed-Rule Review Report

## Purpose

This layer turns the raw backtest metrics into reader-friendly review outputs.

The goal is not to pick the final strategy yet. The goal is to answer:

```text
Which fixed-rule leveraged ETF tests were profitable, and how much risk did they require?
```

## Inputs

```text
reports/tables/fixed_rule_metrics.csv
config/gayed_lrs_parameters.yaml
```

## Outputs

```text
reports/tables/fixed_rule_strategy_rankings.csv
reports/tables/fixed_rule_observed_leveraged_rankings.csv
reports/tables/fixed_rule_best_by_signal.csv
reports/tables/fixed_rule_strategy_vs_buy_hold.csv
reports/fixed_rule_review.md
```

## Review Structure

1. Profitability

   A row is profitable when `CAGR > 0` and ending equity is above the configured initial capital.

2. Risk

   Drawdown is grouped into four buckets:

   - `severe`: max drawdown at or below `-70%`
   - `high`: max drawdown at or below `-50%`
   - `moderate`: max drawdown at or below `-30%`
   - `lower`: max drawdown better than `-30%`

3. Recovery

   Recovery time is grouped into four buckets:

   - `severe`: at least 1095 days below a prior equity peak
   - `high`: at least 730 days
   - `moderate`: at least 365 days
   - `lower`: below 365 days

4. Ranking

   Strategies are ranked by:

   ```text
   Calmar ratio, then CAGR, then Sharpe ratio, then ending equity
   ```

   Calmar is the first ranking metric because this project is testing leverage, and leverage can make raw CAGR look attractive while hiding unacceptable drawdown.

5. Strategy Versus Buy-And-Hold

   Each timed strategy is compared with buy-and-hold on the same execution asset over the same available date range.

## Important Limitation

This report is fixed-rule research only. It is useful for candidate selection, but it is not final validation.

The next step is walk-forward testing.
