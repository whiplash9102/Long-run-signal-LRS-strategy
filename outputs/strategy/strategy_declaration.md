# Strategy Declaration

## Core Rule

- Strategy: `Gayed_LRS_Long_Only`
- Direction: `long_only`
- Portfolio mode: `independent_single_asset_tests`
- Signal layer: normal ETF close versus moving-average filter
- Risk-on state: long the configured execution asset
- Risk-off state: `CASH`
- Entry: close crosses from at/below filter to above filter
- Exit: close crosses from above filter to at/below filter
- Signal timing: `confirmed_daily_close`
- Execution timing: `next_session_open`
- Position size: `100%`
- Initial capital: `$100,000`

## ETF Universe

| Ticker | Region | Exposure | Role |
| --- | --- | --- | --- |
| `SPY` | US | S&P 500 large-cap equities | paper_baseline |
| `QQQ` | US | Nasdaq-100 growth and technology-heavy equities | us_variant |
| `IWM` | US | Russell 2000 small-cap equities | us_variant |
| `VGK` | Europe | Developed Europe equities | europe_variant |
| `EZU` | Europe | Eurozone large- and mid-cap equities | europe_variant |

## Leveraged Execution Map

| Signal ETF | Execution ID | Execution Ticker | Leverage | Mode |
| --- | --- | --- | --- | --- |
| `SPY` | `SPY_1X` | `SPY` | 1.0x | `observed_etf` |
| `SPY` | `SSO_2X` | `SSO` | 2.0x | `observed_leveraged_etf` |
| `SPY` | `UPRO_3X` | `UPRO` | 3.0x | `observed_leveraged_etf` |
| `QQQ` | `QQQ_1X` | `QQQ` | 1.0x | `observed_etf` |
| `QQQ` | `QLD_2X` | `QLD` | 2.0x | `observed_leveraged_etf` |
| `QQQ` | `TQQQ_3X` | `TQQQ` | 3.0x | `observed_leveraged_etf` |
| `IWM` | `IWM_1X` | `IWM` | 1.0x | `observed_etf` |
| `IWM` | `UWM_2X` | `UWM` | 2.0x | `observed_leveraged_etf` |
| `IWM` | `TNA_3X` | `TNA` | 3.0x | `observed_leveraged_etf` |
| `VGK` | `VGK_1X` | `VGK` | 1.0x | `observed_etf` |
| `VGK` | `VGK_SYNTHETIC_2X` | `synthetic` | 2.0x | `synthetic_from_signal_etf` |
| `VGK` | `VGK_SYNTHETIC_3X` | `synthetic` | 3.0x | `synthetic_from_signal_etf` |
| `EZU` | `EZU_1X` | `EZU` | 1.0x | `observed_etf` |
| `EZU` | `EZU_SYNTHETIC_2X` | `synthetic` | 2.0x | `synthetic_from_signal_etf` |
| `EZU` | `EZU_SYNTHETIC_3X` | `synthetic` | 3.0x | `synthetic_from_signal_etf` |

## Filters

Baseline:

- `SMA_200`: SMA 200

Candidates:

- `SMA_200`: SMA 200
- `EMA_190`: EMA 190
- `EMA_195`: EMA 195
- `EMA_200`: EMA 200

## False Breakout Handling

- Trading filter enabled: `false`
- Diagnostics enabled: `true`
- Whipsaw definition: `round_trip_exit_within_n_sessions_after_entry`
- Whipsaw window: `20` sessions
- Decision rule: `measure_first_then_decide_after_phase_1_backtest`

Professional stance:

- Phase 1 measures false breakouts but does not filter them.
- A false-breakout filter can be tested later only if whipsaw evidence is material.
