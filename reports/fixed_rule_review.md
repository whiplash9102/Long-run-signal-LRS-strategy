# Fixed-Rule Backtest Review

## Scope

- Purpose: test whether the configured long leveraged ETF rules are profitable.
- Signal assets: normal ETFs only.
- Execution assets: configured 1x, 2x, and 3x assets.
- Risk-off asset: CASH.
- Initial capital: $100,000.
- Validation status: fixed-rule research only; walk-forward validation is not done yet.

## Profitability Snapshot

- Profitable strategy rows: 60 of 60.
- Profitable observed leveraged ETF rows: 24 of 24.
- Strategy rows with high or severe drawdown: 39 of 60.
- Profitability definition: CAGR above 0 and ending equity above initial capital.

## Headline Result

- Best risk-adjusted fixed-rule row: `QQQ` + `EMA_200` + `TQQQ_3X`.
- CAGR: 32.90%.
- Max drawdown: -57.93%.
- Calmar ratio: 0.5679.
- Ending equity: $10,017,549.
- Compared with buy-and-hold on the same execution asset, CAGR gap is -9.93% and drawdown improvement is 23.64%.

## Best By Signal ETF

| Signal | Filter | Execution | Profitable | CAGR | Max DD | Calmar | Recovery Days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZU | SMA_200 | EZU_1X | yes | 6.14% | -35.47% | 0.1730 | 3128 |
| IWM | SMA_200 | TNA_3X | yes | 9.60% | -71.73% | 0.1339 | 1866 |
| QQQ | EMA_200 | TQQQ_3X | yes | 32.90% | -57.93% | 0.5679 | 872 |
| SPY | SMA_200 | UPRO_3X | yes | 21.79% | -58.36% | 0.3734 | 1118 |
| VGK | SMA_200 | VGK_1X | yes | 4.75% | -30.43% | 0.1560 | 2542 |

## Observed Leveraged ETF Ranking

| Rank | Signal | Filter | Execution | Profitable | CAGR | Max DD | Calmar |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | QQQ | EMA_200 | TQQQ_3X | yes | 32.90% | -57.93% | 0.5679 |
| 2 | QQQ | EMA_195 | TQQQ_3X | yes | 31.02% | -57.93% | 0.5355 |
| 3 | QQQ | EMA_190 | TQQQ_3X | yes | 30.53% | -57.93% | 0.5271 |
| 4 | QQQ | EMA_200 | QLD_2X | yes | 22.29% | -44.05% | 0.5061 |
| 5 | QQQ | EMA_195 | QLD_2X | yes | 21.01% | -42.61% | 0.4931 |
| 6 | QQQ | EMA_190 | QLD_2X | yes | 20.72% | -42.61% | 0.4862 |
| 7 | QQQ | SMA_200 | TQQQ_3X | yes | 27.93% | -60.10% | 0.4647 |
| 8 | QQQ | SMA_200 | QLD_2X | yes | 19.43% | -47.20% | 0.4116 |
| 9 | SPY | SMA_200 | UPRO_3X | yes | 21.79% | -58.36% | 0.3734 |
| 10 | SPY | EMA_195 | UPRO_3X | yes | 20.77% | -67.06% | 0.3098 |

## Strategy Versus Buy-And-Hold

| Rank | Signal | Filter | Execution | Strategy CAGR | Buy Hold CAGR | CAGR Gap | Strategy DD | Buy Hold DD | DD Improvement | Calmar Gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | QQQ | EMA_200 | TQQQ_3X | 32.90% | 42.83% | -9.93% | -57.93% | -81.57% | 23.64% | 0.0428 |
| 2 | QQQ | EMA_195 | TQQQ_3X | 31.02% | 42.83% | -11.81% | -57.93% | -81.57% | 23.64% | 0.0104 |
| 3 | QQQ | EMA_190 | TQQQ_3X | 30.53% | 42.83% | -12.30% | -57.93% | -81.57% | 23.64% | 0.0019 |
| 4 | QQQ | EMA_200 | QLD_2X | 22.29% | 24.76% | -2.47% | -44.05% | -82.46% | 38.41% | 0.2058 |
| 5 | QQQ | EMA_195 | QLD_2X | 21.01% | 24.76% | -3.75% | -42.61% | -82.46% | 39.85% | 0.1928 |
| 6 | QQQ | EMA_190 | QLD_2X | 20.72% | 24.76% | -4.04% | -42.61% | -82.46% | 39.85% | 0.1860 |
| 7 | QQQ | SMA_200 | TQQQ_3X | 27.93% | 42.83% | -14.91% | -60.10% | -81.57% | 21.47% | -0.0604 |
| 8 | QQQ | SMA_200 | QLD_2X | 19.43% | 24.76% | -5.33% | -47.20% | -82.46% | 35.26% | 0.1114 |
| 9 | SPY | SMA_200 | UPRO_3X | 21.79% | 32.88% | -11.09% | -58.36% | -74.82% | 16.46% | -0.0661 |
| 10 | SPY | EMA_195 | UPRO_3X | 20.77% | 32.88% | -12.11% | -67.06% | -74.82% | 7.76% | -0.1297 |

## Reading Rule

- `CAGR` answers whether the rule made money over the tested period.
- `Max DD` shows the largest peak-to-trough pain.
- `Recovery Days` shows how long capital stayed below a prior equity peak.
- `Calmar` is the main ranking metric here because it compares return to drawdown.
- A profitable leveraged ETF row is not automatically acceptable if the drawdown or recovery time is too large.

## Next Decision

- Use this report to select candidates for walk-forward testing.
- Do not treat the fixed-rule winner as final until it survives out-of-sample validation.
