"""Format CrewAI responses for Telegram (message splitting, cleanup)."""

MAX_LENGTH = 4096


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
