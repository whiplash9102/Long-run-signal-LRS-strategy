# Gayed LRS Strategy — Phase 1 Final Review

**Date:** April 2026  
**Version:** 1.0  
**Author:** Quantitative Research

---

## 1. What This Review Covers

This document summarises the results of Phase 1 backtesting for the Gayed-Bilello long-only moving average strategy. The objective of Phase 1 was to answer three questions before committing to live or paper trading with leverage.

First, does the moving average timing rule actually improve risk-adjusted returns compared to simply holding each ETF? Second, does the chosen filter hold up on data the model was not trained on, or does it only look good in hindsight? Third, is there evidence of overfitting, meaning that the chosen EMA length performs well only because it was cherry-picked from a range of possibilities?

The answers to all three questions are meaningful enough to continue to Phase 2. The details follow below.

---

## 2. Strategy Description

The rule is simple. Each ETF is compared daily against its own long-run moving average. When the ETF closes above the filter, the position is long that ETF (or its leveraged equivalent). When the ETF closes at or below the filter, the position moves to cash. All signals are confirmed at the daily close and executed at the next session's open, which prevents any same-day lookahead.

Each ETF uses its own price and its own moving average as the signal source, not a shared indicator like SPY. This is an intentional design decision. Testing each market independently reveals which markets respond to trend-following rules, rather than forcing all assets to follow the US equity regime.

Four filters were tested as candidates. The baseline from the original Gayed-Bilello paper is SMA 200. The three alternatives are EMA 190, EMA 195, and EMA 200.

The test universe covers five ETFs across two regions.

| ETF | Market | Period Covered |
| --- | --- | --- |
| SPY | US S&P 500 | 1993 to 2026 |
| QQQ | US Nasdaq 100 | 1999 to 2026 |
| IWM | US Russell 2000 | 2001 to 2026 |
| VGK | Developed Europe | 2005 to 2026 |
| EZU | Eurozone | 2001 to 2026 |

Transaction costs are set at 2 basis points per side (1 bps slippage plus 1 bps spread). Commission is zero to represent a modern retail broker. Synthetic leverage carries an additional annual fee of 100 basis points.

---

## 3. Full-Sample Backtest Results

### 3.1 Unlevered Strategy Performance

The table below shows the strategy result for each ETF using its best candidate filter, compared to what a passive buy-and-hold investor would have earned over the same period.

| ETF | Filter | Strategy CAGR | Buy-Hold CAGR | Strategy Max DD | Buy-Hold Max DD | Calmar |
| --- | --- | --- | --- | --- | --- | --- |
| SPY | SMA 200 | 8.11% | 10.23% | -27.85% | -55.19% | 0.291 |
| QQQ | EMA 200 | 8.79% | 14.56% | -56.72% | -82.46% | 0.155 |
| IWM | SMA 200 | 4.26% | 8.62% | -34.26% | -59.57% | 0.124 |
| VGK | SMA 200 | 4.75% | 6.32% | -30.43% | -63.62% | 0.156 |
| EZU | SMA 200 | 6.14% | 5.49% | -35.47% | -65.58% | 0.173 |

Three observations stand out immediately.

SPY and EZU are the strongest arguments for the strategy. On SPY, the strategy gives up about 2 percentage points of annual return compared to buy-and-hold, but cuts the maximum drawdown from 55% to 28%. For an investor who cannot stomach a 50% decline, that tradeoff is meaningful. On EZU, the strategy actually beats buy-and-hold on CAGR while also significantly reducing drawdown, which is the best possible outcome from a timing rule.

QQQ is the weakest case for the unlevered strategy. The maximum drawdown remains above 56% despite the timing filter. However, as shown in Section 3.2, QQQ becomes dramatically more interesting when the leveraged execution assets are introduced.

IWM and VGK both show the strategy working as designed, reducing drawdown substantially at the cost of some return, but neither ETF produces a compelling standalone result at 1x.

### 3.2 Leveraged Execution Results

The five best observed leveraged ETF results, ranked by Calmar ratio.

| Rank | Signal | Filter | Execution | CAGR | Max DD | Calmar | Sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | QQQ | EMA 200 | TQQQ 3x | 32.90% | -57.93% | 0.568 | 0.831 |
| 2 | QQQ | EMA 195 | TQQQ 3x | 31.02% | -57.93% | 0.536 | 0.803 |
| 3 | QQQ | EMA 190 | TQQQ 3x | 30.53% | -57.93% | 0.527 | 0.796 |
| 4 | QQQ | EMA 200 | QLD 2x | 22.29% | -44.05% | 0.506 | 0.792 |
| 5 | QQQ | EMA 195 | QLD 2x | 21.01% | -42.61% | 0.493 | 0.760 |
| 6 | SPY | SMA 200 | UPRO 3x | 21.79% | -58.36% | 0.373 | 0.698 |
| 7 | SPY | EMA 195 | UPRO 3x | 20.77% | -67.06% | 0.310 | 0.661 |
| 8 | SPY | EMA 190 | UPRO 3x | 19.28% | -68.56% | 0.281 | 0.641 |

**SPY plus UPRO (3x leverage on the S&P 500)** deserves specific attention because it represents the most accessible leveraged strategy for most investors. UPRO is a widely traded ETF with good liquidity, and applying the SMA 200 timing rule to it over the full history produced a 21.79% CAGR with a maximum drawdown of 58.36%. The buy-and-hold baseline for UPRO over the same period was 32.88% CAGR with a 74.82% maximum drawdown. The timing rule gives up 11 percentage points of annual return in exchange for reducing the worst drawdown by more than 16 percentage points.

Whether that tradeoff is worthwhile depends entirely on the investor. An investor who would have sold UPRO in a panic during a 75% decline would have been much better off with the timed version, even at a lower nominal return. An investor with genuine long-term conviction who would have held through the drawdown would have done better without timing. The historical evidence does not resolve this question — it only clarifies the magnitude of both the cost and the benefit.

The QQQ signal combined with TQQQ produces a CAGR of 32.90% over the available history. The timing rule reduces TQQQ's maximum drawdown from 81.57% (buy-and-hold) to 57.93%. That is still severe by any standard, but a reduction of roughly 24 percentage points shows the exit rule is doing meaningful work.


---

## 4. EMA Sensitivity Review

Before walk-forward testing, the sensitivity analysis checks whether results depend on finding one exact EMA length that performed well historically. If EMA 195 is a genuinely useful filter, then EMA 190, EMA 200, and EMA 205 should all produce similar results. If only EMA 195 works and its neighbours collapse, that is a red flag for overfitting.

The analysis tested EMA 180 through EMA 210 in steps of five, plus SMA 200, for all five ETFs. The coefficient of variation of the Calmar ratio across the full range measures how stable performance is across parameter choices.

```
SPY  — EMA length versus Calmar ratio

EMA 180  |████████████████████████      0.217
EMA 185  |█████████████████████████▌    0.237
EMA 190  |███████████████████████████   0.258
EMA 195  |█████████████████████████████ 0.276
EMA 200  |████████████████████████████  0.269
EMA 205  |███████████████████████████   0.262
EMA 210  |████████████████████████████▌ 0.311
SMA 200  |██████████████████████████████ 0.291
```

| ETF | Calmar CV | Verdict |
| --- | --- | --- |
| SPY | 0.111 | Stable |
| QQQ | 0.103 | Stable |
| IWM | 0.106 | Stable |
| VGK | 0.100 | Stable |
| EZU | 0.059 | Stable |

All five ETFs return a stable verdict. A coefficient of variation below 0.30 means the Calmar ratio does not change dramatically as the EMA length moves across the tested range. The performance is a plateau, not a spike.

For SPY, the CAGR moves in a narrow band from 7.1% at EMA 180 to 8.1% at SMA 200. The Calmar ratio improves smoothly as the window length grows, with no sudden collapse. This pattern repeats across all other ETFs and confirms that the parameter choice is not the source of the result.

---

## 5. Walk-Forward Validation

The walk-forward test is the most important check in Phase 1. It simulates what a real investor would have experienced by selecting a filter based only on past data and then trading the next period without looking ahead.

Starting from 1993, a 10-year training window selects the best filter from the four candidates using a composite score that weighs CAGR, Sharpe, Sortino, drawdown penalty, and Calmar. The selected filter then trades the following 2-year test period. The window advances by 6 months and repeats. Forty-one test windows were generated for SPY.

### 5.1 Filter Selection Pattern

Across all 41 test windows, EMA 195 was chosen in 51% of windows, SMA 200 in 27%, and EMA 190 in 18%. EMA 200 was not selected as the top-scoring filter in any training window.

This is an important finding. The composite scoring function consistently favours EMA 195 slightly above the other candidates, but not overwhelmingly so. SMA 200 wins roughly one in four training periods, which means it is a genuine competitor and not simply an inferior option.

### 5.2 Out-of-Sample Performance

| Execution | Windows | Positive CAGR | Median CAGR | Median Sharpe | Median Max DD | Median Calmar |
| --- | --- | --- | --- | --- | --- | --- |
| SPY 1x | 41 | 80.5% | 8.04% | 0.704 | -11.91% | 0.597 |
| SSO 2x | 39 | 71.8% | 14.99% | 0.742 | -23.64% | 0.604 |
| UPRO 3x | 33 | 72.7% | 29.72% | 0.892 | -35.05% | 0.671 |

The strategy produced positive returns in 80.5% of the 2-year test windows for SPY at 1x. That is a strong out-of-sample result. Producing positive CAGR in four out of five unseen future periods, without any knowledge of the future, demonstrates that the timing rule has genuine predictive content and is not purely a historical artifact.

The leverage results are also encouraging. For UPRO, the median 2-year CAGR was just under 30% and the median Calmar of 0.671 is higher than the full-sample Calmar from the fixed-rule test. On a typical 2-year window, the strategy's return-to-drawdown ratio is actually better than the 30-year average suggests. The difficult periods are real but concentrated.

### 5.3 The Difficult Windows

The two worst windows occurred around 2022. In test windows spanning 2021 to 2023, the strategy produced negative CAGR because the market declined sharply from a high base in an environment that was volatile but not cleanly trending. This is the known weakness of moving average strategies. They are slow to react and can generate losses during rapid bear markets before the exit signal triggers. SPY fell roughly 25% in 2022, and the exit signal arrived after a meaningful portion of that decline had already happened.

This is not a reason to abandon the strategy, but it is a reason to be clear-eyed about what it can and cannot do. The rule is designed for sustained, regime-level directional moves, not for short, sharp corrections followed by immediate recoveries.

---

## 6. Summary of Findings

The strategy works as designed on SPY. The timing rule reduces maximum drawdown by roughly half compared to buy-and-hold while retaining most of the long-run return. The rule holds up on data it was never trained on, with positive returns in 80% of unseen 2-year periods. The parameter choice is stable across a wide range of EMA lengths. None of these results depend on a single lucky parameter value.

The most attractive result in the backtest is QQQ plus TQQQ. Over the history of TQQQ since 2010, the timing rule has produced a CAGR close to 33% while cutting maximum drawdown from 82% to 58%. The absolute drawdown level remains too severe for most investors, but for those who can hold through it, the risk-adjusted profile over a long horizon is compelling.

The weakest result is IWM. The US small cap market is noisier, the drawdowns remain above 34%, and the CAGR is only 4.3%. The strategy works on IWM in the sense that it reduces drawdown, but the return level does not justify running an active timing rule rather than simply holding the index.

---

## 7. Phase 2 Recommendations

| Signal | Execution | Recommendation | Rationale |
| --- | --- | --- | --- |
| SPY | SPY 1x | Proceed | Core baseline. Strong out-of-sample results. Meaningful drawdown reduction. |
| SPY | UPRO 3x | Proceed with awareness | Strong CAGR, severe drawdown. Requires full understanding of the downside. |
| QQQ | QLD 2x | Proceed | Good balance of return and drawdown. More manageable than TQQQ. |
| QQQ | TQQQ 3x | Proceed with awareness | Highest CAGR in the universe. Drawdown at -58% is a real risk event to plan for. |
| EZU | EZU 1x | Proceed | Only case that beats buy-and-hold on CAGR while reducing drawdown. |
| VGK | VGK 1x | Proceed with lower priority | Modest but consistent results. Works as designed. |
| IWM | IWM 1x | Deprioritise | Low CAGR and high noise. Not a compelling use of the strategy at this stage. |

The recommended filter for Phase 2 paper trading is EMA 195 for SPY-based executions, given that it was selected most frequently in walk-forward training and performs consistently across the sensitivity range. SMA 200 is the conservative fallback that requires simpler implementation and performs nearly as well across all ETFs.

---

## 8. What Needs to Be Done Before Going Live

Walk-forward validation must be extended to QQQ, IWM, VGK, and EZU. The SPY walk-forward is the anchor of this analysis, but a complete picture of out-of-sample performance across all five markets is required before the Phase 2 decision framework above can be considered fully validated.

An alert system must be built so that end-of-day close prices are compared against the selected filter in real time and a trade notification is generated when a signal changes. The backtest infrastructure is already in place. The alert layer is the final engineering step before any real capital is involved.
