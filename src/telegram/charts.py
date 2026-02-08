"""Financial charts for Telegram — matplotlib, dark theme, PNG output.

Includes a comprehensive HTML dashboard renderer (html2image + Chromium)
with matplotlib fallback.
"""

import base64
import io
import logging
import os
import tempfile

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

logger = logging.getLogger(__name__)

# Zinin Corp color palette (dark theme, Telegram-friendly)
BG_COLOR = "#1a1a2e"
ACCENT_COLORS = [
    "#4ecca3", "#e94560", "#e7b10a", "#0f3460", "#533483",
    "#00adb5", "#ff6b6b", "#6c5ce7", "#fdcb6e", "#55efc4",
]
TEXT_COLOR = "#e0e0e0"
GRID_COLOR = "#333355"

# Sparkline characters for SVG-free inline rendering
_SPARK = "▁▂▃▄▅▆▇█"


def _setup_style():
    plt.style.use("dark_background")


def portfolio_pie(data: dict[str, float], title: str = "Портфель") -> bytes:
    """Pie chart for portfolio breakdown. Returns PNG bytes."""
    _setup_style()

    # Filter out zero/tiny values
    data = {k: v for k, v in data.items() if v > 0.5}
    if not data:
        return b""

    fig, ax = plt.subplots(figsize=(8, 6), dpi=200)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    labels = list(data.keys())
    values = list(data.values())
    total = sum(values)
    colors = ACCENT_COLORS[: len(labels)]

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct=lambda p: f"${p * total / 100:,.0f}" if p > 3 else "",
        colors=colors,
        textprops={"color": TEXT_COLOR, "fontsize": 11},
        pctdistance=0.75,
        labeldistance=1.12,
        startangle=90,
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_color("#ffffff")

    ax.set_title(f"{title} — ${total:,.0f}", color="white", fontsize=16, pad=20)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def expense_bars(categories: dict[str, float], title: str = "Расходы") -> bytes:
    """Horizontal bar chart for expenses. Returns PNG bytes."""
    _setup_style()

    if not categories:
        return b""

    # Sort by value, take top 10
    sorted_items = sorted(categories.items(), key=lambda x: x[1])[-10:]
    cats = [item[0] for item in sorted_items]
    vals = [item[1] for item in sorted_items]

    fig, ax = plt.subplots(figsize=(8, max(3, len(cats) * 0.55)), dpi=200)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    bars = ax.barh(cats, vals, color="#e94560", height=0.6)

    for bar, val in zip(bars, vals):
        ax.text(
            bar.get_width() + max(vals) * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"${val:,.0f}" if val >= 1 else f"${val:,.2f}",
            va="center", color=TEXT_COLOR, fontsize=10,
        )

    ax.set_title(title, color="white", fontsize=14, pad=15)
    ax.grid(True, axis="x", alpha=0.2, color=GRID_COLOR)
    ax.tick_params(colors="#aaa", labelsize=9)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"${x:,.0f}"))

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def balance_history(dates: list, values: list[float], title: str = "История баланса") -> bytes:
    """Line chart with fill for balance history. Returns PNG bytes."""
    _setup_style()

    if len(dates) < 2:
        return b""

    fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    ax.plot(dates, values, color="#4ecca3", linewidth=2.5)
    ax.fill_between(dates, values, alpha=0.15, color="#4ecca3")

    # Start/end markers
    ax.scatter([dates[0], dates[-1]], [values[0], values[-1]],
               color="#4ecca3", s=60, zorder=5)

    ax.set_title(title, color="white", fontsize=14, pad=15)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax.grid(True, alpha=0.2, color=GRID_COLOR)
    ax.tick_params(colors="#aaa", labelsize=9)
    plt.xticks(rotation=30)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def dashboard(
    portfolio: dict[str, float],
    expenses: dict[str, float] | None = None,
    balance_dates: list | None = None,
    balance_values: list[float] | None = None,
) -> bytes:
    """Composite dashboard: pie + bar + line in one image. Returns PNG bytes."""
    _setup_style()
    import matplotlib.gridspec as gridspec

    has_expenses = expenses and any(v > 0 for v in expenses.values())
    has_history = balance_dates and balance_values and len(balance_dates) >= 2

    if not has_expenses and not has_history:
        return portfolio_pie(portfolio, "Портфель Zinin Corp")

    fig = plt.figure(figsize=(12, 10), dpi=200)
    fig.patch.set_facecolor(BG_COLOR)

    if has_expenses and has_history:
        gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3)
        ax_pie = fig.add_subplot(gs[0, 0])
        ax_bar = fig.add_subplot(gs[0, 1])
        ax_line = fig.add_subplot(gs[1, :])
    elif has_expenses:
        gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.3)
        ax_pie = fig.add_subplot(gs[0, 0])
        ax_bar = fig.add_subplot(gs[0, 1])
        ax_line = None
    else:
        gs = gridspec.GridSpec(2, 1, figure=fig, hspace=0.35)
        ax_pie = fig.add_subplot(gs[0])
        ax_bar = None
        ax_line = fig.add_subplot(gs[1])

    # Pie chart
    p_data = {k: v for k, v in portfolio.items() if v > 0.5}
    if p_data:
        ax_pie.pie(
            p_data.values(), labels=p_data.keys(),
            autopct="%1.0f%%",
            colors=ACCENT_COLORS[: len(p_data)],
            textprops={"color": TEXT_COLOR, "fontsize": 9},
        )
        ax_pie.set_title(f"Портфель — ${sum(p_data.values()):,.0f}",
                         color="white", fontsize=12)

    # Bar chart
    if ax_bar and has_expenses:
        sorted_exp = sorted(expenses.items(), key=lambda x: x[1])[-8:]
        cats = [i[0] for i in sorted_exp]
        vals = [i[1] for i in sorted_exp]
        ax_bar.barh(cats, vals, color="#e94560", height=0.6)
        ax_bar.set_title("Расходы", color="white", fontsize=12)
        ax_bar.tick_params(colors="#aaa", labelsize=8)

    # Line chart
    if ax_line and has_history:
        ax_line.plot(balance_dates, balance_values, color="#4ecca3", linewidth=2)
        ax_line.fill_between(balance_dates, balance_values, alpha=0.15, color="#4ecca3")
        ax_line.set_title("История баланса", color="white", fontsize=12)
        ax_line.tick_params(colors="#aaa", labelsize=8)
        ax_line.grid(True, alpha=0.2, color=GRID_COLOR)

    fig.suptitle("Zinin Corp — Финансовый дашборд", color="white", fontsize=16, y=0.98)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════
# Comprehensive Financial Dashboard (HTML → PNG)
# ═══════════════════════════════════════════════════════════

def _render_donut_b64(sources: dict[str, float], total: float) -> str:
    """Render donut chart as base64 PNG for embedding in HTML."""
    _setup_style()
    fig, ax = plt.subplots(figsize=(3.5, 3.5), dpi=150)
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    data = {k: v for k, v in sources.items() if v > 0.5}
    if not data:
        plt.close(fig)
        return ""

    values = list(data.values())
    colors = ACCENT_COLORS[: len(data)]

    ax.pie(
        values,
        labels=None,
        autopct=None,
        colors=colors,
        startangle=90,
        wedgeprops={"width": 0.35, "edgecolor": BG_COLOR, "linewidth": 2},
    )

    ax.text(0, 0.08, f"${total:,.0f}", ha="center", va="center",
            fontsize=20, fontweight="bold", color="white",
            fontfamily="monospace")
    ax.text(0, -0.18, "TOTAL", ha="center", va="center",
            fontsize=9, color="#888888", fontfamily="monospace")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=True, pad_inches=0.05)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _text_sparkline(values: list[float]) -> str:
    """Unicode sparkline from values."""
    if not values:
        return ""
    mn, mx = min(values), max(values)
    if mn == mx:
        return _SPARK[4] * len(values)
    extent = mx - mn
    return "".join(
        _SPARK[min(7, int((v - mn) / extent * 7.99))] for v in values
    )


def _html_to_png(html: str, width: int = 900, height: int = 700) -> bytes:
    """Render HTML to PNG via headless Chromium subprocess.

    Uses direct subprocess call instead of html2image to avoid
    signal-in-non-main-thread issues with asyncio.to_thread.
    """
    import shutil
    import subprocess

    # Find chromium binary
    chrome_bin = os.environ.get("CHROME_BIN")
    if not chrome_bin:
        for candidate in ["/usr/bin/chromium", "/usr/bin/chromium-browser",
                          "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]:
            if os.path.exists(candidate):
                chrome_bin = candidate
                break
    if not chrome_bin:
        chrome_bin = shutil.which("chromium") or shutil.which("google-chrome")
    if not chrome_bin:
        logger.info("Chromium not found, using matplotlib fallback")
        return b""

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, "dash.html")
            png_path = os.path.join(tmpdir, "dash.png")

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            cmd = [
                chrome_bin,
                "--headless", "--no-sandbox", "--disable-gpu",
                "--disable-software-rasterizer", "--disable-dev-shm-usage",
                "--hide-scrollbars",
                f"--screenshot={png_path}",
                f"--window-size={width},{height}",
                f"file://{html_path}",
            ]
            subprocess.run(cmd, timeout=30, capture_output=True)

            if os.path.exists(png_path):
                with open(png_path, "rb") as f:
                    data = f.read()
                if len(data) > 1000:
                    return data
        return b""
    except subprocess.TimeoutExpired:
        logger.warning("Chromium screenshot timed out (30s)")
        return b""
    except Exception as e:
        logger.warning(f"Chromium screenshot failed: {e}")
        return b""


def _build_source_row(color: str, name: str, usd: float, original: str = "") -> str:
    """Build one row for the source legend."""
    orig_html = (
        f'<span style="color:#666;font-size:12px"> ({original})</span>'
        if original else ""
    )
    return (
        f'<div style="display:flex;align-items:center;padding:4px 0">'
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:2px;background:{color};margin-right:8px"></span>'
        f'<span style="flex:1;color:#ccc;font-size:14px">{name}</span>'
        f'<span style="color:white;font-size:14px;font-weight:600">'
        f'${usd:,.0f}</span>{orig_html}'
        f'</div>'
    )


def _build_dashboard_html(data: dict, donut_b64: str) -> str:
    """Build full HTML dashboard from financial data."""
    # Collect all sources for legend
    rows_html = []
    idx = 0

    # Crypto sources
    crypto = data.get("crypto", {})
    for name, val in sorted(crypto.items(), key=lambda x: -x[1]):
        if val > 0.5:
            color = ACCENT_COLORS[idx % len(ACCENT_COLORS)]
            rows_html.append(_build_source_row(color, name, val))
            idx += 1

    # Fiat sources
    fiat = data.get("fiat", {})
    for name, info in fiat.items():
        color = ACCENT_COLORS[idx % len(ACCENT_COLORS)]
        rows_html.append(_build_source_row(color, name, info["usd"], info.get("original", "")))
        idx += 1

    # Manual sources
    manual = data.get("manual", {})
    for name, info in manual.items():
        color = ACCENT_COLORS[idx % len(ACCENT_COLORS)]
        rows_html.append(_build_source_row(color, name, info["usd"], info.get("original", "")))
        idx += 1

    legend = "\n".join(rows_html)

    # T-Bank section
    tbank_html = ""
    tbank = data.get("tbank_summary")
    if tbank:
        income = tbank.get("income", 0)
        expenses = tbank.get("expenses", 0)
        monthly = tbank.get("monthly", {})

        # Sparkline from monthly data
        spark = ""
        if monthly:
            months_sorted = sorted(monthly.items())[-8:]
            expense_vals = [m[1].get("expenses", 0) for m in months_sorted]
            spark = _text_sparkline(expense_vals)
            month_labels = " ".join(m[0][-5:] for m in months_sorted)

        # Top categories
        top_cats = tbank.get("top_categories", [])[:4]
        cats_html = " &middot; ".join(
            f'<span style="color:#ccc">{cat}</span> '
            f'<span style="color:#e94560">{amt:,.0f}</span>'
            for cat, amt in top_cats
        )

        tbank_html = f'''
        <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:14px 16px;margin-top:12px">
            <div style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">
                T-Bank (RUB)
            </div>
            <div style="display:flex;gap:24px;margin-bottom:8px">
                <div>
                    <span style="color:#4ecca3;font-size:18px;font-weight:700">+{income:,.0f}</span>
                    <span style="color:#666;font-size:12px"> доход</span>
                </div>
                <div>
                    <span style="color:#e94560;font-size:18px;font-weight:700">-{expenses:,.0f}</span>
                    <span style="color:#666;font-size:12px"> расход</span>
                </div>
            </div>
            {"<div style='font-size:20px;letter-spacing:2px;margin-bottom:4px'>" + spark + "</div>" if spark else ""}
            {"<div style='color:#555;font-size:10px;letter-spacing:4px;margin-bottom:8px'>" + month_labels + "</div>" if spark else ""}
            <div style="font-size:12px">{cats_html}</div>
        </div>
        '''

    # Footer
    timestamp = data.get("timestamp", "")
    rates = data.get("rates", {})
    rub_rate = rates.get("RUB")
    footer_rate = f"1 USD = {rub_rate:,.1f} RUB" if rub_rate else ""

    donut_img = (
        f'<img src="data:image/png;base64,{donut_b64}" '
        f'style="width:280px;height:280px" />'
        if donut_b64 else
        '<div style="width:280px;height:280px;display:flex;align-items:center;'
        'justify-content:center;color:#555">No chart data</div>'
    )

    total_usd = data.get("total_usd", 0)

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    background: {BG_COLOR};
    font-family: -apple-system, "Liberation Sans", "Segoe UI", Arial, sans-serif;
    color: white;
    width: 900px;
    padding: 24px;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }}
  .header h1 {{
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #4ecca3;
  }}
  .header .date {{
    color: #666;
    font-size: 13px;
  }}
  .main {{
    display: flex;
    gap: 24px;
    align-items: flex-start;
  }}
  .donut-section {{
    flex-shrink: 0;
  }}
  .legend-section {{
    flex: 1;
    padding-top: 8px;
  }}
  .section-label {{
    color: #888;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 12px 0 6px 0;
  }}
  .section-label:first-child {{ margin-top: 0; }}
  .total-line {{
    font-size: 28px;
    font-weight: 800;
    color: white;
    margin-bottom: 16px;
    font-family: monospace;
  }}
  .footer {{
    display: flex;
    justify-content: space-between;
    margin-top: 16px;
    padding-top: 10px;
    border-top: 1px solid rgba(255,255,255,0.08);
    color: #555;
    font-size: 11px;
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>ZININ CORP</h1>
    <span class="date">{timestamp}</span>
  </div>
  <div class="main">
    <div class="donut-section">
      {donut_img}
    </div>
    <div class="legend-section">
      <div class="total-line">${total_usd:,.0f}</div>
      {"<div class='section-label'>Crypto</div>" if crypto else ""}
      {legend}
    </div>
  </div>
  {tbank_html}
  <div class="footer">
    <span>Обновлено: {timestamp}</span>
    <span>{footer_rate}</span>
  </div>
</body>
</html>'''


def render_financial_dashboard(data: dict) -> bytes:
    """Render comprehensive financial dashboard as PNG.

    Uses HTML+Chromium when available, falls back to matplotlib donut.
    """
    # Merge all sources for donut chart
    all_sources: dict[str, float] = {}
    for name, val in data.get("crypto", {}).items():
        if val > 0.5:
            all_sources[name] = val
    for name, info in data.get("fiat", {}).items():
        all_sources[name] = info["usd"]
    for name, info in data.get("manual", {}).items():
        all_sources[name] = info["usd"]

    total = data.get("total_usd", sum(all_sources.values()))

    if not all_sources:
        return b""

    # Render donut chart as base64
    donut_b64 = _render_donut_b64(all_sources, total)

    # Try HTML dashboard
    html = _build_dashboard_html(data, donut_b64)
    png = _html_to_png(html)
    if png:
        return png

    # Fallback: matplotlib donut chart
    logger.info("Falling back to matplotlib donut chart")
    return _render_donut_fallback(all_sources, total, data)


def _render_donut_fallback(
    sources: dict[str, float], total: float, data: dict
) -> bytes:
    """Fallback: render a nice matplotlib donut with legend."""
    _setup_style()
    import matplotlib.gridspec as gridspec

    fig = plt.figure(figsize=(10, 6), dpi=200)
    fig.patch.set_facecolor(BG_COLOR)

    gs = gridspec.GridSpec(1, 2, figure=fig, width_ratios=[1, 1.2], wspace=0.05)
    ax_donut = fig.add_subplot(gs[0])
    ax_legend = fig.add_subplot(gs[1])

    # Donut
    ax_donut.set_facecolor(BG_COLOR)
    labels = list(sources.keys())
    values = list(sources.values())
    colors = ACCENT_COLORS[: len(labels)]

    wedges, _ = ax_donut.pie(
        values, labels=None, colors=colors, startangle=90,
        wedgeprops={"width": 0.35, "edgecolor": BG_COLOR, "linewidth": 2},
    )
    ax_donut.text(0, 0.08, f"${total:,.0f}", ha="center", va="center",
                  fontsize=22, fontweight="bold", color="white", fontfamily="monospace")
    ax_donut.text(0, -0.18, "TOTAL", ha="center", va="center",
                  fontsize=9, color="#888888")

    # Legend
    ax_legend.axis("off")
    ax_legend.set_xlim(0, 1)
    ax_legend.set_ylim(0, 1)

    y = 0.95
    for i, (name, val) in enumerate(sorted(sources.items(), key=lambda x: -x[1])):
        color = colors[i % len(colors)]
        pct = val / total * 100 if total > 0 else 0

        # Check if this is a fiat/manual source with original currency
        original = ""
        fiat_info = data.get("fiat", {}).get(name)
        manual_info = data.get("manual", {}).get(name)
        if fiat_info:
            original = f" ({fiat_info['original']})"
        elif manual_info:
            original = f" ({manual_info['original']})"

        ax_legend.add_patch(plt.Rectangle((0, y - 0.015), 0.03, 0.025,
                                          facecolor=color, transform=ax_legend.transAxes))
        ax_legend.text(0.05, y, f"{name}{original}", transform=ax_legend.transAxes,
                       fontsize=10, color="#cccccc", va="center")
        ax_legend.text(0.95, y, f"${val:,.0f}  {pct:.0f}%", transform=ax_legend.transAxes,
                       fontsize=10, color="white", va="center", ha="right",
                       fontfamily="monospace")
        y -= 0.065

    # T-Bank section
    tbank = data.get("tbank_summary")
    if tbank and y > 0.2:
        y -= 0.04
        ax_legend.plot([0, 0.95], [y, y], color="#333355",
                       transform=ax_legend.transAxes, linewidth=0.5)
        y -= 0.04
        income = tbank.get("income", 0)
        expenses = tbank.get("expenses", 0)
        ax_legend.text(0, y, "T-Bank:", transform=ax_legend.transAxes,
                       fontsize=9, color="#888888", va="center")
        ax_legend.text(0.25, y, f"+{income:,.0f}", transform=ax_legend.transAxes,
                       fontsize=10, color="#4ecca3", va="center", fontfamily="monospace")
        ax_legend.text(0.60, y, f"-{expenses:,.0f}", transform=ax_legend.transAxes,
                       fontsize=10, color="#e94560", va="center", fontfamily="monospace")
        ax_legend.text(0.85, y, "RUB", transform=ax_legend.transAxes,
                       fontsize=9, color="#666666", va="center")

    fig.suptitle("ZININ CORP", color="#4ecca3", fontsize=14,
                 fontweight="bold", x=0.5, y=0.97)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
