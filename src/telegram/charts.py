"""Financial charts for Telegram — matplotlib, dark theme, PNG output."""

import io
import logging

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
