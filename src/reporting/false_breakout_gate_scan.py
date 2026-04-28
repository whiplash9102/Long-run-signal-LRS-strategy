"""Simple false-breakout gate scan built on top of the audit rows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FalseBreakoutGateScanOutputs:
    candidates: Path
    report: Path


def run_false_breakout_gate_scan(config: dict[str, Any]) -> FalseBreakoutGateScanOutputs:
    entries_path = Path("reports/tables/false_breakout_audit_entries.csv")
    summary_path = Path("reports/tables/false_breakout_audit_summary.csv")
    if not entries_path.exists():
        raise FileNotFoundError(f"Missing false-breakout audit entries file: {entries_path}")
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing false-breakout audit summary file: {summary_path}")

    entries = pd.read_csv(entries_path)
    summary = pd.read_csv(summary_path)
    if entries.empty:
        candidates = _empty_candidates()
        report = _render_gate_report(entries, summary, candidates)
    else:
        candidates = scan_false_breakout_gates(entries)
        report = _render_gate_report(entries, summary, candidates)

    outputs = FalseBreakoutGateScanOutputs(
        candidates=Path("reports/tables/false_breakout_gate_candidates.csv"),
        report=Path("reports/false_breakout_gate_review.md"),
    )
    outputs.candidates.parent.mkdir(parents=True, exist_ok=True)
    outputs.report.parent.mkdir(parents=True, exist_ok=True)

    candidates.to_csv(outputs.candidates, index=False)
    outputs.report.write_text(report, encoding="utf-8")
    return outputs


def scan_false_breakout_gates(
    entries: pd.DataFrame,
    min_acceptance_rate: float = 0.75,
) -> pd.DataFrame:
    """Evaluate a compact grid of slope and entry-distance gates."""
    required = {
        "whipsaw",
        "exit_date",
        "entry_distance_pct",
        "filter_slope_pct",
        "trade_return_pct",
    }
    missing = sorted(required.difference(entries.columns))
    if missing:
        raise ValueError(f"entries missing columns: {missing}")

    baseline_completed = entries[entries["exit_date"].notna()]
    baseline_whipsaw_rate = _safe_rate(
        baseline_completed["whipsaw"].sum(), len(baseline_completed)
    )

    entry_distance_thresholds = [0.0, 0.0025, 0.0050, 0.0075, 0.0100, 0.0125, 0.0150]
    slope_thresholds = [-0.0010, -0.0005, 0.0, 0.0005, 0.0010]

    rows: list[dict[str, Any]] = []
    for min_entry_distance_pct in entry_distance_thresholds:
        for min_filter_slope_pct in slope_thresholds:
            accepted = entries[
                (entries["entry_distance_pct"] >= min_entry_distance_pct)
                & (entries["filter_slope_pct"] >= min_filter_slope_pct)
            ].copy()
            accepted_completed = accepted[accepted["exit_date"].notna()]
            whipsaws = int(accepted_completed["whipsaw"].sum())
            whipsaw_rate = _safe_rate(whipsaws, len(accepted_completed))
            acceptance_rate = _safe_rate(len(accepted), len(entries))
            whipsaw_reduction = (
                baseline_whipsaw_rate - whipsaw_rate
                if not pd.isna(whipsaw_rate)
                else np.nan
            )
            rows.append(
                {
                    "min_entry_distance_pct": min_entry_distance_pct,
                    "min_filter_slope_pct": min_filter_slope_pct,
                    "accepted_alerts": int(len(accepted)),
                    "accepted_completed_round_trips": int(len(accepted_completed)),
                    "accepted_whipsaws": whipsaws,
                    "acceptance_rate": acceptance_rate,
                    "whipsaw_rate": whipsaw_rate,
                    "whipsaw_reduction": whipsaw_reduction,
                    "avg_trade_return_pct": float(accepted_completed["trade_return_pct"].mean())
                    if not accepted_completed.empty
                    else np.nan,
                    "avg_entry_distance_pct": float(accepted["entry_distance_pct"].mean())
                    if not accepted.empty
                    else np.nan,
                    "avg_filter_slope_pct": float(accepted["filter_slope_pct"].mean())
                    if not accepted.empty
                    else np.nan,
                    "recommended": bool(
                        acceptance_rate >= min_acceptance_rate and whipsaw_reduction > 0
                    )
                    if not pd.isna(acceptance_rate) and not pd.isna(whipsaw_rate)
                    else False,
                }
            )

    candidates = pd.DataFrame(rows)
    candidates = candidates.sort_values(
        [
            "recommended",
            "whipsaw_reduction",
            "acceptance_rate",
            "whipsaw_rate",
            "avg_trade_return_pct",
        ],
        ascending=[False, False, False, True, False],
        na_position="last",
    ).reset_index(drop=True)
    candidates["rank"] = range(1, len(candidates) + 1)
    return candidates[
        [
            "rank",
            "min_entry_distance_pct",
            "min_filter_slope_pct",
            "accepted_alerts",
            "accepted_completed_round_trips",
            "accepted_whipsaws",
            "acceptance_rate",
            "whipsaw_rate",
            "whipsaw_reduction",
            "avg_trade_return_pct",
            "avg_entry_distance_pct",
            "avg_filter_slope_pct",
            "recommended",
        ]
    ]


def _render_gate_report(
    entries: pd.DataFrame,
    summary: pd.DataFrame,
    candidates: pd.DataFrame,
) -> str:
    baseline = summary.iloc[0] if not summary.empty else None
    baseline_avg_filter_slope_pct = (
        baseline["avg_filter_slope_pct"]
        if baseline is not None and "avg_filter_slope_pct" in baseline.index
        else float(entries["filter_slope_pct"].mean()) if not entries.empty else np.nan
    )
    baseline_avg_entry_distance_pct = (
        baseline["avg_entry_distance_pct"]
        if baseline is not None and "avg_entry_distance_pct" in baseline.index
        else float(entries["entry_distance_pct"].mean()) if not entries.empty else np.nan
    )
    top = candidates.head(10)
    best_recommended = candidates[candidates["recommended"].astype(bool)].head(1)
    recommended_note = (
        _format_gate(best_recommended.iloc[0])
        if not best_recommended.empty
        else "No gate met the retention threshold."
    )

    return f"""# False-Breakout Gate Scan

## Scope

- Purpose: test a small, simple gate on top of the audit.
- Inputs: false-breakout audit entries, not raw price history.
- Status: diagnostics only.

## Baseline

- Buy alerts: {int(baseline["buy_alerts"]) if baseline is not None else 0}.
- Completed round trips: {int(baseline["completed_round_trips"]) if baseline is not None else 0}.
- Whipsaw rate: {_format_percent(baseline["whipsaw_rate"]) if baseline is not None else ""}.
- Average entry distance: {_format_percent(baseline["avg_entry_distance_pct"]) if baseline is not None and "avg_entry_distance_pct" in baseline.index else _format_percent(baseline_avg_entry_distance_pct)}.
- Average filter slope: {_format_percent(baseline["avg_filter_slope_pct"]) if baseline is not None and "avg_filter_slope_pct" in baseline.index else _format_percent(baseline_avg_filter_slope_pct)}.

## Recommended Gate

- {recommended_note}

## Top Candidates

{_markdown_table(top)}

## Reading Rule

- A useful gate must lower whipsaw rate without cutting too much of the trade sample.
- Entry distance is a proxy for how far price has moved above the filter.
- Filter slope is a proxy for whether the moving average is flattening or rising.
- This scan is still not a trading rule. It only tells us which gate is worth testing next.
"""


def _format_gate(row: pd.Series) -> str:
    return (
        f"entry distance >= {_format_percent(row['min_entry_distance_pct'])} and "
        f"filter slope >= {_format_percent(row['min_filter_slope_pct'])}"
        f" with acceptance rate {_format_percent(row['acceptance_rate'])}"
        f" and whipsaw rate {_format_percent(row['whipsaw_rate'])}"
    )


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
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
    if column in {
        "min_entry_distance_pct",
        "min_filter_slope_pct",
        "acceptance_rate",
        "whipsaw_rate",
        "whipsaw_reduction",
        "avg_trade_return_pct",
        "avg_entry_distance_pct",
        "avg_filter_slope_pct",
    }:
        return _format_percent(value)
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.4f}"
    return str(value)


def _format_percent(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.2f}%"


def _safe_rate(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else np.nan


def _empty_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "rank",
            "min_entry_distance_pct",
            "min_filter_slope_pct",
            "accepted_alerts",
            "accepted_completed_round_trips",
            "accepted_whipsaws",
            "acceptance_rate",
            "whipsaw_rate",
            "whipsaw_reduction",
            "avg_trade_return_pct",
            "avg_entry_distance_pct",
            "avg_filter_slope_pct",
            "recommended",
        ]
    )
