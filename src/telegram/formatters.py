"""Format CrewAI responses for Telegram (message splitting, cleanup).

Includes: message splitting, monospace tables, progress bars, sparklines,
markdown→HTML conversion, structured section builders.
All output uses Telegram HTML parse_mode (<pre>, <b>, <code>).
"""

import html
import re

MAX_LENGTH = 4096


# ── Markdown → Telegram HTML ──────────────────────────────────

def markdown_to_telegram_html(text: str) -> str:
    """Convert markdown text (from CrewAI agents) to Telegram-safe HTML.

    Handles: bold, inline code, code blocks, headers, bullets, quotes, hr.
    """
    if not text:
        return ""

    # 1. HTML-escape first (before any HTML tags are added)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 2. Code blocks: ```...``` → <pre>...</pre>
    def _code_block(m):
        code = m.group(1).strip()
        return f"<pre>{code}</pre>"
    text = re.sub(r"```(?:\w*)\n?(.*?)```", _code_block, text, flags=re.DOTALL)

    # 3. Inline code: `code` → <code>code</code>
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # 4. Bold: **text** → <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # 5. Italic: *text* → <i>text</i> (but not inside <b> tags)
    text = re.sub(r"(?<!\w)\*([^*]+?)\*(?!\w)", r"<i>\1</i>", text)

    # 6. Headers: ### Header → bold + separator
    def _header(m):
        level = len(m.group(1))
        title = m.group(2).strip().upper() if level <= 2 else m.group(2).strip()
        sep = "━" * 20 if level <= 2 else "───"
        return f"\n<b>{title}</b>\n{sep}"
    text = re.sub(r"^(#{1,4})\s+(.+)$", _header, text, flags=re.MULTILINE)

    # 7. Horizontal rules: --- or *** → thick separator
    text = re.sub(r"^[-*]{3,}\s*$", "━━━━━━━━━━━━━━━━━━", text, flags=re.MULTILINE)

    # 8. Blockquotes: > text → <blockquote>text</blockquote>
    def _blockquote(m):
        lines = m.group(0).split("\n")
        cleaned = []
        for line in lines:
            # Remove leading "&gt; " or "&gt;" prefix properly (not char-by-char)
            line = re.sub(r"^&gt;\s?", "", line)
            cleaned.append(line)
        return f"<blockquote>{chr(10).join(cleaned).strip()}</blockquote>"
    text = re.sub(r"(?:^&gt;\s?.+\n?)+", _blockquote, text, flags=re.MULTILINE)

    # 9. Bullets: - item or * item → ▸ item
    text = re.sub(r"^[\-\*]\s+", "▸ ", text, flags=re.MULTILINE)

    # 10. Numbered lists: clean up
    text = re.sub(r"^(\d+)\.\s+", r"\1. ", text, flags=re.MULTILINE)

    # 11. Clean up excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ── Section builders ──────────────────────────────────────────

def section_header(title: str, emoji: str = "") -> str:
    """Build a visual section header with separator.

    Returns: '{emoji} <b>{title}</b>\n━━━━━━━━━━━━━━━━━━'
    """
    prefix = f"{emoji} " if emoji else ""
    return f"{prefix}<b>{html.escape(title)}</b>\n━━━━━━━━━━━━━━━━━━"


def key_value(label: str, value: str, width: int = 20) -> str:
    """Build a key-value line with dot leaders.

    Returns: 'Label ········· <code>Value</code>'
    """
    safe_label = html.escape(label)
    safe_value = html.escape(value)
    dots_count = max(2, width - len(label))
    dots = "·" * dots_count
    return f"▸ {safe_label} {dots} <code>{safe_value}</code>"


def separator(style: str = "thick") -> str:
    """Return a visual separator line.

    style: 'thick' → ━━━━━━━━━━━━━━━━━━ | 'thin' → ──────────────────
    """
    if style == "thin":
        return "──────────────────"
    return "━━━━━━━━━━━━━━━━━━"


def status_indicator(status: str) -> str:
    """Return colored status emoji.

    status: 'ok' → 🟢 | 'warn' → 🟡 | 'error' → 🔴 | 'off' → ⚫
    """
    return {"ok": "🟢", "warn": "🟡", "error": "🔴", "off": "⚫"}.get(status, "⚪")

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

    # Escape all values for HTML safety
    safe_headers = [html.escape(str(h)) for h in headers]
    safe_rows = [[html.escape(str(cell)) for cell in row] for row in rows]

    # Calculate column widths
    widths = [len(h) for h in safe_headers]
    for row in safe_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_cell(val, width, a):
        if a == "r":
            return val.rjust(width)
        elif a == "c":
            return val.center(width)
        return val.ljust(width)

    header_line = " ".join(fmt_cell(h, w, a) for h, w, a in zip(safe_headers, widths, align))
    sep = "─" * len(header_line)

    lines = [header_line, sep]
    for row in safe_rows:
        lines.append(" ".join(fmt_cell(v, w, a) for v, w, a in zip(row, widths, align)))

    return "<pre>" + "\n".join(lines) + "</pre>"


def box_table(headers: list[str], rows: list[list]) -> str:
    """Table with Unicode box-drawing borders, wrapped in <pre>."""
    if not rows:
        return "<pre>(нет данных)</pre>"

    # Escape all values for HTML safety
    safe_headers = [html.escape(str(h)) for h in headers]
    safe_rows = [[html.escape(str(cell)) for cell in row] for row in rows]

    ncols = len(safe_headers)
    widths = [len(h) + 2 for h in safe_headers]
    for row in safe_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell) + 2)

    def make_row(cells):
        return "│" + "│".join(c.center(w) for c, w in zip(cells, widths)) + "│"

    top = "┌" + "┬".join("─" * w for w in widths) + "┐"
    mid = "├" + "┼".join("─" * w for w in widths) + "┤"
    bottom = "└" + "┴".join("─" * w for w in widths) + "┘"

    lines = [top, make_row(safe_headers), mid]
    for row in safe_rows:
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


def _close_open_tags(chunk: str) -> str:
    """Close any HTML tags left open in a chunk to avoid malformed HTML."""
    # Track open tags
    open_tags = []
    for m in re.finditer(r"<(/?)(\w+)[^>]*>", chunk):
        is_close = m.group(1) == "/"
        tag = m.group(2)
        if is_close:
            if open_tags and open_tags[-1] == tag:
                open_tags.pop()
        else:
            open_tags.append(tag)
    # Close remaining open tags in reverse order
    for tag in reversed(open_tags):
        chunk += f"</{tag}>"
    return chunk


def format_for_telegram(text: str, max_length: int = MAX_LENGTH) -> list[str]:
    """Split a long response into Telegram-safe chunks.

    Splits on paragraph boundaries (\\n\\n), then on line boundaries (\\n).
    Each chunk is <= max_length characters. Ensures HTML tags are closed properly.
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

    # Close any open HTML tags in each chunk
    chunks = [_close_open_tags(c) for c in chunks] if chunks else [text[:max_length]]

    return chunks
