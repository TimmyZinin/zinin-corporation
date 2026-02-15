"""Post-processing for Алексей (CEO) responses — compact, visual, result-focused.

Strips verbose tool-usage descriptions, trims to max length,
and adds visual structure where possible.
"""

import re

# Max response length for Alexey (characters). Full reports bypass this.
MAX_RESPONSE_LEN = 1500

# Patterns that indicate verbose tool-usage descriptions to strip
_TOOL_NOISE_PATTERNS = [
    # "Я использовал инструмент X" / "I used the tool X"
    re.compile(
        r"^[\-\*▸]?\s*(?:Я\s+)?(?:использовал[аоы]?|применил[аоы]?|вызвал[аоы]?|задействовал[аоы]?)"
        r"\s+(?:инструмент|tool)\s+.{3,80}[.:]?\s*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # "Image Generation:" / "1. Image Generation:" block headers about tools
    re.compile(
        r"^\d+\.\s*(?:Image Generation|Video Creation|Chart Generator|Content Generator"
        r"|Infographic Builder|Visual Analyzer|Design System|Brand Voice|Image Enhancer"
        r"|Image Resizer|Telegraph Publisher|Podcast Script)\s*:?\s*$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # "- Использовал photorealistic стиль для..." (sub-bullets about process)
    re.compile(
        r"^[\-\*▸]\s+(?:Использовал[аоы]?|Применил[аоы]?|Сгенерировал[аоы]?|Создал[аоы]?)\s+"
        r"(?:photorealistic|minimalist|flat|isometric|3D|cartoon)\s+стиль\s+.{0,100}$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # "- Prompt: "..." lines (tool prompt dumps)
    re.compile(
        r'^[\-\*▸]\s+Prompt:\s*["\u201c].{10,}["\u201d]\s*$',
        re.MULTILINE | re.IGNORECASE,
    ),
    # "Для максимальной достоверности / Для наилучшего результата" filler
    re.compile(
        r"^[\-\*▸]\s+(?:Для\s+(?:максимальной|наилучшего)|Чтобы\s+обеспечить)\s+.{10,80}$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # "Используя несколько инструментов" opener
    re.compile(
        r"^.*(?:используя\s+несколько\s+инструментов|using\s+several\s+tools).*$",
        re.MULTILINE | re.IGNORECASE,
    ),
]

# Full blocks to collapse (multiline): numbered lists describing process steps
_PROCESS_BLOCK_RE = re.compile(
    r"(?:^(?:\d+\.\s+(?:Image|Video|Chart|Content|Visual|Design|Infographic)\s+\w+.*\n)"
    r"(?:[\-\*▸]\s+.*\n)*)+",
    re.MULTILINE | re.IGNORECASE,
)


def strip_tool_noise(text: str) -> str:
    """Remove verbose tool-usage descriptions from agent response."""
    for pattern in _TOOL_NOISE_PATTERNS:
        text = pattern.sub("", text)

    # Collapse process blocks (numbered tool steps with sub-bullets)
    text = _PROCESS_BLOCK_RE.sub("", text)

    # Clean up resulting empty lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_response(text: str, max_len: int = MAX_RESPONSE_LEN) -> str:
    """Truncate response to max_len, cutting at paragraph boundary.

    Does NOT truncate if text contains report markers (tables, code blocks, etc.)
    """
    if len(text) <= max_len:
        return text

    # Don't truncate structured content (reports, tables, code)
    report_markers = ["<pre>", "━━━", "───", "┌─", "│", "▸ "]
    if any(marker in text for marker in report_markers):
        return text

    # Find a good cut point (paragraph or sentence boundary)
    cut = text[:max_len].rfind("\n\n")
    if cut < max_len * 0.5:
        cut = text[:max_len].rfind("\n")
    if cut < max_len * 0.3:
        cut = text[:max_len].rfind(". ")
        if cut > 0:
            cut += 1  # include the period
    if cut < max_len * 0.3:
        cut = max_len

    return text[:cut].rstrip()


def compress_ceo_response(text: str) -> str:
    """Full post-processing pipeline for Алексей's responses.

    1. Strip tool-noise patterns
    2. Truncate if too long (preserving reports/tables)
    """
    text = strip_tool_noise(text)
    text = truncate_response(text)
    return text
