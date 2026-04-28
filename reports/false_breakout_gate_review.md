# False-Breakout Gate Scan

## Scope

- Purpose: test a small, simple gate on top of the audit.
- Inputs: false-breakout audit entries, not raw price history.
- Status: diagnostics only.

## Baseline

- Buy alerts: 4425.
- Completed round trips: 4385.
- Whipsaw rate: 71.95%.
- Average entry distance: 0.92%.
- Average filter slope: -0.02%.

## Recommended Gate

- No gate met the retention threshold.

## Top Candidates

| rank | min_entry_distance_pct | min_filter_slope_pct | accepted_alerts | accepted_completed_round_trips | accepted_whipsaws | acceptance_rate | whipsaw_rate | whipsaw_reduction | avg_trade_return_pct | avg_entry_distance_pct | avg_filter_slope_pct | recommended |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1.50% | -0.05% | 585 | 563 | 300 | 13.22% | 53.29% | 18.66% | 2.47% | 2.24% | 0.05% | no |
| 2 | 1.50% | -0.10% | 663 | 641 | 350 | 14.98% | 54.60% | 17.35% | 2.28% | 2.27% | 0.03% | no |
| 3 | 1.50% | 0.00% | 367 | 350 | 192 | 8.29% | 54.86% | 17.09% | 2.67% | 2.33% | 0.09% | no |
| 4 | 1.25% | -0.05% | 800 | 777 | 452 | 18.08% | 58.17% | 13.78% | 2.09% | 2.01% | 0.05% | no |
| 5 | 1.25% | -0.10% | 921 | 898 | 532 | 20.81% | 59.24% | 12.71% | 2.04% | 2.02% | 0.03% | no |
| 6 | 1.25% | 0.00% | 499 | 482 | 286 | 11.28% | 59.34% | 12.61% | 2.08% | 2.08% | 0.09% | no |
| 7 | 1.50% | 0.05% | 200 | 190 | 115 | 4.52% | 60.53% | 11.42% | 0.12% | 2.53% | 0.15% | no |
| 8 | 1.50% | 0.10% | 103 | 99 | 61 | 2.33% | 61.62% | 10.33% | -0.84% | 2.84% | 0.22% | no |
| 9 | 1.00% | 0.00% | 654 | 637 | 394 | 14.78% | 61.85% | 10.10% | 1.85% | 1.85% | 0.08% | no |
| 10 | 1.00% | -0.05% | 1096 | 1073 | 670 | 24.77% | 62.44% | 9.51% | 1.73% | 1.77% | 0.04% | no |

## Reading Rule

- A useful gate must lower whipsaw rate without cutting too much of the trade sample.
- Entry distance is a proxy for how far price has moved above the filter.
- Filter slope is a proxy for whether the moving average is flattening or rising.
- This scan is still not a trading rule. It only tells us which gate is worth testing next.
