"""False-breakout diagnostics for the fixed-rule signal layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BUY_ALERT = "BUY_ALERT"
EXIT_ALERT = "EXIT_ALERT"

DEFAULT_ENTRY_VOL_LOOKBACK = 20
DEFAULT_ENTRY_SLOPE_LOOKBACK = 5


@dataclass(frozen=True)
class FalseBreakoutAuditOutputs:
    entries: Path
    summary: Path
    report: Path


def run_false_breakout_audit(config: dict[str, Any]) -> FalseBreakoutAuditOutputs:
    prices_path = Path("data/processed/prices_adjusted.csv")
    signals_path = Path("data/processed/signals.csv")
    indicators_path = Path("data/processed/indicators.csv")
    if not prices_path.exists():
        raise FileNotFoundError(f"Missing adjusted prices file: {prices_path}")
    if not signals_path.exists():
        raise FileNotFoundError(f"Missing signals file: {signals_path}")
    if not indicators_path.exists():
        raise FileNotFoundError(f"Missing indicators file: {indicators_path}")

    prices = pd.read_csv(prices_path)
    signals = pd.read_csv(signals_path)
    indicators = pd.read_csv(indicators_path)
    whipsaw_window_sessions = int(config["strategy"]["false_breakout"]["whipsaw_window_sessions"])

    audit = build_false_breakout_audit(
        prices=prices,
        signals=signals,
        indicators=indicators,
        whipsaw_window_sessions=whipsaw_window_sessions,
        entry_vol_lookback=DEFAULT_ENTRY_VOL_LOOKBACK,
        entry_slope_lookback=DEFAULT_ENTRY_SLOPE_LOOKBACK,
    )

    outputs = FalseBreakoutAuditOutputs(
        entries=Path("reports/tables/false_breakout_audit_entries.csv"),
        summary=Path("reports/tables/false_breakout_audit_summary.csv"),
        report=Path("reports/false_breakout_review.md"),
    )
    outputs.entries.parent.mkdir(parents=True, exist_ok=True)
    outputs.report.parent.mkdir(parents=True, exist_ok=True)

    audit["entries"].to_csv(outputs.entries, index=False)
    audit["summary"].to_csv(outputs.summary, index=False)
    outputs.report.write_text(
        render_false_breakout_report(
            entries=audit["entries"],
            summary=audit["summary"],
            whipsaw_window_sessions=whipsaw_window_sessions,
        ),
        encoding="utf-8",
    )
    return outputs


def build_false_breakout_audit(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    indicators: pd.DataFrame,
    whipsaw_window_sessions: int,
    entry_vol_lookback: int = DEFAULT_ENTRY_VOL_LOOKBACK,
    entry_slope_lookback: int = DEFAULT_ENTRY_SLOPE_LOOKBACK,
) -> dict[str, pd.DataFrame]:
    """Create one audit row per buy alert and a grouped summary."""
    signal_rows = _prepare_signal_rows(signals)
    if signal_rows.empty:
        return {"entries": _empty_entries(), "summary": _empty_summary()}

    feature_frame = _build_feature_frame(
        prices=prices,
        indicators=indicators,
        tickers=signal_rows["ticker"].unique().tolist(),
        filter_ids=signal_rows["filter_id"].unique().tolist(),
        entry_vol_lookback=entry_vol_lookback,
        entry_slope_lookback=entry_slope_lookback,
    )

    entries = _pair_entries_and_exits(
        signal_rows=signal_rows,
        feature_frame=feature_frame,
        whipsaw_window_sessions=whipsaw_window_sessions,
    )
    summary = _build_summary(entries)
    return {"entries": entries, "summary": summary}


def render_false_breakout_report(
    entries: pd.DataFrame,
    summary: pd.DataFrame,
    whipsaw_window_sessions: int,
) -> str:
    overall = summary.iloc[0] if not summary.empty else None
    top = (
        summary.sort_values(["whipsaw_rate", "whipsaws"], ascending=[False, False]).head(10)
        if not summary.empty
        else summary
    )
    detail = entries[
        [
            "ticker",
            "filter_id",
            "entry_date",
            "exit_date",
            "sessions_held",
            "whipsaw",
            "entry_distance_pct",
            "filter_slope_pct",
            "recent_return_pct",
            "recent_volatility_ann_pct",
            "trade_return_pct",
        ]
    ].head(15)

    return f"""# False-Breakout Audit

## Scope

- Purpose: measure whether buy alerts tend to fail quickly.
- Whipsaw window: {whipsaw_window_sessions} sessions.
- Trading status: diagnostics only, not a trading filter.
- Measurement level: signal ETF only, not leveraged execution.

## Overall Snapshot

- Buy alerts analyzed: {int(overall["buy_alerts"]) if overall is not None else 0}.
- Completed round trips: {int(overall["completed_round_trips"]) if overall is not None else 0}.
- Whipsaws inside the window: {int(overall["whipsaws"]) if overall is not None else 0}.
- Whipsaw rate: {_format_percent(overall["whipsaw_rate"]) if overall is not None else ""}.
- Average entry distance from filter: {_format_percent(overall["avg_entry_distance_pct"]) if overall is not None else ""}.
- Average recent volatility at entry: {_format_percent(overall["avg_recent_volatility_ann_pct"]) if overall is not None else ""}.
- Average recent return at entry: {_format_percent(overall["avg_recent_return_pct"]) if overall is not None else ""}.

## Highest Whipsaw Rates

{_markdown_table(top)}

## Sample Entry Audit Rows

{_markdown_table(detail)}

## Reading Rule

- Small entry distance with weak recent strength is the first place to look for a false breakout filter.
- If whipsaws cluster when slope is flat or negative, a slope gate may help.
- If whipsaws cluster when entry volatility is high, a volatility gate may help.
- This report does not change the strategy yet.
"""


def _prepare_signal_rows(signals: pd.DataFrame) -> pd.DataFrame:
    required = {
        "date",
        "ticker",
        "filter_id",
        "signal_event",
        "signal_price",
        "filter_value",
        "signal_is_tradable",
        "current_state",
        "next_execution_date",
    }
    missing = sorted(required.difference(signals.columns))
    if missing:
        raise ValueError(f"signals missing columns: {missing}")

    rows = signals[signals["signal_is_tradable"].astype(bool)].copy()
    rows = rows.sort_values(["ticker", "filter_id", "date"]).reset_index(drop=True)
    return rows


def _build_feature_frame(
    prices: pd.DataFrame,
    indicators: pd.DataFrame,
    tickers: list[str],
    filter_ids: list[str],
    entry_vol_lookback: int,
    entry_slope_lookback: int,
) -> pd.DataFrame:
    price_frame = prices.loc[
        prices["ticker"].isin(tickers),
        ["date", "ticker", "adjusted_close"],
    ].copy()
    price_frame = price_frame.sort_values(["ticker", "date"]).reset_index(drop=True)
    price_frame["close_return"] = price_frame.groupby("ticker")["adjusted_close"].pct_change()
    price_frame["recent_return_pct"] = price_frame.groupby("ticker")["adjusted_close"].transform(
        lambda series: series / series.shift(entry_vol_lookback) - 1.0
    )
    price_frame["recent_volatility_ann_pct"] = price_frame.groupby("ticker")["close_return"].transform(
        lambda series: series.rolling(entry_vol_lookback, min_periods=entry_vol_lookback).std(ddof=0)
        * np.sqrt(252)
    )

    indicator_frame = indicators.loc[
        indicators["ticker"].isin(tickers) & indicators["filter_id"].isin(filter_ids),
        ["date", "ticker", "filter_id", "filter_value"],
    ].copy()
    indicator_frame = indicator_frame.sort_values(["ticker", "filter_id", "date"]).reset_index(drop=True)
    indicator_frame["filter_slope_pct"] = indicator_frame.groupby(["ticker", "filter_id"])[
        "filter_value"
    ].transform(lambda series: series / series.shift(entry_slope_lookback) - 1.0)

    feature_frame = indicator_frame.merge(price_frame, on=["date", "ticker"], how="left")
    return feature_frame


def _pair_entries_and_exits(
    signal_rows: pd.DataFrame,
    feature_frame: pd.DataFrame,
    whipsaw_window_sessions: int,
) -> pd.DataFrame:
    feature_index = feature_frame.set_index(["date", "ticker", "filter_id"])
    rows: list[dict[str, Any]] = []

    for (ticker, filter_id), group in signal_rows.groupby(["ticker", "filter_id"], sort=True):
        ordered = group.sort_values("date").reset_index(drop=True)
        trade_sequence = ordered[ordered["signal_event"].isin([BUY_ALERT, EXIT_ALERT])].reset_index(
            drop=False
        )
        buy_positions = trade_sequence[trade_sequence["signal_event"] == BUY_ALERT].index.tolist()
        for buy_pos in buy_positions:
            buy_row = trade_sequence.loc[buy_pos]
            next_exit = trade_sequence.loc[buy_pos + 1 :] if buy_pos + 1 < len(trade_sequence) else trade_sequence.iloc[0:0]
            next_exit = next_exit[next_exit["signal_event"] == EXIT_ALERT]
            exit_row = next_exit.iloc[0] if not next_exit.empty else None

            entry_date = buy_row["date"]
            feature_key = (entry_date, ticker, filter_id)
            feature = feature_index.loc[feature_key] if feature_key in feature_index.index else None
            if feature is None or isinstance(feature, pd.DataFrame):
                continue

            sessions_held = (
                int(exit_row["index"] - buy_row["index"]) if exit_row is not None else np.nan
            )
            trade_return_pct = np.nan
            exit_date = None
            if exit_row is not None:
                exit_date = exit_row["date"]
                exit_feature_key = (exit_date, ticker, filter_id)
                if exit_feature_key in feature_index.index:
                    exit_feature = feature_index.loc[exit_feature_key]
                    if not isinstance(exit_feature, pd.DataFrame):
                        trade_return_pct = float(
                            exit_row["signal_price"] / buy_row["signal_price"] - 1.0
                        )

            whipsaw = bool(
                exit_row is not None and sessions_held <= whipsaw_window_sessions
            )
            rows.append(
                {
                    "ticker": ticker,
                    "filter_id": filter_id,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "sessions_held": sessions_held,
                    "whipsaw": whipsaw,
                    "signal_price": float(buy_row["signal_price"]),
                    "filter_value": float(feature["filter_value"]),
                    "entry_distance_pct": float(
                        buy_row["signal_price"] / feature["filter_value"] - 1.0
                    ),
                    "filter_slope_pct": float(feature["filter_slope_pct"]),
                    "recent_return_pct": float(feature["recent_return_pct"]),
                    "recent_volatility_ann_pct": float(feature["recent_volatility_ann_pct"]),
                    "trade_return_pct": trade_return_pct,
                }
            )

    if not rows:
        return _empty_entries()

    entries = pd.DataFrame(rows)
    entries = entries.sort_values(["ticker", "filter_id", "entry_date"]).reset_index(drop=True)
    return entries


def _build_summary(entries: pd.DataFrame) -> pd.DataFrame:
    if entries.empty:
        return _empty_summary()

    rows: list[dict[str, Any]] = []
    overall = _summary_row(entries, ticker="ALL", filter_id="ALL")
    rows.append(overall)
    for (ticker, filter_id), group in entries.groupby(["ticker", "filter_id"], sort=True):
        rows.append(_summary_row(group, ticker=ticker, filter_id=filter_id))
    return pd.DataFrame(rows)


def _summary_row(group: pd.DataFrame, ticker: str, filter_id: str) -> dict[str, Any]:
    completed = group[group["exit_date"].notna()]
    whipsaws = completed[completed["whipsaw"].astype(bool)]
    return {
        "ticker": ticker,
        "filter_id": filter_id,
        "buy_alerts": int(len(group)),
        "completed_round_trips": int(len(completed)),
        "whipsaws": int(len(whipsaws)),
        "whipsaw_rate": float(len(whipsaws) / len(completed)) if len(completed) else np.nan,
        "avg_entry_distance_pct": float(group["entry_distance_pct"].mean()),
        "avg_filter_slope_pct": float(group["filter_slope_pct"].mean()),
        "avg_recent_volatility_ann_pct": float(group["recent_volatility_ann_pct"].mean()),
        "avg_recent_return_pct": float(group["recent_return_pct"].mean()),
        "avg_trade_return_pct": float(group["trade_return_pct"].mean()),
        "avg_whipsaw_trade_return_pct": float(whipsaws["trade_return_pct"].mean())
        if not whipsaws.empty
        else np.nan,
        "avg_non_whipsaw_trade_return_pct": float(
            completed.loc[~completed["whipsaw"].astype(bool), "trade_return_pct"].mean()
        )
        if not completed.empty
        else np.nan,
    }


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
    if column in {"whipsaw_rate", "avg_entry_distance_pct", "avg_recent_volatility_ann_pct", "avg_recent_return_pct", "avg_trade_return_pct", "avg_whipsaw_trade_return_pct", "avg_non_whipsaw_trade_return_pct", "entry_distance_pct", "filter_slope_pct", "recent_return_pct", "recent_volatility_ann_pct", "trade_return_pct"}:
        return _format_percent(value)
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return _format_number(float(value))
    return str(value)


def _format_percent(value: Any) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value) * 100:.2f}%"


def _format_number(value: float) -> str:
    return f"{value:.4f}"


def _empty_entries() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ticker",
            "filter_id",
            "entry_date",
            "exit_date",
            "sessions_held",
            "whipsaw",
            "signal_price",
            "filter_value",
            "entry_distance_pct",
            "filter_slope_pct",
            "recent_return_pct",
            "recent_volatility_ann_pct",
            "trade_return_pct",
        ]
    )


def _empty_summary() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ticker",
            "filter_id",
            "buy_alerts",
            "completed_round_trips",
            "whipsaws",
            "whipsaw_rate",
            "avg_entry_distance_pct",
            "avg_filter_slope_pct",
            "avg_recent_volatility_ann_pct",
            "avg_recent_return_pct",
            "avg_trade_return_pct",
            "avg_whipsaw_trade_return_pct",
            "avg_non_whipsaw_trade_return_pct",
        ]
    )
