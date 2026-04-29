"""Generate the Gayed LRS personal trade review PDF.

Charts produced:
  A. SPY Regime Map        — SPY price vs SMA-200 with LONG/RISK-OFF background shading
  B. Growth of $10,000     — SPY B&H, SPY Strategy, UPRO B&H, UPRO Strategy (log)
  C. Drawdown Comparison   — Strategy vs Buy-and-Hold for SPY and UPRO
  D. Volatility Regime     — Annualized vol above vs below SMA (replicates paper Chart 1)
  E. Return Regime         — Annualized return above vs below SMA (replicates paper Chart 3)
  F. Rolling 3Y Performance— Rolling 3-year CAGR: Strategy vs B&H (replicates paper Chart 9)
  G. Calendar Year Returns — Annual bar chart: Strategy vs Buy-and-Hold

Metrics table: paper Table 8 numbers side-by-side with my backtest results.
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

try:
    import markdown as mdlib
    import weasyprint
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

# ── file paths ────────────────────────────────────────────────────────────────
EQUITY_CSV  = Path("outputs/backtests/fixed_rule_equity_curves.csv")
METRICS_CSV = Path("reports/tables/fixed_rule_metrics.csv")
PRICES_CSV  = Path("data/processed/prices_adjusted.csv")
REPORT_PDF  = Path("reports/gayed_lrs_review.pdf")

TRADING_DAYS = 252

# ── colour palette ────────────────────────────────────────────────────────────
BLUE    = "#2563eb"
NAVY    = "#1e3a8a"
ORANGE  = "#f97316"
GREEN   = "#16a34a"
RED     = "#dc2626"
GRAY    = "#94a3b8"
BG      = "#f8fafc"
GRID    = "#e2e8f0"
GREEN_L = "#bbf7d0"
RED_L   = "#fecaca"


# ══════════════════════════════════════════════════════════════════════════════
# Data helpers
# ══════════════════════════════════════════════════════════════════════════════

def load_equity_curves(filter_id: str = "SMA_200") -> pd.DataFrame:
    chunks = []
    for chunk in pd.read_csv(
        EQUITY_CSV, chunksize=200_000, parse_dates=["date"],
        usecols=["date", "signal_ticker", "filter_id", "execution_id",
                 "result_type", "daily_return", "equity"],
    ):
        rows = chunk[chunk["filter_id"] == filter_id]
        if not rows.empty:
            chunks.append(rows)
    if not chunks:
        raise ValueError(f"No equity data found for filter_id={filter_id}")
    return pd.concat(chunks, ignore_index=True).sort_values(
        ["signal_ticker", "execution_id", "result_type", "date"]
    ).reset_index(drop=True)


def get_combo(df: pd.DataFrame, signal_ticker: str, execution_id: str,
              result_type: str) -> pd.DataFrame:
    mask = (
        (df["signal_ticker"] == signal_ticker)
        & (df["execution_id"] == execution_id)
        & (df["result_type"] == result_type)
    )
    return df[mask].reset_index(drop=True)


def load_spy_prices() -> pd.DataFrame:
    df = pd.read_csv(PRICES_CSV, parse_dates=["date"])
    spy = df[df["ticker"] == "SPY"][["date", "adjusted_close"]].dropna()
    return spy.sort_values("date").reset_index(drop=True)


def load_metrics(filter_id: str = "SMA_200") -> pd.DataFrame:
    df = pd.read_csv(METRICS_CSV)
    return df[df["filter_id"] == filter_id].reset_index(drop=True)


def normalize(equity: pd.Series, start: float = 10_000.0) -> pd.Series:
    return equity / equity.iloc[0] * start


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Chart utilities
# ══════════════════════════════════════════════════════════════════════════════

def to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def style_ax(ax: plt.Axes, title: str) -> None:
    ax.set_facecolor(BG)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_title(title, fontsize=9.5, fontweight="bold", color="#0f172a", pad=8)
    ax.tick_params(labelsize=7.5, colors="#475569")
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)


def fmt_year(ax: plt.Axes, step: int = 4) -> None:
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(step))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha="right")


# ══════════════════════════════════════════════════════════════════════════════
# Chart A — SPY Regime Map
# ══════════════════════════════════════════════════════════════════════════════

def chart_regime_map(prices: pd.DataFrame) -> str:
    close = prices["adjusted_close"]
    dates = pd.to_datetime(prices["date"])
    sma200 = close.rolling(200, min_periods=200).mean()

    fig, ax = plt.subplots(figsize=(10.5, 4.2), facecolor="white")

    # Shade LONG (green) and RISK-OFF (red) regions using xaxis transform
    valid = sma200.notna()
    above = (close > sma200) & valid
    below = (~above) & valid

    ax.fill_between(dates, 0, 1,
                    where=above.values, transform=ax.get_xaxis_transform(),
                    color=GREEN_L, alpha=0.5, linewidth=0, label="_nolegend_")
    ax.fill_between(dates, 0, 1,
                    where=below.values, transform=ax.get_xaxis_transform(),
                    color=RED_L, alpha=0.5, linewidth=0, label="_nolegend_")

    ax.plot(dates, close, color=GRAY, linewidth=0.8, alpha=0.85, label="SPY Close")
    ax.plot(dates, sma200, color=BLUE, linewidth=1.6, label="SMA 200")

    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"${x:.0f}" if x < 100 else f"${x:.0f}"
    ))
    ax.set_ylabel("SPY Price (log scale)", fontsize=8, color="#475569")

    legend_handles = [
        ax.lines[0], ax.lines[1],
        mpatches.Patch(facecolor=GREEN_L, alpha=0.7, label="LONG — SPY above SMA 200"),
        mpatches.Patch(facecolor=RED_L,   alpha=0.7, label="RISK-OFF — SPY at/below SMA 200"),
    ]
    ax.legend(handles=legend_handles, fontsize=8, framealpha=0.9, loc="upper left", ncol=2)
    style_ax(ax, "Chart A — SPY Price vs SMA-200 Regime Map  |  Green = Long leveraged ETF  ·  Red = Cash")
    fmt_year(ax)
    fig.tight_layout()
    return to_b64(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Chart B — Growth of $10,000
# ══════════════════════════════════════════════════════════════════════════════

def chart_growth(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), facecolor="white")

    # Left: SPY 1x
    ax1 = axes[0]
    for eid, rt, color, lw, label in [
        ("SPY_1X", "strategy", BLUE, 1.8, "SPY Strategy (SMA 200 → Cash)"),
        ("SPY_1X", "buy_hold", GRAY, 1.2, "SPY Buy & Hold"),
    ]:
        combo = get_combo(df, "SPY", eid, rt)
        if combo.empty:
            continue
        eq = normalize(combo["equity"])
        ax1.plot(pd.to_datetime(combo["date"]), eq, color=color, linewidth=lw, label=label)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"${x/1000:.0f}k" if x >= 1000 else f"${x:.0f}"
    ))
    ax1.legend(fontsize=8, framealpha=0.9, loc="upper left")
    ax1.set_ylabel("Portfolio Value (start $10,000)", fontsize=8, color="#475569")
    style_ax(ax1, "Chart B1 — SPY 1x: Strategy vs Buy-and-Hold  (1993–2026)")
    fmt_year(ax1)

    # Right: UPRO 3x log
    ax2 = axes[1]
    for eid, rt, color, lw, label in [
        ("UPRO_3X", "strategy", NAVY,   1.8, "UPRO 3x Strategy (SMA 200 → Cash)"),
        ("UPRO_3X", "buy_hold", ORANGE, 1.2, "UPRO 3x Buy & Hold"),
    ]:
        combo = get_combo(df, "SPY", eid, rt)
        if combo.empty:
            continue
        eq = normalize(combo["equity"])
        ax2.plot(pd.to_datetime(combo["date"]), eq, color=color, linewidth=lw, label=label)
    ax2.set_yscale("log")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"${x/1000:.0f}k" if x >= 1000 else f"${x:.0f}"
    ))
    ax2.legend(fontsize=8, framealpha=0.9, loc="upper left")
    ax2.set_ylabel("Portfolio Value, log scale", fontsize=8, color="#475569")
    style_ax(ax2, "Chart B2 — UPRO 3x: Strategy vs Buy-and-Hold  (2009–2026, log)")
    fmt_year(ax2, step=3)

    fig.tight_layout(pad=2.5)
    return to_b64(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Chart C — Drawdown
# ══════════════════════════════════════════════════════════════════════════════

def chart_drawdown(df: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), facecolor="white")

    panels = [
        ("SPY",  "SPY_1X",  "Chart C1 — SPY 1x: Drawdown from Peak"),
        ("SPY",  "UPRO_3X", "Chart C2 — UPRO 3x: Drawdown from Peak"),
    ]
    strat_colors = [BLUE, NAVY]
    bh_colors    = [GRAY, ORANGE]

    for ax, (sig, eid, title), sc, bc in zip(axes, panels, strat_colors, bh_colors):
        strat = get_combo(df, sig, eid, "strategy")
        bh    = get_combo(df, sig, eid, "buy_hold")
        for data, color, label in [(bh, bc, "Buy & Hold"), (strat, sc, "Strategy")]:
            if data.empty:
                continue
            dd = drawdown_series(data["equity"]) * 100
            ax.fill_between(pd.to_datetime(data["date"]), dd, 0,
                            color=color, alpha=0.3, label=label)
            ax.plot(pd.to_datetime(data["date"]), dd, color=color, linewidth=0.8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        ax.legend(fontsize=8, framealpha=0.9, loc="lower left")
        ax.set_ylabel("Drawdown (%)", fontsize=8, color="#475569")
        style_ax(ax, title)
        fmt_year(ax, step=4 if sig == "SPY" else 3)

    fig.tight_layout(pad=2.5)
    return to_b64(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Charts D & E — Regime volatility and return (replicate paper Charts 1 & 3)
# ══════════════════════════════════════════════════════════════════════════════

def _regime_stats(prices: pd.DataFrame) -> dict[int, dict]:
    close = prices["adjusted_close"].reset_index(drop=True)
    daily_ret = close.pct_change().dropna()
    close_aligned = close.loc[daily_ret.index]

    windows = [10, 20, 50, 100, 200]
    stats: dict[int, dict] = {}
    for w in windows:
        sma = close.rolling(w, min_periods=w).mean()
        sma_aligned = sma.loc[daily_ret.index]
        valid = sma_aligned.notna()
        above = (close_aligned > sma_aligned) & valid
        below = (~above) & valid

        r_above = daily_ret[above]
        r_below = daily_ret[below]

        vol_above = r_above.std(ddof=0) * np.sqrt(TRADING_DAYS) if len(r_above) > 1 else np.nan
        vol_below = r_below.std(ddof=0) * np.sqrt(TRADING_DAYS) if len(r_below) > 1 else np.nan
        ret_above = (1 + r_above).prod() ** (TRADING_DAYS / max(len(r_above), 1)) - 1
        ret_below = (1 + r_below).prod() ** (TRADING_DAYS / max(len(r_below), 1)) - 1
        pct_above = above.sum() / valid.sum() if valid.sum() > 0 else np.nan

        stats[w] = dict(vol_above=vol_above, vol_below=vol_below,
                        ret_above=ret_above, ret_below=ret_below,
                        pct_above=pct_above)
    return stats


def chart_vol_regime(prices: pd.DataFrame) -> str:
    stats = _regime_stats(prices)
    windows = [10, 20, 50, 100, 200]
    labels = [f"{w}-day" for w in windows]
    v_above = [stats[w]["vol_above"] * 100 for w in windows]
    v_below = [stats[w]["vol_below"] * 100 for w in windows]

    x = np.arange(len(windows))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8.5, 4.2), facecolor="white")
    b1 = ax.bar(x - width/2, v_above, width, color=BLUE,   alpha=0.85, label="Volatility Above SMA")
    b2 = ax.bar(x + width/2, v_below, width, color=ORANGE, alpha=0.85, label="Volatility Below SMA")
    for bar in b1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8, color=BLUE)
    for bar in b2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=8, color=ORANGE)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.legend(fontsize=9, framealpha=0.9)
    ax.set_ylabel("Annualized Volatility", fontsize=8.5, color="#475569")
    style_ax(ax, (
        "Chart D — SPY Annualized Volatility Above vs Below Moving Averages  (1993–Present)\n"
        "Paper (1928–2015): 14.7% above vs 26.5% below for the 200-day SMA"
    ))
    fig.tight_layout()
    return to_b64(fig)


def chart_return_regime(prices: pd.DataFrame) -> str:
    stats = _regime_stats(prices)
    windows = [10, 20, 50, 100, 200]
    labels = [f"{w}-day" for w in windows]
    r_above = [stats[w]["ret_above"] * 100 for w in windows]
    r_below = [stats[w]["ret_below"] * 100 for w in windows]

    x = np.arange(len(windows))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8.5, 4.2), facecolor="white")
    b1 = ax.bar(x - width/2, r_above, width, color=BLUE,   alpha=0.85, label="Return Above SMA")
    b2 = ax.bar(x + width/2, r_below, width, color=ORANGE, alpha=0.85, label="Return Below SMA")
    for bar in (list(b1) + list(b2)):
        v = bar.get_height()
        offset = 0.4 if v >= 0 else -1.8
        ax.text(bar.get_x() + bar.get_width()/2, v + offset,
                f"{v:.1f}%", ha="center", va="bottom", fontsize=8,
                color=BLUE if bar in b1 else ORANGE)
    ax.axhline(0, color="#475569", linewidth=0.8, linestyle="--")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.legend(fontsize=9, framealpha=0.9)
    ax.set_ylabel("Annualized Return", fontsize=8.5, color="#475569")
    style_ax(ax, (
        "Chart E — SPY Annualized Return Above vs Below Moving Averages  (1993–Present)\n"
        "Paper (1928–2015): +14.1% above vs −2.3% below for the 200-day SMA"
    ))
    fig.tight_layout()
    return to_b64(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Chart F — Rolling 3-Year Outperformance
# ══════════════════════════════════════════════════════════════════════════════

def chart_rolling_outperformance(df: pd.DataFrame) -> str:
    window = 3 * TRADING_DAYS

    combos = [
        ("SPY", "SPY_1X",  BLUE,   "SPY 1x LRS"),
        ("SPY", "SSO_2X",  GREEN,  "SPY→SSO 2x LRS"),
        ("SPY", "UPRO_3X", NAVY,   "SPY→UPRO 3x LRS"),
    ]

    fig, ax = plt.subplots(figsize=(10.5, 4.2), facecolor="white")

    for sig, eid, color, label in combos:
        strat = get_combo(df, sig, eid, "strategy")
        bh    = get_combo(df, sig, eid, "buy_hold")
        if strat.empty or bh.empty:
            continue

        merged = pd.merge(
            strat[["date", "daily_return"]].rename(columns={"daily_return": "s"}),
            bh[["date", "daily_return"]].rename(columns={"daily_return": "b"}),
            on="date", how="inner",
        ).sort_values("date").reset_index(drop=True)

        # Rolling CAGR using cumulative product ratio
        cum_s = (1 + merged["s"]).cumprod()
        cum_b = (1 + merged["b"]).cumprod()
        # ratio of trailing window
        roll_s = cum_s / cum_s.shift(window).bfill()
        roll_b = cum_b / cum_b.shift(window).bfill()
        ann_s = roll_s ** (TRADING_DAYS / window) - 1
        ann_b = roll_b ** (TRADING_DAYS / window) - 1
        excess = (ann_s - ann_b) * 100

        dates = pd.to_datetime(merged["date"])
        ax.plot(dates, excess, color=color, linewidth=1.2, label=label, alpha=0.85)

    ax.axhline(0, color=RED, linewidth=1.0, linestyle="--", alpha=0.6, label="Zero line")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.legend(fontsize=8, framealpha=0.9, loc="upper right")
    ax.set_ylabel("Rolling 3Y Outperformance vs B&H (annualised)", fontsize=8, color="#475569")
    style_ax(ax, (
        "Chart F — Rolling 3-Year Outperformance: LRS vs Buy-and-Hold\n"
        "Positive = strategy ahead of B&H. Replicates paper Chart 9."
    ))
    fmt_year(ax)
    fig.tight_layout()
    return to_b64(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Chart G — Calendar Year Returns
# ══════════════════════════════════════════════════════════════════════════════

def chart_calendar_year(df: pd.DataFrame) -> str:
    pairs = [
        ("SPY", "SPY_1X",  "Chart G1 — SPY 1x: Calendar Year Returns"),
        ("SPY", "UPRO_3X", "Chart G2 — UPRO 3x: Calendar Year Returns"),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 6.5), facecolor="white")

    for ax, (sig, eid, title) in zip(axes, pairs):
        strat = get_combo(df, sig, eid, "strategy")
        bh    = get_combo(df, sig, eid, "buy_hold")
        if strat.empty or bh.empty:
            continue

        def annual(data: pd.DataFrame) -> pd.Series:
            d = data.copy()
            d["year"] = pd.to_datetime(d["date"]).dt.year
            return d.groupby("year")["daily_return"].apply(
                lambda r: (1 + r).prod() - 1
            ) * 100

        strat_yr = annual(strat)
        bh_yr    = annual(bh)
        years = sorted(set(strat_yr.index) & set(bh_yr.index))

        s_vals = [strat_yr.get(y, np.nan) for y in years]
        b_vals = [bh_yr.get(y, np.nan) for y in years]

        x = np.arange(len(years))
        w = 0.38
        ax.bar(x - w/2, s_vals, w, color=BLUE,   alpha=0.85, label="Strategy")
        ax.bar(x + w/2, b_vals, w, color=GRAY,   alpha=0.75, label="Buy & Hold")

        ax.set_xticks(x)
        ax.set_xticklabels(years, rotation=45, ha="right", fontsize=6.5)
        ax.axhline(0, color="#475569", linewidth=0.6)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        ax.legend(fontsize=8, framealpha=0.9, loc="upper left")
        ax.set_ylabel("Annual Return (%)", fontsize=8, color="#475569")
        style_ax(ax, title)

    fig.tight_layout(pad=2.5)
    return to_b64(fig)


# ══════════════════════════════════════════════════════════════════════════════
# Metrics comparison table HTML
# ══════════════════════════════════════════════════════════════════════════════

# Paper Table 8 — 200-day LRS, Oct 1928 – Oct 2015 (synthetic leverage, 1% annual fee)
_PAPER = [
    ("S&P 500 Buy & Hold",  "9.1%",  "18.9%", "0.30", "0.43", "−86.2%", "~0"),
    ("S&P 1.25x LRS",       "12.5%", "15.5%", "0.53", "0.83", "−59.0%", "~5"),
    ("S&P 2x LRS",          "19.1%", "24.9%", "0.51", "0.90", "−78.7%", "~5"),
    ("S&P 3x LRS",          "26.8%", "37.3%", "0.47", "0.90", "−92.2%", "~5"),
]


def _pct(v) -> str:
    return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v*100:.1f}%"

def _num(v, d: int = 2) -> str:
    return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{d}f}"


def build_metrics_table(metrics: pd.DataFrame) -> str:
    wanted = [
        ("SPY", "SPY_1X",  "strategy", "SPY 1x Strategy",    "1993–2026"),
        ("SPY", "SPY_1X",  "buy_hold", "SPY 1x Buy & Hold",  "1993–2026"),
        ("SPY", "SSO_2X",  "strategy", "SPY→SSO 2x Strategy","2006–2026"),
        ("SPY", "SSO_2X",  "buy_hold", "SSO 2x Buy & Hold",  "2006–2026"),
        ("SPY", "UPRO_3X", "strategy", "SPY→UPRO 3x Strategy","2009–2026"),
        ("SPY", "UPRO_3X", "buy_hold", "UPRO 3x Buy & Hold", "2009–2026"),
    ]

    def row_class(result_type: str) -> str:
        return ' style="background:#eff6ff;"' if result_type == "strategy" else ""

    paper_rows = "\n".join(
        f'<tr><td>{n}</td><td>{c}</td><td>{v}</td><td>{sh}</td>'
        f'<td>{so}</td><td>{md}</td><td>{tr}</td><td style="font-size:8pt;color:#64748b">1928–2015</td></tr>'
        for n, c, v, sh, so, md, tr in _PAPER
    )

    my_rows = ""
    for sig, eid, rt, label, period in wanted:
        row = metrics[
            (metrics["signal_ticker"] == sig)
            & (metrics["execution_id"] == eid)
            & (metrics["result_type"] == rt)
        ]
        rc = row_class(rt)
        if row.empty:
            my_rows += f'<tr{rc}><td>{label}</td><td colspan="6" style="color:#94a3b8">No data — re-run backtest</td><td style="font-size:8pt;color:#64748b">{period}</td></tr>\n'
            continue
        r = row.iloc[0]
        s_date = str(r.get("start_date", ""))[:10]
        e_date = str(r.get("end_date",   ""))[:10]
        my_rows += (
            f'<tr{rc}>'
            f'<td>{label}</td>'
            f'<td>{_pct(r.get("CAGR"))}</td>'
            f'<td>{_pct(r.get("annualized_volatility"))}</td>'
            f'<td>{_num(r.get("sharpe_ratio"))}</td>'
            f'<td>{_num(r.get("sortino_ratio"))}</td>'
            f'<td>{_pct(r.get("max_drawdown"))}</td>'
            f'<td>{_num(r.get("trades_per_year"), 1)}</td>'
            f'<td style="font-size:8pt;color:#64748b">{s_date} → {e_date}</td>'
            f'</tr>\n'
        )

    return f"""
<table>
<thead>
<tr>
  <th>Strategy</th><th>CAGR</th><th>Ann. Vol</th><th>Sharpe</th>
  <th>Sortino</th><th>Max DD</th><th>Trades/Yr</th><th>Period</th>
</tr>
</thead>
<tbody>
<tr style="background:#1e3a8a;color:white;">
  <td colspan="8"><strong>Paper Results — Gayed &amp; Bilello (2016), S&amp;P 500 synthetic leverage,
  Oct 1928–Oct 2015, 1% annual leverage fee, risk-off = T-bills</strong></td>
</tr>
{paper_rows}
<tr style="background:#166534;color:white;">
  <td colspan="8"><strong>My Backtest — SPY/SSO/UPRO ETFs, SMA-200 signal, risk-off = 0% cash,
  costs = 2 bps slippage+spread per side</strong></td>
</tr>
{my_rows}
</tbody>
</table>
<p style="font-size:8.5pt;color:#64748b;margin-top:6px;">
<strong>Period difference:</strong> paper runs from 1928; my data starts at SPY inception (Jan 1993).
SSO launched Jun 2006, UPRO launched Jun 2009. Shorter periods explain lower absolute returns on
leveraged ETF strategies. Sharpe is shown without risk-free rate deduction in both paper and my backtest.
Risk-off = 0% cash in my backtest vs T-bills in the paper — underestimates strategy return during
high-rate periods (e.g. 2022–2024).
</p>
"""


# ══════════════════════════════════════════════════════════════════════════════
# Report markdown body
# ══════════════════════════════════════════════════════════════════════════════

REPORT_MD = """# Gayed-Bilello Leverage Rotation Strategy — Personal Trade Review

**Reference:** *Leverage for the Long Run* — Michael A. Gayed CFA & Charlie Bilello CMT, 2016 Charles H. Dow Award

---

## The Rule (Exact Paper Definition)

> When the S&P 500 Index closes **above** its 200-day Simple Moving Average → go **long** the leveraged ETF.
>
> When the S&P 500 Index closes **at or below** its 200-day Simple Moving Average → rotate into **Treasury bills**.

- Signal: confirmed at end-of-day close using `adjusted_close`
- Execution: next session open (no same-day lookahead)
- Filter: SMA, not EMA. Length: 200 calendar days
- Risk-off: paper uses T-bills; this backtest uses 0% cash (conservative)

---

## How to Read the Signal (Live Use)

| Condition | Action |
|---|---|
| SPY close > SMA-200 and you are in cash | **Buy** leveraged ETF at next open |
| SPY close ≤ SMA-200 and you hold the ETF | **Sell** leveraged ETF at next open, move to cash |
| No change | Hold current position |

Check the signal each day after market close. Act at the following morning's open.

---

## Metrics Comparison — Paper vs My Backtest

"""


# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════

CSS = """
@page {
  size: A4;
  margin: 2cm 2.2cm 2cm 2.2cm;
  @bottom-right {
    content: "Page " counter(page) " of " counter(pages);
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 8.5pt;
    color: #94a3b8;
  }
}

* { box-sizing: border-box; }

body {
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  font-size: 10pt;
  line-height: 1.70;
  color: #1e293b;
}

h1 {
  font-size: 19pt;
  font-weight: 700;
  color: #0f172a;
  border-bottom: 3px solid #2563eb;
  padding-bottom: 9px;
  margin-top: 0;
  margin-bottom: 6px;
}

h2 {
  font-size: 13pt;
  font-weight: 700;
  color: #1e40af;
  border-left: 4px solid #2563eb;
  padding-left: 10px;
  margin-top: 26px;
  margin-bottom: 6px;
  page-break-after: avoid;
}

h3 {
  font-size: 10.5pt;
  font-weight: 600;
  color: #334155;
  margin-top: 16px;
  margin-bottom: 4px;
  page-break-after: avoid;
}

p { margin: 0 0 8px 0; text-align: justify; }

blockquote {
  margin: 10px 0;
  padding: 8px 16px;
  border-left: 4px solid #2563eb;
  background: #eff6ff;
  font-style: italic;
  color: #1e40af;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0 14px 0;
  font-size: 8.5pt;
  page-break-inside: avoid;
}

thead tr { background: #1e40af; color: white; }
thead th { padding: 6px 8px; text-align: left; font-weight: 600; }
tbody tr:nth-child(even) { background: #f8fafc; }
tbody td { padding: 5px 8px; border-bottom: 1px solid #e2e8f0; }

code {
  font-family: 'Courier New', monospace;
  font-size: 8pt;
  background: #f1f5f9;
  color: #1e40af;
  padding: 1px 5px;
  border-radius: 3px;
}

hr { border: none; border-top: 1px solid #e2e8f0; margin: 18px 0; }

ul, ol { padding-left: 18px; margin: 4px 0 8px 0; }
li { margin-bottom: 3px; }

.chart-block {
  margin: 16px 0 20px 0;
  text-align: center;
  page-break-inside: avoid;
}

.chart-block img {
  max-width: 100%;
  border-radius: 5px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.10);
}

.chart-caption {
  font-size: 8pt;
  color: #64748b;
  margin-top: 4px;
  font-style: italic;
}

.page-break { page-break-before: always; }
"""


# ══════════════════════════════════════════════════════════════════════════════
# HTML assembly
# ══════════════════════════════════════════════════════════════════════════════

def img_block(b64: str, caption: str) -> str:
    return (
        f'<div class="chart-block">'
        f'<img src="data:image/png;base64,{b64}" alt="{caption}">'
        f'<div class="chart-caption">{caption}</div>'
        f'</div>'
    )


def build_html(charts: dict[str, str], metrics_table: str) -> str:
    md = mdlib.Markdown(extensions=["tables", "fenced_code"])
    body = md.convert(REPORT_MD)

    charts_section = f"""
{metrics_table}

<div class="page-break"></div>
<h2>Charts</h2>

<h3>Chart A — SPY Regime Map</h3>
<p>The SMA-200 divides history into LONG regimes (green) and RISK-OFF regimes (red).
The signal is generated at daily close; execution happens at the next session open.</p>
{img_block(charts['regime'], "SPY price vs SMA-200. Green = long leveraged ETF. Red = move to cash.")}

<h3>Chart B — Growth of $10,000</h3>
<p>Left panel: SPY 1x — strategy vs buy-and-hold. Right panel: UPRO 3x on a log scale.
The strategy exits to cash during risk-off periods, dramatically reducing the worst drawdowns
of the leveraged buy-and-hold position. Both series start at $10,000.</p>
{img_block(charts['growth'], "Growth of $10,000. Note: UPRO data starts June 2009.")}

<h3>Chart C — Drawdown from Peak</h3>
<p>The SMA-200 timing rule's primary value is downside protection, not upside capture.
The strategy significantly truncates the worst drawdowns on both SPY and UPRO.</p>
{img_block(charts['drawdown'], "Drawdown from peak. Shaded area shows underwater periods.")}

<div class="page-break"></div>

<h3>Chart D — Annualized Volatility Above vs Below SMA</h3>
<p>Replicates paper Chart 1 (1928–2015), now computed on SPY data from 1993.
The pattern is consistent: volatility is materially lower when SPY trades above its moving average.
Paper found 14.7% above vs 26.5% below for the 200-day SMA.</p>
{img_block(charts['vol_regime'], "Annualized volatility by regime. Paper: 14.7% above vs 26.5% below (200-day, 1928–2015).")}

<h3>Chart E — Annualized Return Above vs Below SMA</h3>
<p>Replicates paper Chart 3. Returns when SPY is above its SMA are strongly positive;
returns when below are near zero or negative. The 200-day SMA shows the clearest separation.
Paper found +14.1% above vs −2.3% below for the 200-day SMA.</p>
{img_block(charts['ret_regime'], "Annualized return by regime. Paper: +14.1% above vs −2.3% below (200-day, 1928–2015).")}

<h3>Chart F — Rolling 3-Year Outperformance</h3>
<p>Replicates paper Chart 9. Shows how much the LRS outperforms (or underperforms) buy-and-hold
on a rolling 3-year basis. Periods below zero are when the strategy lagged the market — typically
strong uninterrupted bull runs (1995–2000, 2013–2021).</p>
{img_block(charts['rolling'], "Rolling 3-year annualised outperformance vs buy-and-hold. Dashed = zero line.")}

<h3>Chart G — Calendar Year Returns</h3>
<p>Year-by-year comparison of strategy (blue) vs buy-and-hold (gray).
The strategy underperforms in strong bull years but protects capital in bear years (2000, 2002, 2008, 2022).</p>
{img_block(charts['calendar'], "Calendar year returns. Strategy protects in bear years at the cost of some bull-year upside.")}
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Gayed LRS — Personal Trade Review</title>
<style>{CSS}</style>
</head>
<body>
{body}
{charts_section}
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    for path in [EQUITY_CSV, METRICS_CSV, PRICES_CSV]:
        if not path.exists():
            print(f"Missing file: {path}"); sys.exit(1)

    print("Loading data...")
    df      = load_equity_curves("SMA_200")
    metrics = load_metrics("SMA_200")
    prices  = load_spy_prices()

    print("Generating Chart A: SPY regime map...")
    charts: dict[str, str] = {}
    charts["regime"] = chart_regime_map(prices)

    print("Generating Chart B: growth of $10,000...")
    charts["growth"] = chart_growth(df)

    print("Generating Chart C: drawdown...")
    charts["drawdown"] = chart_drawdown(df)

    print("Generating Chart D: volatility regime...")
    charts["vol_regime"] = chart_vol_regime(prices)

    print("Generating Chart E: return regime...")
    charts["ret_regime"] = chart_return_regime(prices)

    print("Generating Chart F: rolling 3-year outperformance...")
    charts["rolling"] = chart_rolling_outperformance(df)

    print("Generating Chart G: calendar year returns...")
    charts["calendar"] = chart_calendar_year(df)

    print("Building metrics table...")
    metrics_table = build_metrics_table(metrics)

    print("Rendering PDF (this takes ~30–60 seconds)...")
    html = build_html(charts, metrics_table)
    REPORT_PDF.parent.mkdir(parents=True, exist_ok=True)
    weasyprint.HTML(string=html, base_url=str(Path.cwd())).write_pdf(str(REPORT_PDF))

    size_kb = REPORT_PDF.stat().st_size // 1024
    print(f"\nSaved: {REPORT_PDF.resolve()}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
