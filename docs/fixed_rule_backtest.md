# Fixed-Rule Leveraged Backtest

## Purpose

This backtest answers the first profitability question:

```text
If the normal ETF is above the selected moving average, is holding the configured leveraged ETF profitable?
```

## Inputs

```text
data/processed/prices_adjusted.csv
data/processed/signals.csv
config/gayed_lrs_parameters.yaml
```

## Signal And Execution

The signal comes from the normal ETF:

- `SPY`
- `QQQ`
- `IWM`
- `VGK`
- `EZU`

When the signal is `LONG`, the backtest holds the configured execution asset:

- `SPY -> SPY / SSO / UPRO`
- `QQQ -> QQQ / QLD / TQQQ`
- `IWM -> IWM / UWM / TNA`
- `VGK -> VGK / synthetic 2x / synthetic 3x`
- `EZU -> EZU / synthetic 2x / synthetic 3x`

When the signal is `RISK_OFF`, the backtest holds `CASH`.

## Return Timing

Signals are confirmed after the close.

Trades execute at the next session open.

The backtest uses open-to-open returns:

```text
return = next_adjusted_open / current_adjusted_open - 1
```

For a signal generated after today close, the return starts at tomorrow open.

## Synthetic Leverage

For synthetic Europe leverage:

```text
synthetic_return = leverage * signal_etf_open_to_open_return - daily_leverage_fee
```

The daily leverage fee comes from:

```text
synthetic_leverage_fee_bps_per_year / 252
```

Synthetic returns are floored at `-100%`.

## Costs

The strategy applies one-side cost on each `BUY_ALERT` and `EXIT_ALERT`:

```text
commission + slippage + spread
```

Buy-and-hold benchmark rows do not apply recurring trade costs.

## Outputs

```text
outputs/backtests/fixed_rule_equity_curves.csv
outputs/backtests/fixed_rule_trades.csv
reports/tables/fixed_rule_metrics.csv
```

## Review Checklist

- Compare `strategy` versus `buy_hold` for each execution asset.
- Check `CAGR` and `max_drawdown` together.
- Check `max_recovery_days` to understand how long capital stayed underwater.
- Check `average_hold_days`, `win_rate_by_trade`, and `profit_factor` to understand trade quality.
- Treat high CAGR with extreme drawdown as risky, not automatically good.
- Compare observed leveraged ETFs separately from synthetic leverage.
