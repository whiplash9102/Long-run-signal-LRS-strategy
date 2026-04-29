# Gayed LRS Strategy Backtesting Engine

A comprehensive Python-based backtesting and research engine for validating the Gayed-Bilello Leverage Risk System (LRS) strategy.

## 📌 Project Overview

This project implements and extends the momentum and trend-following strategy outlined in Michael A. Gayed and Charlie Bilello's 2016 paper, *"Leverage for the Long Run"*. 

The core premise of the strategy is that leveraged ETFs suffer from severe volatility decay during market drawdowns, but outsize returns during uptrends. By using a long-term moving average (e.g., 200-day SMA) as a regime filter, the strategy aims to:
- Be **LONG (Risk-On)** in leveraged assets when the market is above its moving average.
- Rotate to **CASH (Risk-Off)** when the market falls below its moving average, avoiding the compounded decay of leveraged ETFs during bear markets.

### Extensions Beyond the Original Paper
1. **Per-ETF Signaling:** Unlike the original paper which uses SPY as a universal signal for all assets, this engine tests whether each ETF's *own* price versus its *own* moving average is an effective signal.
2. **Alternative Filters:** Alongside the traditional SMA 200, the engine systematically tests Exponential Moving Averages (EMA 180 through EMA 210) to validate parameter stability.
3. **Rigorous Out-of-Sample Testing:** The system includes a walk-forward validation engine to ensure the chosen moving averages are not overfit to full-sample historical data.

## 🛠️ Project Architecture

The project is structured into distinct phases and modules, ensuring a clean pipeline from raw data to final PDF reports.

```
personal_trade/
├── config/
│   └── gayed_lrs_parameters.yaml      # Master configuration file
├── data/
│   ├── raw/                           # Raw OHLCV data from yfinance
│   └── processed/                     # Adjusted prices, indicators, and signals
├── docs/                              # Technical specifications and task breakdowns
├── reports/
│   ├── tables/                        # CSV outputs of all metrics
│   ├── final_strategy_review.md       # Synthesized markdown report
│   └── final_strategy_review.pdf      # Styled PDF report with charts
├── scripts/
│   ├── run_walk_forward.py            # CLI for walk-forward testing
│   ├── run_sensitivity.py             # CLI for EMA sensitivity analysis
│   └── export_pdf.py                  # CLI to generate the PDF report
├── src/
│   ├── backtest/                      # Core backtesting engines (fixed rule, walk-forward)
│   ├── data/                          # Data fetching and cleaning pipelines
│   ├── strategy/                      # Indicator and signal generation
│   └── reporting/                     # Report generation and formatting
└── tests/                             # Unit tests for backtest logic
```

## 🚀 How to Run the Pipeline

The pipeline is entirely driven by the `gayed_lrs_parameters.yaml` config file.

### 1. Configure the Strategy
Edit `config/gayed_lrs_parameters.yaml` to adjust the ETF universe, moving average lengths, execution mappings (1x, 2x, 3x), and transaction costs.

### 2. Run the Core Backtest (Fixed-Rule)
*(Assuming you have a script to run the base backtest, e.g., `python scripts/run_backtest.py`)*
This generates the core equity curves, trade logs, and base metrics for the full historical sample.

### 3. Run Walk-Forward Validation
Tests the strategy out-of-sample using rolling training (10 years) and testing (2 years) windows.
```bash
# Run for all configured ETFs
python scripts/run_walk_forward.py

# Run for a specific ETF
python scripts/run_walk_forward.py --tickers SPY
```

### 4. Run EMA Sensitivity Analysis
Validates if the chosen moving average is stable or overfit by testing a range of nearby values (EMA 180 to 210).
```bash
python scripts/run_sensitivity.py
```

### 5. Generate the Final PDF Report
Compiles the markdown review, embeds generated matplotlib charts (Equity Curves, Drawdowns, Sensitivity), and exports a styled PDF using WeasyPrint.
```bash
conda run -n final_project python scripts/export_pdf.py
```

## 📊 Key Findings (Phase 1)

1. **Drawdown Reduction:** The strategy successfully cuts maximum drawdowns by roughly half across major indices compared to buy-and-hold, while retaining the majority of the long-term CAGR.
2. **Leverage Scaling:** The strategy shines when applied to leveraged ETFs. For example, applying the EMA 200 timing rule to **TQQQ (3x QQQ)** historically produced a ~33% CAGR while reducing the max drawdown from a catastrophic 82% down to 58%.
3. **Parameter Stability:** Sensitivity analysis confirms that the results are not knife-edge anomalies. The Calmar ratios form a stable plateau across EMA lengths from 180 to 210.
4. **Out-of-Sample Robustness:** In walk-forward testing on SPY, the strategy generated positive returns in over 80% of unseen 2-year test windows.

## 🔜 Next Steps (Phase 2)

With Phase 1 (Research & Validation) complete, the project is moving towards live execution readiness:
- **Alert System:** Building a real-time alerting layer to evaluate end-of-day closing prices against the active moving average filter and trigger trade notifications.
- **Paper Trading:** Running the system forward on live data without capital at risk to monitor execution slippage and operational friction.

## Morning Email Alert

The repository includes a GitHub Actions workflow that can send a morning US-market alert by email:

```bash
python scripts/send_market_alert.py --dry-run --force-market
```

The alert refreshes data, rebuilds indicators/signals, and emails the latest confirmed recommendation for each configured signal ETF and candidate filter:

- `INVEST`: latest confirmed close crossed above the filter.
- `EXIT`: latest confirmed close crossed at or below the filter.
- `HOLD_INVESTED`: signal remains long.
- `HOLD_CASH`: signal remains risk-off.

False-breakout warnings are included for fresh `INVEST` alerts. They are probabilistic diagnostics based on historical whipsaw behavior, not proof that a new entry will fail.

To enable the workflow, add these GitHub repository secrets:

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
ALERT_EMAIL_FROM
ALERT_EMAIL_TO
```

For Gmail, use `smtp.gmail.com`, port `587`, your Gmail address as `SMTP_USERNAME`, and a Gmail App Password as `SMTP_PASSWORD`.
