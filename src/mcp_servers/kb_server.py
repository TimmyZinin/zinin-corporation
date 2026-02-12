"""
Knowledge Base MCP Server — search and read knowledge/ files.

Provides simple text search across the corporation's knowledge base
files (company info, team, content guidelines).

Run: python run_kb_mcp.py
"""

import logging
import os

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "kb-mcp",
    instructions="Knowledge Base for Zinin Corporation — search company docs, team info, guidelines",
)

# Knowledge base directory (relative paths for different envs)
_KB_DIRS = ["/app/knowledge", "knowledge"]


def _kb_dir() -> str:
    for d in _KB_DIRS:
        if os.path.isdir(d):
            return d
    return "knowledge"


def _list_kb_files() -> list[str]:
    """List all .md files in knowledge directory."""
    kb = _kb_dir()
    if not os.path.isdir(kb):
        return []
    return sorted(f for f in os.listdir(kb) if f.endswith(".md"))


@mcp.tool()
def kb_search(query: str) -> str:
    """Search across all knowledge base files for a query string.

    Args:
        query: Search term (case-insensitive substring match)
    """
    kb = _kb_dir()
    if not os.path.isdir(kb):
        return "Knowledge base directory not found."

    query_lower = query.lower()
    results = []

    for filename in _list_kb_files():
        filepath = os.path.join(kb, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        lines = content.split("\n")
        matches = []
        for i, line in enumerate(lines, 1):
            if query_lower in line.lower():
                # Show context: line before, match, line after
                start = max(0, i - 2)
                end = min(len(lines), i + 1)
                context = "\n".join(lines[start:end])
                matches.append(f"  Line {i}: {context.strip()}")

        if matches:
            results.append(f"📄 {filename} ({len(matches)} matches):\n" + "\n".join(matches[:5]))

    if not results:
        return f"No matches for '{query}' in knowledge base."

    return "\n\n".join(results)


@mcp.tool()
def kb_list_topics() -> str:
    """List all available knowledge base files with descriptions."""
    files = _list_kb_files()
    if not files:
        return "Knowledge base is empty."

    kb = _kb_dir()
    lines = ["📚 Knowledge Base Topics:\n"]
    for filename in files:
        filepath = os.path.join(kb, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                first_line = f.readline().strip().lstrip("#").strip()
            size = os.path.getsize(filepath)
            lines.append(f"  📄 {filename} — {first_line} ({size} bytes)")
        except Exception:
            lines.append(f"  📄 {filename}")

    return "\n".join(lines)


@mcp.tool()
def kb_read_topic(filename: str) -> str:
    """Read the full content of a knowledge base file.

    Args:
        filename: File name (e.g. "company.md", "team.md", "content_guidelines.md")
    """
    kb = _kb_dir()
    # Security: prevent path traversal
    safe_name = os.path.basename(filename)
    filepath = os.path.join(kb, safe_name)

    if not os.path.exists(filepath):
        available = ", ".join(_list_kb_files())
        return f"File '{safe_name}' not found. Available: {available}"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # Truncate very large files
        if len(content) > 10000:
            content = content[:10000] + "\n\n... (truncated)"
        return content
    except Exception as e:
        return f"Error reading {safe_name}: {e}"
