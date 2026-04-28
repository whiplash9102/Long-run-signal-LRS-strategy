"""Walk-forward validation engine for the Gayed LRS project.

Methodology
-----------
For each rolling window:
  1. Run the strategy backtest for every candidate filter over the TRAINING period,
     using the 1x (unlevered) execution asset for scoring only.
  2. Compute a composite score from the configured score_weights.
  3. Select the filter with the highest composite score.
  4. Run the strategy on the TEST period using the selected filter for ALL execution assets.

Windows
-------
- Training window: ``training_window_years`` years ending at test_start.
- Test window    : ``test_window_years`` years starting at test_start.
- Step           : advance test_start by ``step_months`` each iteration.
- Skip windows where the training period has fewer than training_window_years of data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.fixed_rule import (
    ExecutionAsset,
    ExecutionMapping,
    build_open_to_open_returns,
    build_strategy_curve,
    build_trade_log,
    calculate_metrics,
    execution_mappings_from_config,
    prepare_strategy_rows,
    select_execution_returns,
)


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str


@dataclass(frozen=True)
class WalkForwardOutputs:
    results: Path
    filter_scores: Path
    summary: Path


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_walk_forward(
    config: dict[str, Any],
    signal_tickers: list[str] | None = None,
) -> WalkForwardOutputs:
    """Run walk-forward validation and write output files.

    Parameters
    ----------
    config:
        Loaded and validated strategy config dict.
    signal_tickers:
        Optional list of signal tickers to restrict the run. ``None`` means
        all tickers in the configured execution mappings. Pass ``["SPY"]`` to
        validate SPY only.
    """
    prices_path = Path("data/processed/prices_adjusted.csv")
    signals_path = Path("data/processed/signals.csv")
    if not prices_path.exists():
        raise FileNotFoundError(f"Missing adjusted prices file: {prices_path}")
    if not signals_path.exists():
        raise FileNotFoundError(f"Missing signals file: {signals_path}")

    prices = pd.read_csv(prices_path)
    signals = pd.read_csv(signals_path)

    wf_cfg = config["backtest"]["walk_forward"]
    training_years: int = int(wf_cfg["training_window_years"])
    test_years: int = int(wf_cfg["test_window_years"])
    step_months: int = int(wf_cfg["step_months"])
    score_weights: dict[str, float] = wf_cfg["score_weights"]

    candidate_filter_ids: list[str] = [
        item["id"] for item in config["strategy"]["candidate_filters"]
    ]
    mappings: tuple[ExecutionMapping, ...] = execution_mappings_from_config(config)
    cost_bps: float = (
        float(config["costs"]["commission_bps_per_side"])
        + float(config["costs"]["slippage_bps_per_side"])
        + float(config["costs"]["spread_bps_per_side"])
    )
    synthetic_fee_bps: float = float(config["costs"]["synthetic_leverage_fee_bps_per_year"])
    initial_capital: float = float(config["execution"]["initial_capital"])

    # Scoring uses the 1x unlevered observed ETF only
    scoring_assets: dict[str, ExecutionAsset] = _scoring_assets_from_mappings(mappings)
    open_returns: pd.DataFrame = build_open_to_open_returns(prices)

    all_results: list[pd.DataFrame] = []
    all_filter_scores: list[pd.DataFrame] = []

    for mapping in mappings:
        ticker = mapping.signal_ticker
        if signal_tickers is not None and ticker not in signal_tickers:
            continue
        if ticker not in scoring_assets:
            continue

        scoring_asset = scoring_assets[ticker]
        ticker_signals = signals[
            (signals["ticker"] == ticker)
            & (signals["filter_id"].isin(candidate_filter_ids))
        ].copy()

        # All available execution dates for this ticker (union across filters)
        all_exec_dates: list[str] = sorted(
            ticker_signals[ticker_signals["signal_is_tradable"]]["next_execution_date"]
            .dropna()
            .unique()
            .tolist()
        )
        if not all_exec_dates:
            continue

        windows = generate_windows(
            dates=all_exec_dates,
            training_years=training_years,
            test_years=test_years,
            step_months=step_months,
        )
        if not windows:
            continue

        for window in windows:
            # ------------------------------------------------------------------
            # Step 1: Score every candidate filter on the TRAINING period
            # ------------------------------------------------------------------
            filter_score_rows: list[dict[str, Any]] = []

            for fid in candidate_filter_ids:
                f_signals = ticker_signals[ticker_signals["filter_id"] == fid]
                train_metrics = _run_window_backtest(
                    signals=f_signals,
                    open_returns=open_returns,
                    signal_ticker=ticker,
                    filter_id=fid,
                    execution_asset=scoring_asset,
                    cost_bps_per_side=cost_bps,
                    synthetic_fee_bps_per_year=synthetic_fee_bps,
                    initial_capital=initial_capital,
                    date_start=window.train_start,
                    date_end=window.train_end,
                )
                if train_metrics is None:
                    continue

                score = _composite_score(train_metrics, score_weights)
                filter_score_rows.append({
                    "signal_ticker": ticker,
                    "window_id": window.window_id,
                    "train_start": window.train_start,
                    "train_end": window.train_end,
                    "test_start": window.test_start,
                    "test_end": window.test_end,
                    "filter_id": fid,
                    "composite_score": score,
                    "train_CAGR": train_metrics["CAGR"],
                    "train_sharpe_ratio": train_metrics["sharpe_ratio"],
                    "train_sortino_ratio": train_metrics["sortino_ratio"],
                    "train_max_drawdown": train_metrics["max_drawdown"],
                    "train_calmar_ratio": train_metrics["calmar_ratio"],
                    "train_exposure_pct": train_metrics["exposure_pct"],
                })

            if not filter_score_rows:
                continue

            scores_df = pd.DataFrame(filter_score_rows)
            all_filter_scores.append(scores_df)

            # ------------------------------------------------------------------
            # Step 2: Select the highest-scoring filter
            # ------------------------------------------------------------------
            best_row = scores_df.loc[scores_df["composite_score"].idxmax()]
            selected_filter: str = str(best_row["filter_id"])

            # ------------------------------------------------------------------
            # Step 3: Test the selected filter on the TEST period for ALL assets
            # ------------------------------------------------------------------
            for execution_asset in mapping.execution_assets:
                sel_signals = ticker_signals[ticker_signals["filter_id"] == selected_filter]
                test_metrics = _run_window_backtest(
                    signals=sel_signals,
                    open_returns=open_returns,
                    signal_ticker=ticker,
                    filter_id=selected_filter,
                    execution_asset=execution_asset,
                    cost_bps_per_side=cost_bps,
                    synthetic_fee_bps_per_year=synthetic_fee_bps,
                    initial_capital=initial_capital,
                    date_start=window.test_start,
                    date_end=window.test_end,
                )
                if test_metrics is None:
                    continue

                all_results.append(pd.DataFrame([{
                    "signal_ticker": ticker,
                    "window_id": window.window_id,
                    "train_start": window.train_start,
                    "train_end": window.train_end,
                    "test_start": window.test_start,
                    "test_end": window.test_end,
                    "selected_filter": selected_filter,
                    "train_composite_score": float(best_row["composite_score"]),
                    "train_CAGR": float(best_row["train_CAGR"]),
                    "train_sharpe_ratio": float(best_row["train_sharpe_ratio"]),
                    "train_max_drawdown": float(best_row["train_max_drawdown"]),
                    "execution_id": execution_asset.id,
                    "execution_ticker": execution_asset.ticker or ticker,
                    "execution_mode": execution_asset.mode,
                    "leverage": execution_asset.leverage,
                    "test_CAGR": test_metrics["CAGR"],
                    "test_sharpe_ratio": test_metrics["sharpe_ratio"],
                    "test_sortino_ratio": test_metrics["sortino_ratio"],
                    "test_max_drawdown": test_metrics["max_drawdown"],
                    "test_calmar_ratio": test_metrics["calmar_ratio"],
                    "test_exposure_pct": test_metrics["exposure_pct"],
                    "test_trade_count": test_metrics["trade_count"],
                    "test_win_rate": test_metrics["win_rate_by_trade"],
                }]))

    # --------------------------------------------------------------------------
    # Write outputs
    # --------------------------------------------------------------------------
    outputs = WalkForwardOutputs(
        results=Path("outputs/backtests/walk_forward_results.csv"),
        filter_scores=Path("outputs/backtests/walk_forward_filter_scores.csv"),
        summary=Path("reports/tables/walk_forward_summary.csv"),
    )
    for path in (outputs.results, outputs.filter_scores, outputs.summary):
        path.parent.mkdir(parents=True, exist_ok=True)

    results_df = (
        pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()
    )
    filter_scores_df = (
        pd.concat(all_filter_scores, ignore_index=True)
        if all_filter_scores
        else pd.DataFrame()
    )
    summary_df = _build_summary(results_df) if not results_df.empty else pd.DataFrame()

    results_df.to_csv(outputs.results, index=False)
    filter_scores_df.to_csv(outputs.filter_scores, index=False)
    summary_df.to_csv(outputs.summary, index=False)

    return outputs


# ---------------------------------------------------------------------------
# Window generation
# ---------------------------------------------------------------------------

def generate_windows(
    dates: list[str],
    training_years: int,
    test_years: int,
    step_months: int,
) -> list[WalkForwardWindow]:
    """Return a list of walk-forward windows from the available execution dates.

    Windows where the training span is shorter than ``training_years`` are skipped.
    """
    if not dates:
        return []

    date_ts = pd.to_datetime(sorted(dates))
    first_date = date_ts[0]
    last_date = date_ts[-1]

    windows: list[WalkForwardWindow] = []
    window_id = 1
    test_start = first_date + pd.DateOffset(years=training_years)

    while True:
        test_end = test_start + pd.DateOffset(years=test_years)
        if test_end > last_date:
            break

        train_start = test_start - pd.DateOffset(years=training_years)
        train_end = test_start

        # Verify the actual training span is close enough to training_years
        actual_years = (train_end - train_start).days / 365.25
        train_rows = int(((date_ts >= train_start) & (date_ts < train_end)).sum())
        if actual_years < training_years - 0.1 or train_rows < 200:
            test_start += pd.DateOffset(months=step_months)
            continue

        windows.append(WalkForwardWindow(
            window_id=window_id,
            train_start=train_start.strftime("%Y-%m-%d"),
            train_end=train_end.strftime("%Y-%m-%d"),
            test_start=test_start.strftime("%Y-%m-%d"),
            test_end=test_end.strftime("%Y-%m-%d"),
        ))
        window_id += 1
        test_start += pd.DateOffset(months=step_months)

    return windows


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_window_backtest(
    signals: pd.DataFrame,
    open_returns: pd.DataFrame,
    signal_ticker: str,
    filter_id: str,
    execution_asset: ExecutionAsset,
    cost_bps_per_side: float,
    synthetic_fee_bps_per_year: float,
    initial_capital: float,
    date_start: str,
    date_end: str,
) -> dict[str, Any] | None:
    """Run backtest over a date range and return a metrics dict, or None if insufficient data."""
    # Filter signals to the execution-date window [date_start, date_end)
    window_sigs = signals[
        (signals["next_execution_date"] >= date_start)
        & (signals["next_execution_date"] < date_end)
    ].copy()

    if window_sigs.empty or int(window_sigs["signal_is_tradable"].sum()) < 5:
        return None

    exec_returns = select_execution_returns(
        open_returns=open_returns,
        signal_ticker=signal_ticker,
        execution_asset=execution_asset,
        synthetic_fee_bps_per_year=synthetic_fee_bps_per_year,
    )
    exec_returns = exec_returns[
        (exec_returns["date"] >= date_start)
        & (exec_returns["date"] < date_end)
    ]

    prepared = prepare_strategy_rows(window_sigs, exec_returns)
    if prepared.empty or len(prepared) < 5:
        return None

    curve = build_strategy_curve(
        prepared=prepared,
        signal_ticker=signal_ticker,
        filter_id=filter_id,
        execution_asset=execution_asset,
        cost_bps_per_side=cost_bps_per_side,
        initial_capital=initial_capital,
    )
    trades = build_trade_log(
        strategy_curve=curve,
        signal_ticker=signal_ticker,
        filter_id=filter_id,
        execution_asset=execution_asset,
    )
    metrics_df = calculate_metrics(curve, trades)
    return metrics_df.iloc[0].to_dict()


def _composite_score(metrics: dict[str, Any], score_weights: dict[str, float]) -> float:
    """Weighted composite score.

    ``max_drawdown_penalty`` uses ``max_drawdown`` directly (which is negative),
    so larger drawdowns produce a more negative contribution and a lower score.
    All other metrics are used directly (higher = better).
    """
    def _safe(key: str) -> float:
        v = metrics.get(key)
        return float(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else 0.0

    return (
        float(score_weights.get("cagr", 0.0)) * _safe("CAGR")
        + float(score_weights.get("sharpe_ratio", 0.0)) * _safe("sharpe_ratio")
        + float(score_weights.get("sortino_ratio", 0.0)) * _safe("sortino_ratio")
        + float(score_weights.get("max_drawdown_penalty", 0.0)) * _safe("max_drawdown")
        + float(score_weights.get("calmar_ratio", 0.0)) * _safe("calmar_ratio")
    )


def _scoring_assets_from_mappings(
    mappings: tuple[ExecutionMapping, ...],
) -> dict[str, ExecutionAsset]:
    """Return the 1x observed ETF per signal ticker. Used for filter scoring only."""
    result: dict[str, ExecutionAsset] = {}
    for mapping in mappings:
        candidates = [
            a for a in mapping.execution_assets
            if a.mode == "observed_etf" and a.leverage == 1.0
        ]
        if candidates:
            result[mapping.signal_ticker] = candidates[0]
    return result


def _build_summary(results: pd.DataFrame) -> pd.DataFrame:
    """Aggregate walk-forward results into a per-(signal_ticker, execution_id) summary."""
    if results.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for (ticker, exec_id), grp in results.groupby(["signal_ticker", "execution_id"], sort=True):
        freq = grp["selected_filter"].value_counts(normalize=True)
        rows.append({
            "signal_ticker": ticker,
            "execution_id": exec_id,
            "windows_tested": len(grp),
            "dominant_filter": freq.index[0],
            "dominant_filter_selected_pct": round(float(freq.iloc[0]) * 100, 1),
            "pct_windows_positive_cagr": round(float((grp["test_CAGR"] > 0).mean()) * 100, 1),
            "median_test_CAGR": round(float(grp["test_CAGR"].median()), 4),
            "median_test_sharpe": round(float(grp["test_sharpe_ratio"].median()), 4),
            "median_test_max_drawdown": round(float(grp["test_max_drawdown"].median()), 4),
            "median_test_calmar": round(float(grp["test_calmar_ratio"].median()), 4),
            "median_test_exposure_pct": round(float(grp["test_exposure_pct"].median()), 4),
        })
    return pd.DataFrame(rows)
