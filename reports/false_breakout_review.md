# False-Breakout Audit

## Scope

- Purpose: measure whether buy alerts tend to fail quickly.
- Whipsaw window: 20 sessions.
- Trading status: diagnostics only, not a trading filter.
- Measurement level: signal ETF only, not leveraged execution.

## Overall Snapshot

- Buy alerts analyzed: 4425.
- Completed round trips: 4385.
- Whipsaws inside the window: 3155.
- Whipsaw rate: 71.95%.
- Average entry distance from filter: 0.92%.
- Average recent volatility at entry: 22.48%.
- Average recent return at entry: 0.67%.

## Highest Whipsaw Rates

| ticker | filter_id | buy_alerts | completed_round_trips | whipsaws | whipsaw_rate | avg_entry_distance_pct | avg_filter_slope_pct | avg_recent_volatility_ann_pct | avg_recent_return_pct | avg_trade_return_pct | avg_whipsaw_trade_return_pct | avg_non_whipsaw_trade_return_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IWM | EMA_200 | 141 | 140 | 110 | 78.57% | 0.82% | -0.0002 | 23.53% | 1.35% | 0.83% | -1.66% | 9.95% |
| IWM | EMA_205 | 140 | 139 | 109 | 78.42% | 0.83% | -0.0002 | 23.51% | 1.33% | 0.77% | -1.68% | 9.68% |
| IWM | EMA_210 | 140 | 139 | 109 | 78.42% | 0.83% | -0.0002 | 23.88% | 1.30% | 0.72% | -1.74% | 9.68% |
| IWM | EMA_190 | 149 | 148 | 115 | 77.70% | 0.81% | -0.0002 | 23.72% | 1.18% | 0.72% | -1.64% | 8.94% |
| IWM | EMA_195 | 147 | 146 | 113 | 77.40% | 0.83% | -0.0001 | 23.54% | 1.16% | 0.72% | -1.64% | 8.79% |
| IWM | EMA_185 | 147 | 146 | 112 | 76.71% | 0.81% | -0.0002 | 23.74% | 1.40% | 0.81% | -1.62% | 8.82% |
| IWM | EMA_180 | 148 | 147 | 112 | 76.19% | 0.83% | -0.0002 | 23.64% | 1.57% | 0.77% | -1.66% | 8.56% |
| VGK | EMA_180 | 107 | 106 | 79 | 74.53% | 0.79% | -0.0002 | 20.75% | 0.63% | 0.84% | -1.51% | 7.72% |
| SPY | EMA_205 | 125 | 124 | 92 | 74.19% | 0.79% | -0.0002 | 20.73% | -0.11% | 2.59% | -1.53% | 14.46% |
| SPY | EMA_200 | 124 | 123 | 91 | 73.98% | 0.76% | -0.0002 | 20.44% | -0.07% | 2.70% | -1.42% | 14.41% |

## Sample Entry Audit Rows

| ticker | filter_id | entry_date | exit_date | sessions_held | whipsaw | entry_distance_pct | filter_slope_pct | recent_return_pct | recent_volatility_ann_pct | trade_return_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZU | EMA_180 | 2002-03-07 | 2002-03-12 | 3.0000 | yes | 0.44% | -0.07% | 9.18% | 19.12% | -1.20% |
| EZU | EMA_180 | 2002-03-15 | 2002-03-22 | 5.0000 | yes | 0.32% | -0.03% | 6.02% | 19.68% | -0.57% |
| EZU | EMA_180 | 2002-03-28 | 2002-04-02 | 2.0000 | yes | 0.04% | -0.04% | 5.82% | 17.88% | -0.13% |
| EZU | EMA_180 | 2002-04-16 | 2002-04-22 | 4.0000 | yes | 0.30% | -0.09% | -1.29% | 16.73% | -0.84% |
| EZU | EMA_180 | 2002-05-14 | 2002-05-21 | 5.0000 | yes | 0.51% | -0.05% | -0.02% | 19.10% | -0.90% |
| EZU | EMA_180 | 2002-05-23 | 2002-05-24 | 1.0000 | yes | 0.29% | 0.02% | 1.46% | 18.03% | -1.46% |
| EZU | EMA_180 | 2003-04-17 | 2004-05-10 | 267.0000 | no | 0.91% | -0.05% | 9.32% | 33.65% | 33.92% |
| EZU | EMA_180 | 2004-05-19 | 2004-05-21 | 2.0000 | yes | 0.30% | -0.05% | -3.45% | 18.44% | -0.40% |
| EZU | EMA_180 | 2004-05-24 | 2004-07-23 | 41.0000 | no | 1.27% | 0.01% | -3.57% | 18.47% | -0.26% |
| EZU | EMA_180 | 2004-07-27 | 2004-08-05 | 7.0000 | yes | 0.18% | 0.01% | -4.90% | 15.04% | -1.01% |
| EZU | EMA_180 | 2004-08-10 | 2004-08-11 | 1.0000 | yes | 0.09% | -0.03% | -4.37% | 13.43% | -1.42% |
| EZU | EMA_180 | 2004-08-16 | 2004-08-23 | 5.0000 | yes | 0.34% | -0.05% | -2.55% | 16.50% | -0.46% |
| EZU | EMA_180 | 2004-08-25 | 2005-10-20 | 292.0000 | no | 0.95% | 0.03% | 0.83% | 14.27% | 24.09% |
| EZU | EMA_180 | 2005-10-21 | 2006-06-12 | 159.0000 | no | 0.02% | 0.07% | -3.32% | 14.14% | 14.66% |
| EZU | EMA_180 | 2006-06-15 | 2006-06-19 | 2.0000 | yes | 1.33% | -0.05% | -3.97% | 24.69% | -1.41% |

## Reading Rule

- Small entry distance with weak recent strength is the first place to look for a false breakout filter.
- If whipsaws cluster when slope is flat or negative, a slope gate may help.
- If whipsaws cluster when entry volatility is high, a volatility gate may help.
- This report does not change the strategy yet.
