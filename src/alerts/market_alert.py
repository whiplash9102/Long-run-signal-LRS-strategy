"""Morning email alerts for the Gayed LRS strategy.

The alert uses the last confirmed close before the current US market date.
It does not use same-day partial daily bars.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import ssl
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.reporting.false_breakout_audit import (
    DEFAULT_ENTRY_SLOPE_LOOKBACK,
    DEFAULT_ENTRY_VOL_LOOKBACK,
    build_false_breakout_audit,
)
from src.strategy.signals import BUY_ALERT, EXIT_ALERT, LONG, RISK_OFF, WARMUP


EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


@dataclass(frozen=True)
class AlertRow:
    ticker: str
    filter_id: str
    action: str
    position_state: str
    signal_event: str
    signal_date: str
    signal_price: float | None
    filter_value: float | None
    execution_assets: str
    false_breakout_warning: str
    false_breakout_note: str
    entry_distance_pct: float | None = None
    filter_slope_pct: float | None = None
    recent_return_pct: float | None = None
    recent_volatility_ann_pct: float | None = None
    historical_whipsaw_rate: float | None = None
    similar_whipsaw_rate: float | None = None
    similar_sample_size: int = 0
    new_entrant_tier: str = "N/A"
    new_entrant_note: str = ""


@dataclass(frozen=True)
class MarketAlert:
    market_date: str
    generated_at_et: str
    rows: tuple[AlertRow, ...]
    subject: str
    text_body: str
    html_body: str


@dataclass(frozen=True)
class EmailSettings:
    smtp_host: str
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    sender: str
    recipient: str
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> "EmailSettings":
        host = _required_env("SMTP_HOST")
        recipient = _required_env("ALERT_EMAIL_TO")
        sender = os.getenv("ALERT_EMAIL_FROM") or os.getenv("SMTP_USERNAME")
        if not sender:
            raise ValueError("Set ALERT_EMAIL_FROM or SMTP_USERNAME.")

        return cls(
            smtp_host=host,
            smtp_port=int(os.getenv("SMTP_PORT") or "587"),
            smtp_username=os.getenv("SMTP_USERNAME"),
            smtp_password=os.getenv("SMTP_PASSWORD"),
            sender=sender,
            recipient=recipient,
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() not in {"0", "false", "no"},
        )


def build_market_alert(
    config: dict[str, Any],
    prices: pd.DataFrame,
    indicators: pd.DataFrame,
    signals: pd.DataFrame,
    generated_at: datetime | None = None,
    market_date: date | None = None,
    tickers: list[str] | None = None,
    filter_ids: list[str] | None = None,
) -> MarketAlert:
    """Build the alert payload from already generated prices, indicators, and signals."""
    generated_at_et = _to_eastern(generated_at or datetime.now(timezone.utc))
    active_market_date = market_date or generated_at_et.date()
    tickers = tickers or [item["ticker"] for item in config["data"]["test_universe"]]
    filter_ids = filter_ids or [item["id"] for item in config["strategy"]["candidate_filters"]]
    execution_map = _execution_assets_by_signal_ticker(config)
    audit_entries = _build_audit_entries(config, prices, indicators, signals)

    rows: list[AlertRow] = []
    for ticker in tickers:
        for filter_id in filter_ids:
            signal_row = _latest_confirmed_signal(signals, ticker, filter_id, active_market_date)
            if signal_row is None:
                rows.append(
                    AlertRow(
                        ticker=ticker,
                        filter_id=filter_id,
                        action="NO_DATA",
                        position_state="UNKNOWN",
                        signal_event="NO_VALID_SIGNAL",
                        signal_date="",
                        signal_price=None,
                        filter_value=None,
                        execution_assets=execution_map.get(ticker, ""),
                        false_breakout_warning="UNKNOWN",
                        false_breakout_note="No confirmed signal row was available before the market date.",
                    )
                )
                continue

            action = _action_from_signal(signal_row)
            features = _entry_features(
                prices=prices,
                indicators=indicators,
                signal_row=signal_row,
                active_market_date=active_market_date,
            )
            warning = _false_breakout_warning(
                audit_entries=audit_entries,
                ticker=ticker,
                filter_id=filter_id,
                signal_date=str(signal_row["date"]),
                action=action,
                entry_distance_pct=features.get("entry_distance_pct"),
                filter_slope_pct=features.get("filter_slope_pct"),
            )
            entrant = _new_entrant_guidance(
                action=action,
                entry_distance_pct=features.get("entry_distance_pct"),
                filter_slope_pct=features.get("filter_slope_pct"),
                audit_entries=audit_entries,
                ticker=ticker,
                filter_id=filter_id,
            )
            rows.append(
                AlertRow(
                    ticker=ticker,
                    filter_id=filter_id,
                    action=action,
                    position_state=str(signal_row["current_state"]),
                    signal_event=str(signal_row["signal_event"]),
                    signal_date=str(signal_row["date"]),
                    signal_price=_safe_float(signal_row.get("signal_price")),
                    filter_value=_safe_float(signal_row.get("filter_value")),
                    execution_assets=execution_map.get(ticker, ""),
                    false_breakout_warning=warning["level"],
                    false_breakout_note=warning["note"],
                    entry_distance_pct=features.get("entry_distance_pct"),
                    filter_slope_pct=features.get("filter_slope_pct"),
                    recent_return_pct=features.get("recent_return_pct"),
                    recent_volatility_ann_pct=features.get("recent_volatility_ann_pct"),
                    historical_whipsaw_rate=warning["historical_whipsaw_rate"],
                    similar_whipsaw_rate=warning["similar_whipsaw_rate"],
                    similar_sample_size=int(warning["similar_sample_size"]),
                    new_entrant_tier=entrant["tier"],
                    new_entrant_note=entrant["note"],
                )
            )

    alert_rows = tuple(rows)
    subject = _build_subject(active_market_date, alert_rows)
    text_body = _build_text_body(active_market_date, generated_at_et, alert_rows)
    html_body = _build_html_body(active_market_date, generated_at_et, alert_rows)
    return MarketAlert(
        market_date=active_market_date.isoformat(),
        generated_at_et=generated_at_et.isoformat(timespec="seconds"),
        rows=alert_rows,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def write_alert_outputs(alert: MarketAlert, output_dir: str | Path) -> tuple[Path, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "latest_market_alert.json"
    text_path = output_path / "latest_market_alert.txt"
    payload = {
        "market_date": alert.market_date,
        "generated_at_et": alert.generated_at_et,
        "subject": alert.subject,
        "rows": [asdict(row) for row in alert.rows],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    text_path.write_text(alert.text_body, encoding="utf-8")
    return json_path, text_path


def send_email(alert: MarketAlert, settings: EmailSettings) -> None:
    message = EmailMessage()
    message["Subject"] = alert.subject
    message["From"] = settings.sender
    message["To"] = settings.recipient
    message.set_content(alert.text_body)
    message.add_alternative(alert.html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.use_tls:
            server.starttls(context=ssl.create_default_context())
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def is_us_market_open_now(now: datetime | None = None) -> bool:
    now_et = _to_eastern(now or datetime.now(timezone.utc))
    current_time = now_et.time().replace(tzinfo=None)
    return (
        is_us_market_day(now_et.date())
        and MARKET_OPEN <= current_time <= MARKET_CLOSE
    )


def is_us_market_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False
    holidays = _us_market_holidays(day.year) | _us_market_holidays(day.year + 1)
    return day not in holidays


def _build_audit_entries(
    config: dict[str, Any],
    prices: pd.DataFrame,
    indicators: pd.DataFrame,
    signals: pd.DataFrame,
) -> pd.DataFrame:
    whipsaw_window_sessions = int(config["strategy"]["false_breakout"]["whipsaw_window_sessions"])
    audit = build_false_breakout_audit(
        prices=prices,
        signals=signals,
        indicators=indicators,
        whipsaw_window_sessions=whipsaw_window_sessions,
        entry_vol_lookback=DEFAULT_ENTRY_VOL_LOOKBACK,
        entry_slope_lookback=DEFAULT_ENTRY_SLOPE_LOOKBACK,
    )
    return audit["entries"]


def _latest_confirmed_signal(
    signals: pd.DataFrame,
    ticker: str,
    filter_id: str,
    market_date: date,
) -> pd.Series | None:
    rows = signals[
        (signals["ticker"] == ticker)
        & (signals["filter_id"] == filter_id)
        & (signals["current_state"] != WARMUP)
    ].copy()
    if rows.empty:
        return None

    rows["date_obj"] = pd.to_datetime(rows["date"]).dt.date
    rows = rows[rows["date_obj"] < market_date].sort_values("date_obj")
    if rows.empty:
        return None
    return rows.iloc[-1]


def _action_from_signal(signal_row: pd.Series) -> str:
    event = str(signal_row["signal_event"])
    state = str(signal_row["current_state"])
    if event == BUY_ALERT:
        return "INVEST"
    if event == EXIT_ALERT:
        return "EXIT"
    if state == LONG:
        return "HOLD_INVESTED"
    if state == RISK_OFF:
        return "HOLD_CASH"
    return "HOLD"


def _entry_features(
    prices: pd.DataFrame,
    indicators: pd.DataFrame,
    signal_row: pd.Series,
    active_market_date: date,
) -> dict[str, float | None]:
    ticker = str(signal_row["ticker"])
    filter_id = str(signal_row["filter_id"])
    signal_date = pd.Timestamp(signal_row["date"]).date()
    cutoff = min(signal_date, active_market_date - timedelta(days=1))

    price_rows = prices[prices["ticker"] == ticker].copy()
    price_rows["date_obj"] = pd.to_datetime(price_rows["date"]).dt.date
    price_rows = price_rows[price_rows["date_obj"] <= cutoff].sort_values("date_obj")

    indicator_rows = indicators[
        (indicators["ticker"] == ticker) & (indicators["filter_id"] == filter_id)
    ].copy()
    indicator_rows["date_obj"] = pd.to_datetime(indicator_rows["date"]).dt.date
    indicator_rows = indicator_rows[indicator_rows["date_obj"] <= cutoff].sort_values("date_obj")

    entry_distance = None
    signal_price = _safe_float(signal_row.get("signal_price"))
    filter_value = _safe_float(signal_row.get("filter_value"))
    if signal_price is not None and filter_value not in (None, 0.0):
        entry_distance = signal_price / filter_value - 1.0

    filter_slope = None
    if len(indicator_rows) > DEFAULT_ENTRY_SLOPE_LOOKBACK:
        latest = _safe_float(indicator_rows.iloc[-1]["filter_value"])
        prior = _safe_float(indicator_rows.iloc[-1 - DEFAULT_ENTRY_SLOPE_LOOKBACK]["filter_value"])
        if latest is not None and prior not in (None, 0.0):
            filter_slope = latest / prior - 1.0

    recent_return = None
    recent_volatility = None
    if len(price_rows) > DEFAULT_ENTRY_VOL_LOOKBACK:
        close = price_rows["adjusted_close"].astype(float)
        latest_close = float(close.iloc[-1])
        prior_close = float(close.iloc[-1 - DEFAULT_ENTRY_VOL_LOOKBACK])
        if prior_close:
            recent_return = latest_close / prior_close - 1.0
        returns = close.pct_change().dropna().tail(DEFAULT_ENTRY_VOL_LOOKBACK)
        if len(returns) == DEFAULT_ENTRY_VOL_LOOKBACK:
            recent_volatility = float(returns.std(ddof=0) * np.sqrt(252))

    return {
        "entry_distance_pct": entry_distance,
        "filter_slope_pct": filter_slope,
        "recent_return_pct": recent_return,
        "recent_volatility_ann_pct": recent_volatility,
    }


def _false_breakout_warning(
    audit_entries: pd.DataFrame,
    ticker: str,
    filter_id: str,
    signal_date: str,
    action: str,
    entry_distance_pct: float | None,
    filter_slope_pct: float | None,
) -> dict[str, Any]:
    if action != "INVEST":
        return {
            "level": "N/A",
            "note": "False-breakout warning only applies to fresh INVEST alerts.",
            "historical_whipsaw_rate": None,
            "similar_whipsaw_rate": None,
            "similar_sample_size": 0,
        }
    if audit_entries.empty:
        return _unknown_warning("No historical false-breakout audit rows are available.")

    completed = audit_entries[
        (audit_entries["ticker"] == ticker)
        & (audit_entries["filter_id"] == filter_id)
        & (audit_entries["exit_date"].notna())
    ].copy()
    if completed.empty:
        return _unknown_warning("No completed historical round trips exist for this ticker/filter.")

    completed = completed[pd.to_datetime(completed["entry_date"]) < pd.Timestamp(signal_date)]
    if len(completed) < 5:
        return _unknown_warning("Too few completed historical round trips for this ticker/filter.")

    baseline_rate = float(completed["whipsaw"].astype(bool).mean())
    similar = completed.copy()
    if entry_distance_pct is not None:
        similar = similar[similar["entry_distance_pct"] <= entry_distance_pct]
    if filter_slope_pct is not None:
        similar = similar[similar["filter_slope_pct"] <= filter_slope_pct]

    similar_rate = None
    if len(similar) >= 5:
        similar_rate = float(similar["whipsaw"].astype(bool).mean())

    weak_distance = entry_distance_pct is not None and entry_distance_pct < 0.005
    weak_slope = filter_slope_pct is not None and filter_slope_pct <= 0.0

    if similar_rate is not None and similar_rate >= max(0.60, baseline_rate + 0.10):
        level = "HIGH"
    elif weak_distance and weak_slope:
        level = "HIGH"
    elif similar_rate is not None and similar_rate >= baseline_rate + 0.05:
        level = "ELEVATED"
    elif weak_distance or weak_slope:
        level = "ELEVATED"
    else:
        level = "NORMAL"

    parts = [
        "This is a risk warning, not proof of a future false breakout.",
        f"Historical whipsaw rate for {ticker}/{filter_id}: {_format_pct(baseline_rate)}.",
    ]
    if similar_rate is not None:
        parts.append(
            f"Similar weak-entry sample: {len(similar)} trades, {_format_pct(similar_rate)} whipsaw rate."
        )
    else:
        parts.append("Similar-entry sample is too small for a stable rate.")

    return {
        "level": level,
        "note": " ".join(parts),
        "historical_whipsaw_rate": baseline_rate,
        "similar_whipsaw_rate": similar_rate,
        "similar_sample_size": int(len(similar)),
    }


_ENTRANT_TIER_ENTER = "ENTER"
_ENTRANT_TIER_CAUTION = "CAUTION"
_ENTRANT_TIER_WAIT = "WAIT"
_ENTRANT_TIER_FRESH = "FRESH_SIGNAL"
_ENTRANT_TIER_NA = "N/A"

# Whipsaw rates by distance bucket, derived from the Phase 1 false-breakout audit.
# Used to add historical context to new-entrant notes.
_WHIPSAW_BY_DISTANCE: list[tuple[float, float, str]] = [
    # (dist_lo, dist_hi, label)
    (0.00, 0.01, "76.7%"),
    (0.01, 0.02, "65.0%"),
    (0.02, 0.03, "47.9%"),
    (0.03, 0.05, "45.6%"),
    (0.05, 1.00, "~50–65% (small historical sample)"),
]


def _whipsaw_rate_label(distance: float) -> str:
    for lo, hi, label in _WHIPSAW_BY_DISTANCE:
        if lo <= distance < hi:
            return label
    return "unknown"


def _new_entrant_guidance(
    action: str,
    entry_distance_pct: float | None,
    filter_slope_pct: float | None,
    audit_entries: pd.DataFrame,
    ticker: str,
    filter_id: str,
) -> dict[str, str]:
    """Guidance for a new entrant with no existing position."""
    if action == "INVEST":
        return {
            "tier": _ENTRANT_TIER_FRESH,
            "note": (
                "Fresh INVEST signal. This is the strategy's entry trigger. "
                "See the false-breakout warning above for historical whipsaw context."
            ),
        }

    if action not in ("HOLD_INVESTED",):
        return {
            "tier": _ENTRANT_TIER_NA,
            "note": "Market is not in a LONG regime. No entry case for a new entrant.",
        }

    dist = entry_distance_pct
    slope = filter_slope_pct

    if dist is None:
        return {"tier": "UNKNOWN", "note": "Cannot compute regime cushion — distance data unavailable."}

    historical_note = ""
    if not audit_entries.empty:
        completed = audit_entries[
            (audit_entries["ticker"] == ticker)
            & (audit_entries["filter_id"] == filter_id)
            & (audit_entries["exit_date"].notna())
        ]
        if len(completed) >= 5:
            baseline = float(completed["whipsaw"].astype(bool).mean())
            historical_note = (
                f" When the next INVEST signal eventually fires, the historical whipsaw rate "
                f"for {ticker}/{filter_id} is {baseline * 100:.0f}% overall "
                f"(entries at <1% above filter: ~77%; at 2–5%: ~46%)."
            )

    dist_pct_str = f"{dist * 100:.1f}%"
    slope_str = f"{slope * 100:.2f}%" if slope is not None else "unknown"
    slope_ok = slope is None or slope >= -0.001

    if dist > 0.03 and slope_ok:
        tier = _ENTRANT_TIER_ENTER
        note = (
            f"Regime is well established. Price is {dist_pct_str} above the filter "
            f"(slope {slope_str}/period). "
            f"Entering mid-regime is consistent with the strategy's risk-on rule. "
            f"The exit trigger fires only if price falls back to the filter — "
            f"currently {dist_pct_str} below today's close."
            f"{historical_note}"
        )
    elif dist > 0.015:
        tier = _ENTRANT_TIER_CAUTION
        note = (
            f"Price is {dist_pct_str} above the filter (slope {slope_str}/period). "
            f"Cushion is moderate. Consider entering at a reduced initial size, "
            f"or waiting for a pullback and re-entry on a fresh INVEST signal with wider distance."
            f"{historical_note}"
        )
    else:
        whipsaw_label = _whipsaw_rate_label(dist)
        tier = _ENTRANT_TIER_WAIT
        note = (
            f"Price is only {dist_pct_str} above the filter (slope {slope_str}/period). "
            f"This is effectively at the filter boundary. "
            f"Historical whipsaw rate for entries at this distance: {whipsaw_label}. "
            f"Wait for a clearer re-entry — a fresh INVEST signal with at least 2–3% distance "
            f"cuts historical whipsaw risk to roughly half."
            f"{historical_note}"
        )

    return {"tier": tier, "note": note}


def _unknown_warning(note: str) -> dict[str, Any]:
    return {
        "level": "UNKNOWN",
        "note": note,
        "historical_whipsaw_rate": None,
        "similar_whipsaw_rate": None,
        "similar_sample_size": 0,
    }


def _build_subject(market_date: date, rows: tuple[AlertRow, ...]) -> str:
    invests = sum(row.action == "INVEST" for row in rows)
    exits = sum(row.action == "EXIT" for row in rows)
    warnings = sum(row.false_breakout_warning in {"HIGH", "ELEVATED"} for row in rows)
    return (
        f"Gayed LRS alert {market_date.isoformat()}: "
        f"{invests} invest, {exits} exit, {warnings} breakout warnings"
    )


def _build_text_body(
    market_date: date,
    generated_at_et: datetime,
    rows: tuple[AlertRow, ...],
) -> str:
    lines = [
        f"Market date: {market_date.isoformat()}",
        f"Generated at: {generated_at_et.isoformat(timespec='seconds')} ET",
        "",
        "Ticker | Filter | Action | State | Signal date | False-breakout warning | Execution assets",
        "--- | --- | --- | --- | --- | --- | ---",
    ]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    row.ticker,
                    row.filter_id,
                    row.action,
                    row.position_state,
                    row.signal_date,
                    row.false_breakout_warning,
                    row.execution_assets,
                ]
            )
        )
    lines.extend(["", "Details:"])
    for row in rows:
        lines.append(
            f"- {row.ticker}/{row.filter_id}: {row.action}. "
            f"Price={_format_number(row.signal_price)}, filter={_format_number(row.filter_value)}, "
            f"distance={_format_pct(row.entry_distance_pct)}, slope={_format_pct(row.filter_slope_pct)}. "
            f"{row.false_breakout_note}"
        )
    lines.extend(["", "New Entrant Guidance (no existing position):"])
    for row in rows:
        if row.new_entrant_tier not in ("N/A", "UNKNOWN", ""):
            lines.append(
                f"- {row.ticker}/{row.filter_id}: [{row.new_entrant_tier}] {row.new_entrant_note}"
            )
    lines.extend(
        [
            "",
            "Rules:",
            "- INVEST means the latest confirmed close crossed above the filter.",
            "- EXIT means the latest confirmed close crossed at or below the filter.",
            "- HOLD_INVESTED means the signal remains LONG.",
            "- HOLD_CASH means the signal remains RISK_OFF.",
            "- False-breakout warnings are probabilistic and use historical whipsaw diagnostics.",
            "- New Entrant tiers: ENTER (>3% above filter, slope ok) | CAUTION (1.5-3%) | WAIT (<1.5%) | FRESH_SIGNAL (at cross).",
        ]
    )
    return "\n".join(lines)


def _build_html_body(
    market_date: date,
    generated_at_et: datetime,
    rows: tuple[AlertRow, ...],
) -> str:
    _TIER_COLOR = {
        "ENTER": "#1a7a1a",
        "CAUTION": "#b36b00",
        "WAIT": "#a80000",
        "FRESH_SIGNAL": "#0055a0",
        "N/A": "#555555",
        "UNKNOWN": "#555555",
    }

    def _tier_badge(tier: str) -> str:
        color = _TIER_COLOR.get(tier, "#555555")
        return (
            f'<span style="background:{color};color:#fff;padding:2px 7px;'
            f'border-radius:3px;font-size:0.85em;font-weight:bold;">{tier}</span>'
        )

    row_html = "\n".join(
        "<tr>"
        f"<td>{row.ticker}</td>"
        f"<td>{row.filter_id}</td>"
        f"<td><strong>{row.action}</strong></td>"
        f"<td>{row.position_state}</td>"
        f"<td>{row.signal_date}</td>"
        f"<td>{row.false_breakout_warning}</td>"
        f"<td>{row.execution_assets}</td>"
        "</tr>"
        for row in rows
    )
    detail_html = "\n".join(
        "<li>"
        f"<strong>{row.ticker}/{row.filter_id}</strong>: {row.action}. "
        f"Price={_format_number(row.signal_price)}, filter={_format_number(row.filter_value)}, "
        f"distance={_format_pct(row.entry_distance_pct)}, slope={_format_pct(row.filter_slope_pct)}. "
        f"{row.false_breakout_note}"
        "</li>"
        for row in rows
    )
    entrant_rows = [r for r in rows if r.new_entrant_tier not in ("N/A", "UNKNOWN", "")]
    entrant_html = "\n".join(
        "<tr>"
        f"<td><strong>{row.ticker}/{row.filter_id}</strong></td>"
        f"<td>{_tier_badge(row.new_entrant_tier)}</td>"
        f"<td style='font-size:0.9em'>{row.new_entrant_note}</td>"
        "</tr>"
        for row in entrant_rows
    )
    entrant_section = ""
    if entrant_html:
        entrant_section = f"""
  <h3>New Entrant Guidance</h3>
  <p style="font-size:0.85em;color:#444;">
    For investors with no existing position.
    <strong>ENTER</strong> = &gt;3% above filter, slope positive.
    <strong>CAUTION</strong> = 1.5–3% above filter.
    <strong>WAIT</strong> = &lt;1.5% above filter (high whipsaw risk at next cross).
  </p>
  <table border="1" cellpadding="6" cellspacing="0">
    <thead>
      <tr><th>Ticker/Filter</th><th>Tier</th><th>Note</th></tr>
    </thead>
    <tbody>{entrant_html}</tbody>
  </table>"""

    return f"""<!doctype html>
<html>
<body>
  <h2>Gayed LRS Market Alert</h2>
  <p><strong>Market date:</strong> {market_date.isoformat()}<br>
  <strong>Generated at:</strong> {generated_at_et.isoformat(timespec="seconds")} ET</p>
  <table border="1" cellpadding="6" cellspacing="0">
    <thead>
      <tr>
        <th>Ticker</th><th>Filter</th><th>Action</th><th>State</th>
        <th>Signal date</th><th>False-breakout warning</th><th>Execution assets</th>
      </tr>
    </thead>
    <tbody>{row_html}</tbody>
  </table>
  <h3>Details</h3>
  <ul>{detail_html}</ul>
  <p><em>False-breakout warnings are probabilistic and use historical whipsaw diagnostics.</em></p>
  {entrant_section}
</body>
</html>"""


def _execution_assets_by_signal_ticker(config: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for mapping in config["data"]["leveraged_execution"]:
        assets = [asset["id"] for asset in mapping["execution_assets"]]
        result[mapping["signal_ticker"]] = ", ".join(assets)
    return result


def _us_market_holidays(year: int) -> set[date]:
    holidays = {
        _observed_fixed_holiday(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter_date(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed_fixed_holiday(year, 7, 4),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed_fixed_holiday(year, 12, 25),
    }
    if year >= 2022:
        holidays.add(_observed_fixed_holiday(year, 6, 19))
    return holidays


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _easter_date(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _to_eastern(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(EASTERN)


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def _format_number(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.4f}"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value
