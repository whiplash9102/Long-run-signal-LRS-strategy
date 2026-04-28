"""Fixed-rule leveraged ETF backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LONG = "LONG"
RISK_OFF = "RISK_OFF"
BUY_ALERT = "BUY_ALERT"
EXIT_ALERT = "EXIT_ALERT"
TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class ExecutionAsset:
    id: str
    ticker: str | None
    leverage: float
    mode: str


@dataclass(frozen=True)
class ExecutionMapping:
    signal_ticker: str
    execution_assets: tuple[ExecutionAsset, ...]


@dataclass(frozen=True)
class FixedRuleOutputs:
    equity_curves: Path
    trades: Path
    metrics: Path


def run_fixed_rule_backtest(config: dict[str, Any]) -> FixedRuleOutputs:
    prices_path = Path("data/processed/prices_adjusted.csv")
    signals_path = Path("data/processed/signals.csv")
    if not prices_path.exists():
        raise FileNotFoundError(f"Missing adjusted prices file: {prices_path}")
    if not signals_path.exists():
        raise FileNotFoundError(f"Missing signals file: {signals_path}")

    prices = pd.read_csv(prices_path)
    signals = pd.read_csv(signals_path)

    candidate_filter_ids = [item["id"] for item in config["strategy"]["candidate_filters"]]
    mappings = execution_mappings_from_config(config)
    cost_bps = (
        float(config["costs"]["commission_bps_per_side"])
        + float(config["costs"]["slippage_bps_per_side"])
        + float(config["costs"]["spread_bps_per_side"])
    )
    synthetic_fee_bps = float(config["costs"]["synthetic_leverage_fee_bps_per_year"])
    initial_capital = float(config["execution"]["initial_capital"])

    backtest = build_fixed_rule_backtest(
        prices=prices,
        signals=signals,
        mappings=mappings,
        candidate_filter_ids=candidate_filter_ids,
        cost_bps_per_side=cost_bps,
        synthetic_fee_bps_per_year=synthetic_fee_bps,
        initial_capital=initial_capital,
    )

    outputs = FixedRuleOutputs(
        equity_curves=Path("outputs/backtests/fixed_rule_equity_curves.csv"),
        trades=Path("outputs/backtests/fixed_rule_trades.csv"),
        metrics=Path("reports/tables/fixed_rule_metrics.csv"),
    )
    outputs.equity_curves.parent.mkdir(parents=True, exist_ok=True)
    outputs.trades.parent.mkdir(parents=True, exist_ok=True)
    outputs.metrics.parent.mkdir(parents=True, exist_ok=True)

    backtest["equity_curves"].to_csv(outputs.equity_curves, index=False)
    backtest["trades"].to_csv(outputs.trades, index=False)
    backtest["metrics"].to_csv(outputs.metrics, index=False)
    return outputs


def execution_mappings_from_config(config: dict[str, Any]) -> tuple[ExecutionMapping, ...]:
    mappings: list[ExecutionMapping] = []
    for item in config["data"]["leveraged_execution"]:
        mappings.append(
            ExecutionMapping(
                signal_ticker=item["signal_ticker"],
                execution_assets=tuple(
                    ExecutionAsset(
                        id=asset["id"],
                        ticker=asset.get("ticker"),
                        leverage=float(asset["leverage"]),
                        mode=asset["mode"],
                    )
                    for asset in item["execution_assets"]
                ),
            )
        )
    return tuple(mappings)


def build_fixed_rule_backtest(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    mappings: tuple[ExecutionMapping, ...],
    candidate_filter_ids: list[str],
    cost_bps_per_side: float,
    synthetic_fee_bps_per_year: float,
    initial_capital: float,
) -> dict[str, pd.DataFrame]:
    """Run strategy and buy-and-hold backtests for every configured mapping."""
    open_returns = build_open_to_open_returns(prices)
    all_equity_curves: list[pd.DataFrame] = []
    all_trade_logs: list[pd.DataFrame] = []
    all_metrics: list[pd.DataFrame] = []

    for mapping in mappings:
        mapping_signals = signals[
            (signals["ticker"] == mapping.signal_ticker)
            & (signals["filter_id"].isin(candidate_filter_ids))
        ].copy()
        for filter_id, filter_signals in mapping_signals.groupby("filter_id", sort=True):
            for execution_asset in mapping.execution_assets:
                combo = run_single_combination(
                    signals=filter_signals,
                    open_returns=open_returns,
                    signal_ticker=mapping.signal_ticker,
                    filter_id=filter_id,
                    execution_asset=execution_asset,
                    cost_bps_per_side=cost_bps_per_side,
                    synthetic_fee_bps_per_year=synthetic_fee_bps_per_year,
                    initial_capital=initial_capital,
                )
                if combo["equity_curve"].empty:
                    continue
                all_equity_curves.append(combo["equity_curve"])
                if not combo["trades"].empty:
                    all_trade_logs.append(combo["trades"])
                all_metrics.append(combo["metrics"])

    return {
        "equity_curves": pd.concat(all_equity_curves, ignore_index=True),
        "trades": pd.concat(all_trade_logs, ignore_index=True)
        if all_trade_logs
        else _empty_trade_log(),
        "metrics": pd.concat(all_metrics, ignore_index=True),
    }


def run_single_combination(
    signals: pd.DataFrame,
    open_returns: pd.DataFrame,
    signal_ticker: str,
    filter_id: str,
    execution_asset: ExecutionAsset,
    cost_bps_per_side: float,
    synthetic_fee_bps_per_year: float,
    initial_capital: float,
) -> dict[str, pd.DataFrame]:
    execution_returns = select_execution_returns(
        open_returns=open_returns,
        signal_ticker=signal_ticker,
        execution_asset=execution_asset,
        synthetic_fee_bps_per_year=synthetic_fee_bps_per_year,
    )
    prepared = prepare_strategy_rows(signals, execution_returns)
    if prepared.empty:
        return {
            "equity_curve": pd.DataFrame(),
            "trades": pd.DataFrame(),
            "metrics": pd.DataFrame(),
        }

    strategy_curve = build_strategy_curve(
        prepared=prepared,
        signal_ticker=signal_ticker,
        filter_id=filter_id,
        execution_asset=execution_asset,
        cost_bps_per_side=cost_bps_per_side,
        initial_capital=initial_capital,
    )
    benchmark_curve = build_buy_hold_curve(
        prepared=prepared,
        signal_ticker=signal_ticker,
        filter_id=filter_id,
        execution_asset=execution_asset,
        initial_capital=initial_capital,
    )
    trades = build_trade_log(
        strategy_curve=strategy_curve,
        signal_ticker=signal_ticker,
        filter_id=filter_id,
        execution_asset=execution_asset,
    )
    metrics = pd.concat(
        [
            calculate_metrics(strategy_curve, trades),
            calculate_metrics(benchmark_curve, pd.DataFrame()),
        ],
        ignore_index=True,
    )

    return {
        "equity_curve": pd.concat([strategy_curve, benchmark_curve], ignore_index=True),
        "trades": trades,
        "metrics": metrics,
    }


def build_open_to_open_returns(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices[["date", "ticker", "adjusted_open"]].copy()
    frame = frame.dropna(subset=["adjusted_open"])
    frame = frame.sort_values(["ticker", "date"]).reset_index(drop=True)
    frame["next_open"] = frame.groupby("ticker")["adjusted_open"].shift(-1)
    frame["open_to_open_return"] = frame["next_open"] / frame["adjusted_open"] - 1.0
    return frame[["date", "ticker", "adjusted_open", "open_to_open_return"]]


def select_execution_returns(
    open_returns: pd.DataFrame,
    signal_ticker: str,
    execution_asset: ExecutionAsset,
    synthetic_fee_bps_per_year: float,
) -> pd.DataFrame:
    if execution_asset.mode == "synthetic_from_signal_etf":
        base = open_returns[open_returns["ticker"] == signal_ticker].copy()
        daily_fee = synthetic_fee_bps_per_year / 10000.0 / TRADING_DAYS_PER_YEAR
        base["execution_return"] = (
            base["open_to_open_return"] * execution_asset.leverage - daily_fee
        ).clip(lower=-1.0)
        base["execution_price"] = base["adjusted_open"]
    else:
        if not execution_asset.ticker:
            raise ValueError(f"Observed execution asset requires ticker: {execution_asset.id}")
        base = open_returns[open_returns["ticker"] == execution_asset.ticker].copy()
        base["execution_return"] = base["open_to_open_return"]
        base["execution_price"] = base["adjusted_open"]

    return base[["date", "execution_price", "execution_return"]].dropna(
        subset=["execution_return"]
    )


def prepare_strategy_rows(signals: pd.DataFrame, execution_returns: pd.DataFrame) -> pd.DataFrame:
    rows = signals[signals["signal_is_tradable"]].copy()
    rows = rows[rows["current_state"].isin([LONG, RISK_OFF])]
    rows = rows.rename(columns={"date": "signal_date", "next_execution_date": "date"})
    rows = rows.merge(execution_returns, on="date", how="inner")
    return rows.sort_values("date").reset_index(drop=True)


def build_strategy_curve(
    prepared: pd.DataFrame,
    signal_ticker: str,
    filter_id: str,
    execution_asset: ExecutionAsset,
    cost_bps_per_side: float,
    initial_capital: float,
) -> pd.DataFrame:
    curve = _base_curve_frame(prepared, signal_ticker, filter_id, execution_asset, "strategy")
    curve["position_state"] = prepared["current_state"].values
    curve["gross_return"] = np.where(
        curve["position_state"].eq(LONG), prepared["execution_return"].values, 0.0
    )
    curve["trade_cost"] = np.where(
        prepared["signal_event"].isin([BUY_ALERT, EXIT_ALERT]),
        cost_bps_per_side / 10000.0,
        0.0,
    )
    curve["daily_return"] = curve["gross_return"] - curve["trade_cost"]
    curve["equity"] = initial_capital * (1.0 + curve["daily_return"]).cumprod()
    curve["exposure"] = np.where(curve["position_state"].eq(LONG), 1.0, 0.0)
    return curve


def build_buy_hold_curve(
    prepared: pd.DataFrame,
    signal_ticker: str,
    filter_id: str,
    execution_asset: ExecutionAsset,
    initial_capital: float,
) -> pd.DataFrame:
    curve = _base_curve_frame(prepared, signal_ticker, filter_id, execution_asset, "buy_hold")
    curve["position_state"] = LONG
    curve["gross_return"] = prepared["execution_return"].values
    curve["trade_cost"] = 0.0
    curve["daily_return"] = curve["gross_return"]
    curve["equity"] = initial_capital * (1.0 + curve["daily_return"]).cumprod()
    curve["exposure"] = 1.0
    return curve


def build_trade_log(
    strategy_curve: pd.DataFrame,
    signal_ticker: str,
    filter_id: str,
    execution_asset: ExecutionAsset,
) -> pd.DataFrame:
    events = strategy_curve[
        strategy_curve["signal_event"].isin([BUY_ALERT, EXIT_ALERT])
    ].copy()
    if events.empty:
        return _empty_trade_log()

    events["action"] = np.where(events["signal_event"].eq(BUY_ALERT), "BUY", "EXIT")
    events["signal_ticker"] = signal_ticker
    events["filter_id"] = filter_id
    events["execution_id"] = execution_asset.id
    events["execution_ticker"] = execution_asset.ticker or signal_ticker
    events["execution_mode"] = execution_asset.mode
    events["leverage"] = execution_asset.leverage
    return events[
        [
            "signal_ticker",
            "filter_id",
            "execution_id",
            "execution_ticker",
            "execution_mode",
            "leverage",
            "signal_date",
            "date",
            "action",
            "execution_price",
            "equity",
        ]
    ].rename(columns={"date": "execution_date"})


def calculate_metrics(curve: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    returns = curve["daily_return"].astype(float)
    equity = curve["equity"].astype(float)
    years = _years_between(curve["date"].iloc[0], curve["date"].iloc[-1])
    ending_equity = float(equity.iloc[-1])
    starting_equity = float(equity.iloc[0] / (1.0 + returns.iloc[0]))
    cagr = (ending_equity / starting_equity) ** (1.0 / years) - 1.0 if years > 0 else np.nan
    annualized_volatility = returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe = (
        returns.mean() / returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)
        if returns.std(ddof=0) > 0
        else np.nan
    )
    downside = returns[returns < 0]
    sortino = (
        returns.mean() / downside.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)
        if len(downside) > 1 and downside.std(ddof=0) > 0
        else np.nan
    )
    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    max_recovery_days = _max_recovery_days(curve)
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else np.nan
    trades_per_year = len(trades) / years if years > 0 and not trades.empty else 0.0
    trade_stats = _trade_stats(trades)
    worst_year = _worst_calendar_year(curve)

    row = {
        "signal_ticker": curve["signal_ticker"].iloc[0],
        "filter_id": curve["filter_id"].iloc[0],
        "execution_id": curve["execution_id"].iloc[0],
        "execution_ticker": curve["execution_ticker"].iloc[0],
        "execution_mode": curve["execution_mode"].iloc[0],
        "leverage": curve["leverage"].iloc[0],
        "result_type": curve["result_type"].iloc[0],
        "start_date": curve["date"].iloc[0],
        "end_date": curve["date"].iloc[-1],
        "years": years,
        "ending_equity": ending_equity,
        "total_return": ending_equity / starting_equity - 1.0,
        "CAGR": cagr,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "max_drawdown": max_drawdown,
        "max_recovery_days": max_recovery_days,
        "exposure_pct": float(curve["exposure"].mean()),
        "trades_per_year": trades_per_year,
        "trade_count": len(trades),
        "round_trip_count": trade_stats["round_trip_count"],
        "average_hold_days": trade_stats["average_hold_days"],
        "win_rate_by_trade": trade_stats["win_rate_by_trade"],
        "profit_factor": trade_stats["profit_factor"],
        "worst_year": worst_year,
    }
    return pd.DataFrame([row])


def _base_curve_frame(
    prepared: pd.DataFrame,
    signal_ticker: str,
    filter_id: str,
    execution_asset: ExecutionAsset,
    result_type: str,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": prepared["date"],
            "signal_date": prepared["signal_date"],
            "signal_ticker": signal_ticker,
            "filter_id": filter_id,
            "execution_id": execution_asset.id,
            "execution_ticker": execution_asset.ticker or signal_ticker,
            "execution_mode": execution_asset.mode,
            "leverage": execution_asset.leverage,
            "result_type": result_type,
            "signal_event": prepared["signal_event"],
            "execution_price": prepared["execution_price"],
        }
    )


def _years_between(start: str, end: str) -> float:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return max((end_ts - start_ts).days / 365.25, 1 / TRADING_DAYS_PER_YEAR)


def _worst_calendar_year(curve: pd.DataFrame) -> float:
    yearly = curve[["date", "daily_return"]].copy()
    yearly["year"] = pd.to_datetime(yearly["date"]).dt.year
    year_returns = yearly.groupby("year")["daily_return"].apply(lambda x: (1.0 + x).prod() - 1.0)
    return float(year_returns.min()) if not year_returns.empty else np.nan


def _max_recovery_days(curve: pd.DataFrame) -> int:
    dates = pd.to_datetime(curve["date"]).reset_index(drop=True)
    equity = curve["equity"].reset_index(drop=True)
    running_peak = equity.cummax()

    peak_date = dates.iloc[0]
    max_days = 0
    for index, value in equity.items():
        if value >= running_peak.iloc[index]:
            peak_date = dates.iloc[index]
            continue
        days = (dates.iloc[index] - peak_date).days
        max_days = max(max_days, int(days))
    return max_days


def _trade_stats(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {
            "round_trip_count": 0,
            "average_hold_days": np.nan,
            "win_rate_by_trade": np.nan,
            "profit_factor": np.nan,
        }

    round_trips: list[dict[str, float]] = []
    open_trade: pd.Series | None = None
    ordered = trades.sort_values("execution_date")
    for _, trade in ordered.iterrows():
        if trade["action"] == "BUY":
            open_trade = trade
            continue
        if trade["action"] == "EXIT" and open_trade is not None:
            entry_equity = float(open_trade["equity"])
            exit_equity = float(trade["equity"])
            round_trips.append(
                {
                    "return": exit_equity / entry_equity - 1.0,
                    "hold_days": (
                        pd.Timestamp(trade["execution_date"])
                        - pd.Timestamp(open_trade["execution_date"])
                    ).days,
                }
            )
            open_trade = None

    if not round_trips:
        return {
            "round_trip_count": 0,
            "average_hold_days": np.nan,
            "win_rate_by_trade": np.nan,
            "profit_factor": np.nan,
        }

    trade_returns = pd.Series([item["return"] for item in round_trips])
    hold_days = pd.Series([item["hold_days"] for item in round_trips])
    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]
    profit_factor = (
        float(wins.sum() / abs(losses.sum()))
        if not wins.empty and not losses.empty and abs(losses.sum()) > 0
        else np.nan
    )

    return {
        "round_trip_count": len(round_trips),
        "average_hold_days": float(hold_days.mean()),
        "win_rate_by_trade": float((trade_returns > 0).mean()),
        "profit_factor": profit_factor,
    }


def _empty_trade_log() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "signal_ticker",
            "filter_id",
            "execution_id",
            "execution_ticker",
            "execution_mode",
            "leverage",
            "signal_date",
            "execution_date",
            "action",
            "execution_price",
            "equity",
        ]
    )
