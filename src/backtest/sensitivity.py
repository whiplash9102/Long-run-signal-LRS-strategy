"""EMA sensitivity review for the Gayed LRS project (Phase 8).

Purpose
-------
Test whether EMA performance is stable or fragile around the candidate values.
A stable result means CAGR / Sharpe / Calmar change gradually across EMA lengths.
A fragile (overfit) result means one length spikes and neighbors collapse.

Method
------
- Run the full fixed-rule backtest for every EMA length in the configured
  sensitivity range (EMA 180–210, step 5).
- The data is already in ``signals.csv`` — no re-download needed.
- Score each EMA length with the same composite score used in walk-forward.
- Compute a stability metric: coefficient of variation (CV) of Calmar ratio
  across the range. Low CV = stable plateau. High CV = fragile spike.
- Output a ranked table and a markdown stability report.
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
class SensitivityOutputs:
    metrics: Path
    report: Path


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_sensitivity_review(
    config: dict[str, Any],
    signal_tickers: list[str] | None = None,
) -> SensitivityOutputs:
    """Run EMA sensitivity review and write output files.

    Parameters
    ----------
    config:
        Loaded and validated strategy config dict.
    signal_tickers:
        Restrict to specific signal tickers. ``None`` means all configured.
    """
    prices_path = Path("data/processed/prices_adjusted.csv")
    signals_path = Path("data/processed/signals.csv")
    if not prices_path.exists():
        raise FileNotFoundError(f"Missing adjusted prices file: {prices_path}")
    if not signals_path.exists():
        raise FileNotFoundError(f"Missing signals file: {signals_path}")

    prices = pd.read_csv(prices_path)
    signals = pd.read_csv(signals_path)

    sensitivity_cfg = config["strategy"]["sensitivity_filters"]
    sensitivity_filter_ids: list[str] = [
        f"{sensitivity_cfg['type']}_{length}"
        for length in range(
            int(sensitivity_cfg["min_length"]),
            int(sensitivity_cfg["max_length"]) + 1,
            int(sensitivity_cfg["step"]),
        )
    ]
    candidate_filter_ids: list[str] = [
        item["id"] for item in config["strategy"]["candidate_filters"]
    ]
    # All filter IDs to test = sensitivity range (includes the candidates)
    all_filter_ids: list[str] = sorted(set(sensitivity_filter_ids) | set(candidate_filter_ids))

    mappings: tuple[ExecutionMapping, ...] = execution_mappings_from_config(config)
    cost_bps: float = (
        float(config["costs"]["commission_bps_per_side"])
        + float(config["costs"]["slippage_bps_per_side"])
        + float(config["costs"]["spread_bps_per_side"])
    )
    synthetic_fee_bps: float = float(config["costs"]["synthetic_leverage_fee_bps_per_year"])
    initial_capital: float = float(config["execution"]["initial_capital"])
    score_weights: dict[str, float] = config["backtest"]["walk_forward"]["score_weights"]

    open_returns: pd.DataFrame = build_open_to_open_returns(prices)

    # For sensitivity review use the 1x observed ETF only (clean comparison)
    scoring_assets: dict[str, ExecutionAsset] = _scoring_assets_from_mappings(mappings)

    all_rows: list[pd.DataFrame] = []

    for mapping in mappings:
        ticker = mapping.signal_ticker
        if signal_tickers is not None and ticker not in signal_tickers:
            continue
        if ticker not in scoring_assets:
            continue

        scoring_asset = scoring_assets[ticker]

        for fid in all_filter_ids:
            filter_signals = signals[
                (signals["ticker"] == ticker) & (signals["filter_id"] == fid)
            ].copy()
            if filter_signals.empty:
                continue

            exec_returns = select_execution_returns(
                open_returns=open_returns,
                signal_ticker=ticker,
                execution_asset=scoring_asset,
                synthetic_fee_bps_per_year=synthetic_fee_bps,
            )
            prepared = prepare_strategy_rows(filter_signals, exec_returns)
            if prepared.empty or len(prepared) < 50:
                continue

            curve = build_strategy_curve(
                prepared=prepared,
                signal_ticker=ticker,
                filter_id=fid,
                execution_asset=scoring_asset,
                cost_bps_per_side=cost_bps,
                initial_capital=initial_capital,
            )
            trades = build_trade_log(
                strategy_curve=curve,
                signal_ticker=ticker,
                filter_id=fid,
                execution_asset=scoring_asset,
            )
            metrics_df = calculate_metrics(curve, trades)
            row = metrics_df.iloc[0].to_dict()

            is_candidate = fid in candidate_filter_ids
            ema_length = int(fid.split("_")[1]) if "_" in fid else 0
            score = _composite_score(row, score_weights)

            all_rows.append(pd.DataFrame([{
                "signal_ticker": ticker,
                "filter_id": fid,
                "ema_length": ema_length,
                "is_candidate": is_candidate,
                "composite_score": round(score, 6),
                "CAGR": row.get("CAGR"),
                "annualized_volatility": row.get("annualized_volatility"),
                "sharpe_ratio": row.get("sharpe_ratio"),
                "sortino_ratio": row.get("sortino_ratio"),
                "calmar_ratio": row.get("calmar_ratio"),
                "max_drawdown": row.get("max_drawdown"),
                "exposure_pct": row.get("exposure_pct"),
                "trades_per_year": row.get("trades_per_year"),
                "average_hold_days": row.get("average_hold_days"),
                "win_rate_by_trade": row.get("win_rate_by_trade"),
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
            }]))

    if not all_rows:
        raise ValueError("No sensitivity rows were generated. Check signals.csv contains sensitivity filter IDs.")

    results_df = (
        pd.concat(all_rows, ignore_index=True)
        .sort_values(["signal_ticker", "ema_length"])
        .reset_index(drop=True)
    )

    outputs = SensitivityOutputs(
        metrics=Path("reports/tables/parameter_sensitivity.csv"),
        report=Path("reports/ema_sensitivity_review.md"),
    )
    outputs.metrics.parent.mkdir(parents=True, exist_ok=True)
    outputs.report.parent.mkdir(parents=True, exist_ok=True)

    results_df.to_csv(outputs.metrics, index=False)
    report = _render_sensitivity_report(results_df, candidate_filter_ids)
    outputs.report.write_text(report, encoding="utf-8")

    return outputs


# ---------------------------------------------------------------------------
# Stability analysis
# ---------------------------------------------------------------------------

def compute_stability(results: pd.DataFrame) -> pd.DataFrame:
    """Compute per-ticker stability metrics across the EMA sensitivity range.

    Returns a DataFrame with one row per signal_ticker containing:
    - calmar_cv      : coefficient of variation of Calmar ratio (lower = more stable)
    - cagr_cv        : coefficient of variation of CAGR
    - calmar_range   : max - min Calmar across the EMA range
    - best_filter    : EMA length with highest composite_score
    - stability_note : 'stable' if calmar_cv < 0.30, else 'fragile'
    """
    rows: list[dict[str, Any]] = []
    for ticker, grp in results.groupby("signal_ticker", sort=True):
        calmar = grp["calmar_ratio"].dropna()
        cagr = grp["CAGR"].dropna()

        calmar_cv = float(calmar.std() / calmar.mean()) if calmar.mean() != 0 else np.nan
        cagr_cv = float(cagr.std() / cagr.mean()) if cagr.mean() != 0 else np.nan
        calmar_range = float(calmar.max() - calmar.min()) if not calmar.empty else np.nan

        best_idx = grp["composite_score"].idxmax()
        best_filter = grp.loc[best_idx, "filter_id"]

        stability_note = "stable" if (not np.isnan(calmar_cv) and calmar_cv < 0.30) else "fragile"

        rows.append({
            "signal_ticker": ticker,
            "best_filter": best_filter,
            "calmar_cv": round(calmar_cv, 4) if not np.isnan(calmar_cv) else None,
            "cagr_cv": round(cagr_cv, 4) if not np.isnan(cagr_cv) else None,
            "calmar_range": round(calmar_range, 4) if not np.isnan(calmar_range) else None,
            "stability_note": stability_note,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------

def _render_sensitivity_report(
    results: pd.DataFrame,
    candidate_filter_ids: list[str],
) -> str:
    stability = compute_stability(results)

    ticker_sections: list[str] = []
    for ticker, grp in results.groupby("signal_ticker", sort=True):
        grp = grp.sort_values("ema_length").copy()
        stab = stability[stability["signal_ticker"] == ticker].iloc[0]

        # Build per-filter table
        table_rows = []
        for _, row in grp.iterrows():
            marker = " ← candidate" if row["filter_id"] in candidate_filter_ids else ""
            table_rows.append(
                f"| `{row['filter_id']}` | "
                f"{_pct(row['CAGR'])} | "
                f"{_pct(row['max_drawdown'])} | "
                f"{_num(row['calmar_ratio'])} | "
                f"{_num(row['sharpe_ratio'])} | "
                f"{_num(row['composite_score'])} |"
                f"{marker}"
            )

        table = (
            "| Filter | CAGR | Max DD | Calmar | Sharpe | Score | Notes |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            + "\n".join(table_rows)
        )

        ticker_sections.append(f"""## {ticker}

{table}

**Stability:** {stab['stability_note'].upper()} — Calmar CV = {stab['calmar_cv']}, range = {stab['calmar_range']}  
**Best filter by composite score:** `{stab['best_filter']}`
""")

    ticker_body = "\n".join(ticker_sections)

    # Stability summary table
    stab_table_rows = []
    for _, row in stability.iterrows():
        stab_table_rows.append(
            f"| `{row['signal_ticker']}` | `{row['best_filter']}` | "
            f"{row['calmar_cv']} | {row['calmar_range']} | **{row['stability_note'].upper()}** |"
        )
    stab_table = (
        "| Ticker | Best Filter | Calmar CV | Calmar Range | Verdict |\n"
        "| --- | --- | --- | --- | --- |\n"
        + "\n".join(stab_table_rows)
    )

    tickers_run = ", ".join(f"`{t}`" for t in sorted(results["signal_ticker"].unique()))

    return f"""# EMA Sensitivity Review

## Purpose

Check whether EMA performance across lengths 180–210 is stable or concentrated
in a narrow spike that would indicate overfitting.

**Tickers reviewed:** {tickers_run}  
**Metric used for ranking:** composite score (CAGR 25%, Sharpe 25%, Sortino 20%, Drawdown penalty 20%, Calmar 10%)  
**Execution asset:** 1x unlevered ETF per signal ticker  

## Stability Verdict

{stab_table}

**Interpretation:**
- `Calmar CV` = coefficient of variation of Calmar ratio across EMA 180–210. Lower = more stable.
- CV < 0.30 → **STABLE** (results form a consistent plateau; not a knife-edge)
- CV ≥ 0.30 → **FRAGILE** (results spike at one value; likely overfit)

## Per-Ticker Detail

{ticker_body}

## Reading Rule

- If all EMA lengths from 180 to 210 produce similar metrics, the strategy is not sensitive
  to the exact parameter. The chosen filter is robust.
- If only EMA 195 works and neighbors collapse, the backtest is overfit and the result
  should not be used for live trading.
- A STABLE verdict does not guarantee future performance. It only shows the rule is not
  a lucky coincidence of one specific number.
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scoring_assets_from_mappings(
    mappings: tuple[ExecutionMapping, ...],
) -> dict[str, ExecutionAsset]:
    result: dict[str, ExecutionAsset] = {}
    for mapping in mappings:
        candidates = [
            a for a in mapping.execution_assets
            if a.mode == "observed_etf" and a.leverage == 1.0
        ]
        if candidates:
            result[mapping.signal_ticker] = candidates[0]
    return result


def _composite_score(metrics: dict[str, Any], score_weights: dict[str, float]) -> float:
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


def _pct(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return f"{float(value) * 100:.2f}%"


def _num(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return f"{float(value):.4f}"
