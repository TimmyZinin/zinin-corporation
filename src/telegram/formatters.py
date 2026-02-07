"""Format CrewAI responses for Telegram (message splitting, cleanup).

Includes: message splitting, monospace tables, progress bars, sparklines.
All output uses Telegram HTML parse_mode (<pre>, <b>, <code>).
"""

MAX_LENGTH = 4096

# ── Sparklines ──────────────────────────────────────────────

SPARK_BARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float]) -> str:
    """Convert numeric values to Unicode sparkline: ▁▂▃▅▇█▆▃"""
    if not values:
        return ""
    mn, mx = min(values), max(values)
    if mn == mx:
        return SPARK_BARS[4] * len(values)
    extent = mx - mn
    return "".join(
        SPARK_BARS[min(7, int((v - mn) / extent * 7.99))] for v in values
    )


# ── Progress bars ───────────────────────────────────────────

def progress_bar(value: float, total: float, width: int = 15) -> str:
    """Unicode progress bar: ████████░░░░ 67%"""
    ratio = min(value / total, 1.0) if total > 0 else 0
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {ratio:.0%}"


def budget_line(name: str, spent: float, budget: float) -> str:
    """Single budget line with emoji indicator + progress bar."""
    pct = spent / budget if budget > 0 else 0
    icon = "🔴" if pct > 0.9 else "🟡" if pct > 0.7 else "🟢"
    bar = progress_bar(spent, budget, width=12)
    return f"{icon} {name}\n   {bar}  ${spent:,.0f} / ${budget:,.0f}"


# ── Monospace tables ────────────────────────────────────────

def mono_table(headers: list[str], rows: list[list], align: list[str] | None = None) -> str:
    """Format as monospace table wrapped in <pre> for Telegram.

    align: list of 'l', 'r', 'c' per column. Default: first col left, rest right.
    """
    if not rows:
        return "<pre>(нет данных)</pre>"

    ncols = len(headers)
    if align is None:
        align = ["l"] + ["r"] * (ncols - 1)

    # Calculate column widths
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt_cell(val, width, a):
        s = str(val)
        if a == "r":
            return s.rjust(width)
        elif a == "c":
            return s.center(width)
        return s.ljust(width)

    header_line = " ".join(fmt_cell(h, w, a) for h, w, a in zip(headers, widths, align))
    separator = "─" * len(header_line)

    lines = [header_line, separator]
    for row in rows:
        lines.append(" ".join(fmt_cell(v, w, a) for v, w, a in zip(row, widths, align)))

    return "<pre>" + "\n".join(lines) + "</pre>"


def box_table(headers: list[str], rows: list[list]) -> str:
    """Table with Unicode box-drawing borders, wrapped in <pre>."""
    if not rows:
        return "<pre>(нет данных)</pre>"

    ncols = len(headers)
    widths = [len(str(h)) + 2 for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)) + 2)

    def make_row(cells):
        return "│" + "│".join(str(c).center(w) for c, w in zip(cells, widths)) + "│"

    top = "┌" + "┬".join("─" * w for w in widths) + "┐"
    mid = "├" + "┼".join("─" * w for w in widths) + "┤"
    bottom = "└" + "┴".join("─" * w for w in widths) + "┘"

    lines = [top, make_row(headers), mid]
    for row in rows:
        lines.append(make_row(row))
    lines.append(bottom)

    return "<pre>" + "\n".join(lines) + "</pre>"


# ── Financial summary helpers ───────────────────────────────

def format_balance_summary(sources: dict[str, float]) -> str:
    """Format multi-source balance summary with mono table."""
    total = sum(sources.values())
    rows = [[name, f"${val:,.2f}"] for name, val in sorted(sources.items(), key=lambda x: -x[1])]
    rows.append(["ИТОГО", f"${total:,.2f}"])
    return mono_table(["Источник", "Баланс"], rows)


def format_for_telegram(text: str, max_length: int = MAX_LENGTH) -> list[str]:
    """Split a long response into Telegram-safe chunks.

    Splits on paragraph boundaries (\\n\\n), then on line boundaries (\\n).
    Each chunk is <= max_length characters.
    """
    if not text or not text.strip():
        return ["(пустой ответ)"]

    text = text.strip()

    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current = ""

    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 <= max_length:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current)
            if len(para) > max_length:
                # Split oversized paragraph on line boundaries
                current = ""
                for line in para.split("\n"):
                    if len(current) + len(line) + 1 <= max_length:
                        current += ("\n" if current else "") + line
                    else:
                        if current:
                            chunks.append(current)
                        current = line[:max_length]
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks or [text[:max_length]]
