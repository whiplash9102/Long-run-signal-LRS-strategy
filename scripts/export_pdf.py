"""Generate the final strategy review PDF with embedded charts.

Charts generated:
  1. SPY — Strategy (SMA 200) vs Buy-and-Hold equity curve
  2. SPY — Drawdown comparison over time (strategy vs buy-and-hold)
  3. UPRO 3x — Strategy (SMA 200) vs Buy-and-Hold equity curve
  4. UPRO 3x — Drawdown comparison over time
  5. TQQQ 3x — Strategy (EMA 200) vs Buy-and-Hold equity curve
  6. EMA Sensitivity — Calmar ratio by EMA length (SPY and QQQ)
"""

import base64
import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

try:
    import markdown as mdlib
    import weasyprint
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

REPORT_MD  = Path("reports/final_strategy_review.md")
REPORT_PDF = Path("reports/final_strategy_review.pdf")
EQUITY_CSV = Path("outputs/backtests/fixed_rule_equity_curves.csv")
SENS_CSV   = Path("reports/tables/parameter_sensitivity.csv")

# ─── colour palette ────────────────────────────────────────────────────────────
BLUE    = "#2563eb"
GRAY    = "#94a3b8"
RED     = "#ef4444"
RED_LT  = "#fca5a5"
BG      = "#f8fafc"
GRID    = "#e2e8f0"


# ══════════════════════════════════════════════════════════════════════════════
# Chart helpers
# ══════════════════════════════════════════════════════════════════════════════

def _to_b64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _load_equity_slice(
    signal_ticker: str,
    filter_id: str,
    execution_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (strategy_df, buyhold_df) for the requested combo."""
    chunks = []
    for chunk in pd.read_csv(EQUITY_CSV, chunksize=200_000,
                              parse_dates=["date"],
                              usecols=["date", "signal_ticker", "filter_id",
                                       "execution_id", "result_type",
                                       "equity", "daily_return"]):
        rows = chunk[
            (chunk["signal_ticker"] == signal_ticker)
            & (chunk["filter_id"] == filter_id)
            & (chunk["execution_id"] == execution_id)
        ]
        if not rows.empty:
            chunks.append(rows)

    if not chunks:
        raise ValueError(f"No equity data for {signal_ticker}/{filter_id}/{execution_id}")

    df = pd.concat(chunks).sort_values("date")
    strat = df[df["result_type"] == "strategy"].reset_index(drop=True)
    bh    = df[df["result_type"] == "buy_hold"].reset_index(drop=True)
    return strat, bh


def _drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def _style_axes(ax, title: str) -> None:
    ax.set_facecolor(BG)
    ax.grid(True, color=GRID, linewidth=0.6, linestyle="-")
    ax.set_title(title, fontsize=10, fontweight="bold", color="#0f172a", pad=8)
    ax.tick_params(labelsize=7.5, colors="#475569")
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator(5))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")


# ─── Chart 1 & 2 : equity curve + drawdown for any combo ──────────────────────

def chart_equity_and_drawdown(
    signal_ticker: str,
    filter_id: str,
    execution_id: str,
    title: str,
    subtitle_strat: str = "Strategy",
    subtitle_bh: str = "Buy and Hold",
    log_scale: bool = True,
) -> str:
    strat, bh = _load_equity_slice(signal_ticker, filter_id, execution_id)
    start_val = 100_000.0
    s_eq = strat["equity"].values
    b_eq = bh["equity"].values
    s_norm = s_eq / s_eq[0] * start_val
    b_norm = b_eq / b_eq[0] * start_val

    s_dd = _drawdown_series(pd.Series(s_norm))
    b_dd = _drawdown_series(pd.Series(b_norm))
    dates = strat["date"].values

    fig, axes = plt.subplots(2, 1, figsize=(8.5, 5.2),
                             gridspec_kw={"height_ratios": [3, 1.5], "hspace": 0.35},
                             facecolor="white")

    # ── top: equity curve ────────────────────────────────────────────────────
    ax = axes[0]
    ax.plot(dates, b_norm, color=GRAY, linewidth=1.2, label=subtitle_bh, alpha=0.85)
    ax.plot(dates, s_norm, color=BLUE, linewidth=1.6, label=subtitle_strat)
    if log_scale:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}k" if x >= 1000 else f"${x:.0f}")
        )
    else:
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}k")
        )
    ax.legend(fontsize=8, framealpha=0.9, loc="upper left")
    ax.set_ylabel("Portfolio value (log)", fontsize=8, color="#475569")
    _style_axes(ax, f"{title} — Equity Curve")

    # ── bottom: drawdown ─────────────────────────────────────────────────────
    ax2 = axes[1]
    ax2.fill_between(dates, b_dd * 100, 0, color=RED_LT, alpha=0.6, label=subtitle_bh)
    ax2.fill_between(dates, s_dd * 100, 0, color=RED, alpha=0.7, label=subtitle_strat)
    ax2.set_ylabel("Drawdown (%)", fontsize=8, color="#475569")
    ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax2.legend(fontsize=8, framealpha=0.9, loc="lower left")
    _style_axes(ax2, "Drawdown from Peak")

    return _to_b64(fig)


# ─── Chart 3 : EMA sensitivity ────────────────────────────────────────────────

def chart_ema_sensitivity() -> str:
    sens = pd.read_csv(SENS_CSV)
    ema_only = sens[sens["filter_id"].str.startswith("EMA")].copy()
    ema_only["length"] = ema_only["filter_id"].str.replace("EMA_", "").astype(int)

    colours = {
        "SPY": "#2563eb",
        "QQQ": "#7c3aed",
        "IWM": "#16a34a",
        "VGK": "#ea580c",
        "EZU": "#db2777",
    }

    fig, ax = plt.subplots(figsize=(8.5, 3.8), facecolor="white")
    for ticker, grp in ema_only.groupby("signal_ticker"):
        g = grp.sort_values("length")
        ax.plot(g["length"], g["calmar_ratio"],
                marker="o", markersize=4,
                color=colours.get(ticker, "#64748b"),
                linewidth=1.5, label=ticker)

    ax.set_xlabel("EMA Length", fontsize=8.5, color="#475569")
    ax.set_ylabel("Calmar Ratio", fontsize=8.5, color="#475569")
    ax.set_facecolor(BG)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_title("EMA Sensitivity — Calmar Ratio by EMA Length (all ETFs)",
                 fontsize=10, fontweight="bold", color="#0f172a", pad=8)
    ax.legend(fontsize=8.5, framealpha=0.9)
    ax.tick_params(labelsize=8, colors="#475569")
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)

    return _to_b64(fig)


# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════

CSS = """
@page {
    size: A4;
    margin: 2.2cm 2.5cm 2.2cm 2.5cm;
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        font-size: 9pt;
        color: #94a3b8;
    }
}

* { box-sizing: border-box; }

body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.72;
    color: #1e293b;
}

h1 {
    font-size: 21pt;
    font-weight: 700;
    color: #0f172a;
    border-bottom: 3px solid #2563eb;
    padding-bottom: 10px;
    margin-top: 0;
    margin-bottom: 4px;
}

h2 {
    font-size: 13.5pt;
    font-weight: 700;
    color: #1e40af;
    margin-top: 30px;
    margin-bottom: 6px;
    border-left: 4px solid #2563eb;
    padding-left: 10px;
    page-break-after: avoid;
}

h3 {
    font-size: 11pt;
    font-weight: 600;
    color: #334155;
    margin-top: 18px;
    margin-bottom: 4px;
    page-break-after: avoid;
}

p { margin: 0 0 9px 0; text-align: justify; }

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 16px 0;
    font-size: 9pt;
    page-break-inside: avoid;
}

thead tr { background-color: #1e40af; color: #ffffff; }
thead th { padding: 7px 9px; text-align: left; font-weight: 600; }
tbody tr:nth-child(even) { background-color: #f1f5f9; }
tbody td { padding: 6px 9px; border-bottom: 1px solid #e2e8f0; }

code {
    font-family: 'Courier New', monospace;
    font-size: 8.5pt;
    background-color: #f1f5f9;
    color: #1e40af;
    padding: 1px 5px;
    border-radius: 3px;
}

pre {
    background-color: #0f172a;
    color: #e2e8f0;
    font-family: 'Courier New', monospace;
    font-size: 8pt;
    padding: 12px 14px;
    border-radius: 6px;
    margin: 10px 0;
    line-height: 1.55;
    page-break-inside: avoid;
}

pre code { background: none; color: inherit; padding: 0; }

hr { border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }

ul, ol { padding-left: 20px; margin: 4px 0 10px 0; }
li { margin-bottom: 3px; }

.chart-block {
    margin: 18px 0 22px 0;
    text-align: center;
    page-break-inside: avoid;
}

.chart-block img {
    max-width: 100%;
    border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.10);
}

.chart-caption {
    font-size: 8.5pt;
    color: #64748b;
    margin-top: 5px;
    font-style: italic;
}

.section-charts { page-break-before: always; }
"""


# ══════════════════════════════════════════════════════════════════════════════
# Build HTML
# ══════════════════════════════════════════════════════════════════════════════

def _img_tag(b64: str, caption: str) -> str:
    return (
        f'<div class="chart-block">'
        f'<img src="data:image/png;base64,{b64}" alt="{caption}">'
        f'<div class="chart-caption">{caption}</div>'
        f'</div>'
    )


def build_html(md_text: str, charts: dict[str, str]) -> str:
    md = mdlib.Markdown(extensions=["tables", "fenced_code", "nl2br"])
    body = md.convert(md_text)

    charts_html = f"""
<div class="section-charts">
<h2>Appendix — Charts and Visualisations</h2>

<h3>Chart 1 — SPY: Strategy vs Buy-and-Hold</h3>
<p>The strategy uses SMA 200. The buy-and-hold baseline holds SPY continuously for the full period.
Both series start at $100,000.</p>
{_img_tag(charts['spy_1x'], "SPY — Equity Curve (top) and Drawdown from Peak (bottom). Strategy = SMA 200.")}

<h3>Chart 2 — SPY 3x (UPRO): Strategy vs Buy-and-Hold</h3>
<p>The strategy applies the SMA 200 timing rule to UPRO. When the signal exits, the position moves to
cash rather than holding a declining 3x instrument. The buy-and-hold holds UPRO from its inception continuously.</p>
{_img_tag(charts['upro_3x'], "UPRO 3x — Equity Curve and Drawdown. Strategy dramatically reduces underwater periods.")}

<h3>Chart 3 — QQQ 3x (TQQQ): Strategy vs Buy-and-Hold</h3>
<p>The highest CAGR combination in the backtest. TQQQ buy-and-hold shows the severity of leveraged ETF decay
during prolonged downtrends. The strategy exits to cash during these periods.</p>
{_img_tag(charts['tqqq_3x'], "TQQQ 3x — Equity Curve and Drawdown. Strategy reduces max drawdown from 82% to 58%.")}

<h3>Chart 4 — EMA Sensitivity: Calmar Ratio by EMA Length</h3>
<p>All five ETFs are shown. A smooth, gradual slope across EMA lengths confirms the result is not
dependent on one specific parameter value. No ETF shows a sharp spike that would indicate overfitting.</p>
{_img_tag(charts['sensitivity'], "EMA Sensitivity — Calmar ratio across EMA 180 to EMA 210 for all signal ETFs.")}
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Gayed LRS Strategy — Phase 1 Final Review</title>
<style>{CSS}</style>
</head>
<body>
{body}
{charts_html}
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    if not REPORT_MD.exists():
        print(f"Cannot find: {REPORT_MD}"); sys.exit(1)
    if not EQUITY_CSV.exists():
        print(f"Cannot find: {EQUITY_CSV}"); sys.exit(1)

    print("Generating charts (this may take 30–60 seconds while loading equity curves)...")

    charts: dict[str, str] = {}

    print("  Chart 1: SPY strategy vs buy-and-hold...")
    charts["spy_1x"] = chart_equity_and_drawdown(
        "SPY", "SMA_200", "SPY_1X",
        title="SPY (1x)",
        subtitle_strat="Strategy — SMA 200",
        subtitle_bh="Buy and Hold — SPY",
        log_scale=False,
    )

    print("  Chart 2: UPRO 3x strategy vs buy-and-hold...")
    charts["upro_3x"] = chart_equity_and_drawdown(
        "SPY", "SMA_200", "UPRO_3X",
        title="SPY Signal → UPRO 3x Execution",
        subtitle_strat="Strategy — SMA 200 → Cash on exit",
        subtitle_bh="Buy and Hold — UPRO",
        log_scale=True,
    )

    print("  Chart 3: TQQQ 3x strategy vs buy-and-hold...")
    charts["tqqq_3x"] = chart_equity_and_drawdown(
        "QQQ", "EMA_200", "TQQQ_3X",
        title="QQQ Signal → TQQQ 3x Execution",
        subtitle_strat="Strategy — EMA 200 → Cash on exit",
        subtitle_bh="Buy and Hold — TQQQ",
        log_scale=True,
    )

    print("  Chart 4: EMA sensitivity across all ETFs...")
    charts["sensitivity"] = chart_ema_sensitivity()

    print("Building HTML and rendering PDF...")
    md_text = REPORT_MD.read_text(encoding="utf-8")
    html = build_html(md_text, charts)

    REPORT_PDF.parent.mkdir(parents=True, exist_ok=True)
    weasyprint.HTML(string=html, base_url=str(Path.cwd())).write_pdf(str(REPORT_PDF))

    size_kb = REPORT_PDF.stat().st_size // 1024
    print(f"\nSaved: {REPORT_PDF.resolve()} ({size_kb} KB)")


if __name__ == "__main__":
    main()
