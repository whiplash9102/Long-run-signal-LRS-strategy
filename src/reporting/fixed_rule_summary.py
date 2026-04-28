"""Review tables and markdown summary for the fixed-rule backtest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STRATEGY = "strategy"
BUY_HOLD = "buy_hold"

METRIC_KEYS = [
    "signal_ticker",
    "filter_id",
    "execution_id",
]

RANKING_COLUMNS = [
    "rank",
    "signal_ticker",
    "filter_id",
    "execution_id",
    "execution_mode",
    "leverage",
    "profitable",
    "risk_bucket",
    "recovery_bucket",
    "CAGR",
    "max_drawdown",
    "calmar_ratio",
    "sharpe_ratio",
    "ending_equity",
    "max_recovery_days",
    "trades_per_year",
    "average_hold_days",
    "win_rate_by_trade",
    "profit_factor",
    "start_date",
    "end_date",
]

COMPARISON_COLUMNS = [
    "rank",
    "signal_ticker",
    "filter_id",
    "execution_id",
    "execution_mode",
    "leverage",
    "strategy_profitable",
    "buy_hold_profitable",
    "strategy_CAGR",
    "buy_hold_CAGR",
    "CAGR_gap",
    "strategy_max_drawdown",
    "buy_hold_max_drawdown",
    "drawdown_improvement",
    "strategy_calmar_ratio",
    "buy_hold_calmar_ratio",
    "calmar_gap",
    "strategy_ending_equity",
    "buy_hold_ending_equity",
    "strategy_max_recovery_days",
    "buy_hold_max_recovery_days",
    "start_date",
    "end_date",
]


@dataclass(frozen=True)
class FixedRuleSummaryOutputs:
    strategy_rankings: Path
    observed_leveraged_rankings: Path
    best_by_signal: Path
    strategy_vs_buy_hold: Path
    review_report: Path


def run_fixed_rule_summary(config: dict[str, Any]) -> FixedRuleSummaryOutputs:
    """Build review outputs from fixed-rule backtest metrics."""
    metrics_path = Path("reports/tables/fixed_rule_metrics.csv")
    if not metrics_path.exists():
        raise FileNotFoundError(f"Missing fixed-rule metrics file: {metrics_path}")

    initial_capital = float(config["execution"]["initial_capital"])
    metrics = pd.read_csv(metrics_path)
    enriched = enrich_metrics(metrics, initial_capital=initial_capital)

    strategy_rankings = rank_strategy_rows(enriched)
    observed_rankings = strategy_rankings[
        strategy_rankings["execution_mode"].eq("observed_leveraged_etf")
    ].reset_index(drop=True)
    observed_rankings["rank"] = range(1, len(observed_rankings) + 1)

    best_by_signal = select_best_by_signal(strategy_rankings)
    strategy_vs_buy_hold = build_strategy_vs_buy_hold(enriched)
    report = render_review_report(
        metrics=enriched,
        strategy_rankings=strategy_rankings,
        observed_rankings=observed_rankings,
        best_by_signal=best_by_signal,
        strategy_vs_buy_hold=strategy_vs_buy_hold,
        initial_capital=initial_capital,
    )

    outputs = FixedRuleSummaryOutputs(
        strategy_rankings=Path("reports/tables/fixed_rule_strategy_rankings.csv"),
        observed_leveraged_rankings=Path(
            "reports/tables/fixed_rule_observed_leveraged_rankings.csv"
        ),
        best_by_signal=Path("reports/tables/fixed_rule_best_by_signal.csv"),
        strategy_vs_buy_hold=Path("reports/tables/fixed_rule_strategy_vs_buy_hold.csv"),
        review_report=Path("reports/fixed_rule_review.md"),
    )
    outputs.strategy_rankings.parent.mkdir(parents=True, exist_ok=True)
    outputs.review_report.parent.mkdir(parents=True, exist_ok=True)

    strategy_rankings.to_csv(outputs.strategy_rankings, index=False)
    observed_rankings.to_csv(outputs.observed_leveraged_rankings, index=False)
    best_by_signal.to_csv(outputs.best_by_signal, index=False)
    strategy_vs_buy_hold.to_csv(outputs.strategy_vs_buy_hold, index=False)
    outputs.review_report.write_text(report, encoding="utf-8")
    return outputs


def enrich_metrics(metrics: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    """Add reader-friendly profitability and risk labels."""
    enriched = metrics.copy()
    enriched["profitable"] = (
        enriched["CAGR"].astype(float).gt(0)
        & enriched["ending_equity"].astype(float).gt(initial_capital)
    )
    enriched["risk_bucket"] = enriched["max_drawdown"].apply(classify_drawdown)
    enriched["recovery_bucket"] = enriched["max_recovery_days"].apply(classify_recovery)
    return enriched


def classify_drawdown(max_drawdown: float) -> str:
    """Bucket drawdown severity using negative drawdown values."""
    if pd.isna(max_drawdown):
        return "unknown"
    value = float(max_drawdown)
    if value <= -0.70:
        return "severe"
    if value <= -0.50:
        return "high"
    if value <= -0.30:
        return "moderate"
    return "lower"


def classify_recovery(max_recovery_days: float) -> str:
    """Bucket time-under-water severity."""
    if pd.isna(max_recovery_days):
        return "unknown"
    value = float(max_recovery_days)
    if value >= 1095:
        return "severe"
    if value >= 730:
        return "high"
    if value >= 365:
        return "moderate"
    return "lower"


def rank_strategy_rows(metrics: pd.DataFrame) -> pd.DataFrame:
    """Rank strategies by risk-adjusted return first, then growth."""
    strategies = metrics[metrics["result_type"].eq(STRATEGY)].copy()
    ranked = strategies.sort_values(
        ["calmar_ratio", "CAGR", "sharpe_ratio", "ending_equity"],
        ascending=[False, False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    ranked["rank"] = range(1, len(ranked) + 1)
    return ranked[RANKING_COLUMNS]


def select_best_by_signal(strategy_rankings: pd.DataFrame) -> pd.DataFrame:
    """Select the top ranked strategy for each signal ETF."""
    best = (
        strategy_rankings.sort_values("rank")
        .groupby("signal_ticker", as_index=False, sort=True)
        .head(1)
        .sort_values("signal_ticker")
        .reset_index(drop=True)
    )
    return best[RANKING_COLUMNS]


def build_strategy_vs_buy_hold(metrics: pd.DataFrame) -> pd.DataFrame:
    """Compare each timed strategy with buy-and-hold for the same execution asset."""
    strategies = metrics[metrics["result_type"].eq(STRATEGY)].copy()
    buy_hold = metrics[metrics["result_type"].eq(BUY_HOLD)].copy()

    merged = strategies.merge(
        buy_hold,
        on=METRIC_KEYS,
        suffixes=("_strategy", "_buy_hold"),
        how="inner",
    )
    comparison = pd.DataFrame(
        {
            "signal_ticker": merged["signal_ticker"],
            "filter_id": merged["filter_id"],
            "execution_id": merged["execution_id"],
            "execution_mode": merged["execution_mode_strategy"],
            "leverage": merged["leverage_strategy"],
            "strategy_profitable": merged["profitable_strategy"],
            "buy_hold_profitable": merged["profitable_buy_hold"],
            "strategy_CAGR": merged["CAGR_strategy"],
            "buy_hold_CAGR": merged["CAGR_buy_hold"],
            "CAGR_gap": merged["CAGR_strategy"] - merged["CAGR_buy_hold"],
            "strategy_max_drawdown": merged["max_drawdown_strategy"],
            "buy_hold_max_drawdown": merged["max_drawdown_buy_hold"],
            "drawdown_improvement": (
                merged["max_drawdown_strategy"] - merged["max_drawdown_buy_hold"]
            ),
            "strategy_calmar_ratio": merged["calmar_ratio_strategy"],
            "buy_hold_calmar_ratio": merged["calmar_ratio_buy_hold"],
            "calmar_gap": merged["calmar_ratio_strategy"] - merged["calmar_ratio_buy_hold"],
            "strategy_ending_equity": merged["ending_equity_strategy"],
            "buy_hold_ending_equity": merged["ending_equity_buy_hold"],
            "strategy_max_recovery_days": merged["max_recovery_days_strategy"],
            "buy_hold_max_recovery_days": merged["max_recovery_days_buy_hold"],
            "start_date": merged["start_date_strategy"],
            "end_date": merged["end_date_strategy"],
        }
    )
    comparison = comparison.sort_values(
        ["strategy_calmar_ratio", "strategy_CAGR", "calmar_gap"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    comparison["rank"] = range(1, len(comparison) + 1)
    return comparison[COMPARISON_COLUMNS]


def render_review_report(
    metrics: pd.DataFrame,
    strategy_rankings: pd.DataFrame,
    observed_rankings: pd.DataFrame,
    best_by_signal: pd.DataFrame,
    strategy_vs_buy_hold: pd.DataFrame,
    initial_capital: float,
) -> str:
    """Render a concise markdown review for the fixed-rule test."""
    strategies = metrics[metrics["result_type"].eq(STRATEGY)]
    profitable_count = int(strategies["profitable"].sum())
    total_count = len(strategies)
    observed_profitable = int(observed_rankings["profitable"].sum())
    severe_or_high = int(strategy_rankings["risk_bucket"].isin(["severe", "high"]).sum())

    top = strategy_rankings.iloc[0]
    top_comparison = strategy_vs_buy_hold[
        (strategy_vs_buy_hold["signal_ticker"] == top["signal_ticker"])
        & (strategy_vs_buy_hold["filter_id"] == top["filter_id"])
        & (strategy_vs_buy_hold["execution_id"] == top["execution_id"])
    ].iloc[0]

    best_display = best_by_signal[
        [
            "signal_ticker",
            "filter_id",
            "execution_id",
            "profitable",
            "CAGR",
            "max_drawdown",
            "calmar_ratio",
            "max_recovery_days",
        ]
    ].rename(
        columns={
            "signal_ticker": "Signal",
            "filter_id": "Filter",
            "execution_id": "Execution",
            "profitable": "Profitable",
            "CAGR": "CAGR",
            "max_drawdown": "Max DD",
            "calmar_ratio": "Calmar",
            "max_recovery_days": "Recovery Days",
        }
    )

    observed_display = observed_rankings.head(10)[
        [
            "rank",
            "signal_ticker",
            "filter_id",
            "execution_id",
            "profitable",
            "CAGR",
            "max_drawdown",
            "calmar_ratio",
        ]
    ].rename(
        columns={
            "rank": "Rank",
            "signal_ticker": "Signal",
            "filter_id": "Filter",
            "execution_id": "Execution",
            "profitable": "Profitable",
            "CAGR": "CAGR",
            "max_drawdown": "Max DD",
            "calmar_ratio": "Calmar",
        }
    )

    comparison_display = strategy_vs_buy_hold.head(10)[
        [
            "rank",
            "signal_ticker",
            "filter_id",
            "execution_id",
            "strategy_CAGR",
            "buy_hold_CAGR",
            "CAGR_gap",
            "strategy_max_drawdown",
            "buy_hold_max_drawdown",
            "drawdown_improvement",
            "calmar_gap",
        ]
    ].rename(
        columns={
            "rank": "Rank",
            "signal_ticker": "Signal",
            "filter_id": "Filter",
            "execution_id": "Execution",
            "strategy_CAGR": "Strategy CAGR",
            "buy_hold_CAGR": "Buy Hold CAGR",
            "CAGR_gap": "CAGR Gap",
            "strategy_max_drawdown": "Strategy DD",
            "buy_hold_max_drawdown": "Buy Hold DD",
            "drawdown_improvement": "DD Improvement",
            "calmar_gap": "Calmar Gap",
        }
    )

    return f"""# Fixed-Rule Backtest Review

## Scope

- Purpose: test whether the configured long leveraged ETF rules are profitable.
- Signal assets: normal ETFs only.
- Execution assets: configured 1x, 2x, and 3x assets.
- Risk-off asset: CASH.
- Initial capital: {_format_money(initial_capital)}.
- Validation status: fixed-rule research only; walk-forward validation is not done yet.

## Profitability Snapshot

- Profitable strategy rows: {profitable_count} of {total_count}.
- Profitable observed leveraged ETF rows: {observed_profitable} of {len(observed_rankings)}.
- Strategy rows with high or severe drawdown: {severe_or_high} of {total_count}.
- Profitability definition: CAGR above 0 and ending equity above initial capital.

## Headline Result

- Best risk-adjusted fixed-rule row: `{top["signal_ticker"]}` + `{top["filter_id"]}` + `{top["execution_id"]}`.
- CAGR: {_format_percent(top["CAGR"])}.
- Max drawdown: {_format_percent(top["max_drawdown"])}.
- Calmar ratio: {_format_number(top["calmar_ratio"])}.
- Ending equity: {_format_money(top["ending_equity"])}.
- Compared with buy-and-hold on the same execution asset, CAGR gap is {_format_percent(top_comparison["CAGR_gap"])} and drawdown improvement is {_format_percent(top_comparison["drawdown_improvement"])}.

## Best By Signal ETF

{_markdown_table(best_display)}

## Observed Leveraged ETF Ranking

{_markdown_table(observed_display)}

## Strategy Versus Buy-And-Hold

{_markdown_table(comparison_display)}

## Reading Rule

- `CAGR` answers whether the rule made money over the tested period.
- `Max DD` shows the largest peak-to-trough pain.
- `Recovery Days` shows how long capital stayed below a prior equity peak.
- `Calmar` is the main ranking metric here because it compares return to drawdown.
- A profitable leveraged ETF row is not automatically acceptable if the drawdown or recovery time is too large.

## Next Decision

- Use this report to select candidates for walk-forward testing.
- Do not treat the fixed-rule winner as final until it survives out-of-sample validation.
"""


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in frame.iterrows():
        values = [_format_cell(column, row[column]) for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _format_cell(column: str, value: Any) -> str:
    if isinstance(value, (bool, np.bool_)):
        return "yes" if bool(value) else "no"
    if pd.isna(value):
        return ""
    if _is_percent_column(column):
        return _format_percent(value)
    if column in {"Calmar", "Calmar Gap"}:
        return _format_number(value)
    if column in {"Rank", "Recovery Days"}:
        return str(int(value))
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return _format_number(value)
    return str(value)


def _is_percent_column(column: str) -> bool:
    return column in {
        "CAGR",
        "Max DD",
        "Strategy CAGR",
        "Buy Hold CAGR",
        "CAGR Gap",
        "Strategy DD",
        "Buy Hold DD",
        "DD Improvement",
    }


def _format_percent(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.2f}%"


def _format_money(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"${float(value):,.0f}"


def _format_number(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.4f}"
