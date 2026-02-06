"""
Web tools for AI Corporation agents.

Tools:
1. WebSearch — search the web via DuckDuckGo (free, no API key)
2. WebPageReader — fetch and extract text from a web page
"""

import json
import logging
import re
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Tool 1: Web Search (DuckDuckGo — бесплатно)
# ──────────────────────────────────────────────────────────

class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query in any language")
    max_results: int = Field(5, description="Number of results (1-10)")


class WebSearchTool(BaseTool):
    name: str = "Web Search"
    description: str = (
        "Search the internet using DuckDuckGo. Free, no API key needed. "
        "Returns titles, URLs, and snippets. Use for finding current information, "
        "documentation, pricing, APIs, news, etc."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, max_results: int = 5) -> str:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return "Error: ddgs not installed. Run: pip install ddgs"

        max_results = min(max(1, max_results), 10)

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return f"No results found for: {query}"

            lines = [f"SEARCH RESULTS for '{query}' ({len(results)} results):"]
            for i, r in enumerate(results, 1):
                lines.append(f"\n{i}. {r.get('title', 'No title')}")
                lines.append(f"   URL: {r.get('href', '')}")
                lines.append(f"   {r.get('body', '')}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Search error: {e}"


# ──────────────────────────────────────────────────────────
# Tool 2: Web Page Reader
# ──────────────────────────────────────────────────────────

class WebPageReaderInput(BaseModel):
    url: str = Field(..., description="URL of the web page to read")
    max_chars: int = Field(3000, description="Max characters to return (default 3000)")


class WebPageReaderTool(BaseTool):
    name: str = "Web Page Reader"
    description: str = (
        "Fetch and read a web page. Extracts main text content. "
        "Use after Web Search to read full articles, documentation, or pages."
    )
    args_schema: Type[BaseModel] = WebPageReaderInput

    def _run(self, url: str, max_chars: int = 3000) -> str:
        from urllib.request import urlopen, Request
        from urllib.error import HTTPError, URLError

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        max_chars = min(max(500, max_chars), 10000)

        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AICorporation/1.0)",
                    "Accept": "text/html,application/xhtml+xml,*/*",
                },
            )
            with urlopen(req, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text" not in content_type and "html" not in content_type:
                    return f"Not a text page (Content-Type: {content_type})"

                html = resp.read().decode("utf-8", errors="replace")

        except HTTPError as e:
            return f"HTTP error {e.code}: {url}"
        except URLError as e:
            return f"URL error: {e.reason}"
        except Exception as e:
            return f"Fetch error: {e}"

        # Extract text using BeautifulSoup if available, else regex fallback
        text = self._extract_text(html)

        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[... truncated]"

        return f"PAGE: {url}\n\n{text}" if text else f"Could not extract text from {url}"

    def _extract_text(self, html: str) -> str:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Remove scripts, styles, nav, footer
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            # Try main content areas first
            main = soup.find("main") or soup.find("article") or soup.find("body")
            if main:
                text = main.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            # Clean up multiple newlines
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()

        except ImportError:
            # Regex fallback without BeautifulSoup
            html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<[^>]+>", "\n", html)
            html = re.sub(r"&nbsp;", " ", html)
            html = re.sub(r"&amp;", "&", html)
            html = re.sub(r"&lt;", "<", html)
            html = re.sub(r"&gt;", ">", html)
            html = re.sub(r"\n{3,}", "\n\n", html)
            return html.strip()
