# EMA Sensitivity Review

## Purpose

Check whether EMA performance across lengths 180–210 is stable or concentrated
in a narrow spike that would indicate overfitting.

**Tickers reviewed:** `EZU`, `IWM`, `QQQ`, `SPY`, `VGK`  
**Metric used for ranking:** composite score (CAGR 25%, Sharpe 25%, Sortino 20%, Drawdown penalty 20%, Calmar 10%)  
**Execution asset:** 1x unlevered ETF per signal ticker  

## Stability Verdict

| Ticker | Best Filter | Calmar CV | Calmar Range | Verdict |
| --- | --- | --- | --- | --- |
| `EZU` | `SMA_200` | 0.0591 | 0.0252 | **STABLE** |
| `IWM` | `EMA_185` | 0.1057 | 0.0355 | **STABLE** |
| `QQQ` | `EMA_210` | 0.1034 | 0.0483 | **STABLE** |
| `SPY` | `SMA_200` | 0.1111 | 0.094 | **STABLE** |
| `VGK` | `SMA_200` | 0.1004 | 0.0384 | **STABLE** |

**Interpretation:**
- `Calmar CV` = coefficient of variation of Calmar ratio across EMA 180–210. Lower = more stable.
- CV < 0.30 → **STABLE** (results form a consistent plateau; not a knife-edge)
- CV ≥ 0.30 → **FRAGILE** (results spike at one value; likely overfit)

## Per-Ticker Detail

## EZU

| Filter | CAGR | Max DD | Calmar | Sharpe | Score | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `EMA_180` | 5.70% | -37.42% | 0.1523 | 0.4700 | 0.1771 |
| `EMA_185` | 5.64% | -37.42% | 0.1506 | 0.4650 | 0.1744 |
| `EMA_190` | 5.54% | -37.44% | 0.1479 | 0.4578 | 0.1707 | ← candidate
| `EMA_195` | 5.80% | -34.30% | 0.1692 | 0.4764 | 0.1885 | ← candidate
| `EMA_200` | 5.83% | -34.63% | 0.1682 | 0.4770 | 0.1880 | ← candidate
| `SMA_200` | 6.14% | -35.47% | 0.1730 | 0.4963 | 0.1946 | ← candidate
| `EMA_205` | 5.55% | -34.18% | 0.1623 | 0.4582 | 0.1784 |
| `EMA_210` | 5.37% | -32.70% | 0.1643 | 0.4464 | 0.1757 |

**Stability:** STABLE — Calmar CV = 0.0591, range = 0.0252  
**Best filter by composite score:** `SMA_200`

## IWM

| Filter | CAGR | Max DD | Calmar | Sharpe | Score | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `EMA_180` | 4.12% | -36.75% | 0.1121 | 0.3410 | 0.1139 |
| `EMA_185` | 4.48% | -33.61% | 0.1332 | 0.3638 | 0.1345 |
| `EMA_190` | 3.81% | -35.90% | 0.1060 | 0.3211 | 0.1046 | ← candidate
| `EMA_195` | 3.98% | -35.15% | 0.1133 | 0.3324 | 0.1129 | ← candidate
| `EMA_200` | 4.29% | -36.23% | 0.1184 | 0.3514 | 0.1215 | ← candidate
| `SMA_200` | 4.26% | -34.26% | 0.1243 | 0.3522 | 0.1254 | ← candidate
| `EMA_205` | 3.71% | -36.87% | 0.1006 | 0.3146 | 0.0989 |
| `EMA_210` | 3.68% | -37.64% | 0.0977 | 0.3126 | 0.0962 |

**Stability:** STABLE — Calmar CV = 0.1057, range = 0.0355  
**Best filter by composite score:** `EMA_185`

## QQQ

| Filter | CAGR | Max DD | Calmar | Sharpe | Score | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `EMA_180` | 8.04% | -62.51% | 0.1286 | 0.5374 | 0.1570 |
| `EMA_185` | 8.26% | -60.68% | 0.1361 | 0.5497 | 0.1675 |
| `EMA_190` | 8.33% | -60.02% | 0.1387 | 0.5533 | 0.1710 | ← candidate
| `EMA_195` | 8.64% | -59.76% | 0.1445 | 0.5686 | 0.1801 | ← candidate
| `EMA_200` | 8.79% | -56.72% | 0.1550 | 0.5779 | 0.1918 | ← candidate
| `SMA_200` | 7.89% | -53.65% | 0.1471 | 0.5271 | 0.1724 | ← candidate
| `EMA_205` | 8.72% | -54.46% | 0.1601 | 0.5731 | 0.1946 |
| `EMA_210` | 9.32% | -52.67% | 0.1769 | 0.6056 | 0.2168 |

**Stability:** STABLE — Calmar CV = 0.1034, range = 0.0483  
**Best filter by composite score:** `EMA_210`

## SPY

| Filter | CAGR | Max DD | Calmar | Sharpe | Score | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `EMA_180` | 7.12% | -32.74% | 0.2173 | 0.6220 | 0.2715 |
| `EMA_185` | 7.35% | -30.99% | 0.2372 | 0.6395 | 0.2860 |
| `EMA_190` | 7.90% | -30.60% | 0.2580 | 0.6749 | 0.3089 | ← candidate
| `EMA_195` | 8.13% | -29.44% | 0.2761 | 0.6910 | 0.3212 | ← candidate
| `EMA_200` | 7.94% | -29.45% | 0.2694 | 0.6747 | 0.3125 | ← candidate
| `SMA_200` | 8.11% | -27.85% | 0.2913 | 0.6976 | 0.3283 | ← candidate
| `EMA_205` | 7.71% | -29.45% | 0.2617 | 0.6563 | 0.3020 |
| `EMA_210` | 8.08% | -25.94% | 0.3113 | 0.6823 | 0.3278 |

**Stability:** STABLE — Calmar CV = 0.1111, range = 0.094  
**Best filter by composite score:** `SMA_200`

## VGK

| Filter | CAGR | Max DD | Calmar | Sharpe | Score | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `EMA_180` | 4.29% | -30.66% | 0.1398 | 0.3761 | 0.1378 |
| `EMA_185` | 4.31% | -34.24% | 0.1259 | 0.3784 | 0.1301 |
| `EMA_190` | 4.12% | -32.64% | 0.1262 | 0.3650 | 0.1270 | ← candidate
| `EMA_195` | 3.95% | -33.24% | 0.1189 | 0.3530 | 0.1191 | ← candidate
| `EMA_200` | 4.04% | -33.50% | 0.1205 | 0.3592 | 0.1219 | ← candidate
| `SMA_200` | 4.75% | -30.43% | 0.1560 | 0.4138 | 0.1587 | ← candidate
| `EMA_205` | 3.99% | -31.46% | 0.1269 | 0.3563 | 0.1250 |
| `EMA_210` | 3.70% | -31.43% | 0.1176 | 0.3352 | 0.1137 |

**Stability:** STABLE — Calmar CV = 0.1004, range = 0.0384  
**Best filter by composite score:** `SMA_200`


## Reading Rule

- If all EMA lengths from 180 to 210 produce similar metrics, the strategy is not sensitive
  to the exact parameter. The chosen filter is robust.
- If only EMA 195 works and neighbors collapse, the backtest is overfit and the result
  should not be used for live trading.
- A STABLE verdict does not guarantee future performance. It only shows the rule is not
  a lucky coincidence of one specific number.
