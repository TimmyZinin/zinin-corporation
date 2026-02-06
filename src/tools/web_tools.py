"""
Web tools for AI Corporation agents.

Tools:
1. WebSearch — search the internet via DuckDuckGo (free, no API key)
2. WebScrape — read/scrape any URL content
"""

import json
import logging
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Tool 1: Web Search (DuckDuckGo)
# ──────────────────────────────────────────────────────────

class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query in any language")
    max_results: int = Field(
        5,
        description="Number of results to return (1-10, default 5)",
    )


class WebSearchTool(BaseTool):
    name: str = "Web Search"
    description: str = (
        "Search the internet using DuckDuckGo. Free, no API key needed. "
        "Returns titles, URLs, and snippets. Use for finding information, "
        "researching services, APIs, prices, documentation, news."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, max_results: int = 5) -> str:
        try:
            from ddgs import DDGS

            max_results = min(max(1, max_results), 10)
            results = DDGS().text(query, max_results=max_results)

            if not results:
                return f"No results found for: {query}"

            lines = [f"SEARCH RESULTS for '{query}':"]
            for i, r in enumerate(results, 1):
                lines.append(f"\n{i}. {r.get('title', 'No title')}")
                lines.append(f"   URL: {r.get('href', '')}")
                lines.append(f"   {r.get('body', '')}")

            return "\n".join(lines)

        except ImportError:
            return "Error: ddgs package not installed. Run: pip install ddgs"
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Search error: {e}"


# ──────────────────────────────────────────────────────────
# Tool 2: Web Scrape (read URL content)
# ──────────────────────────────────────────────────────────

class WebScrapeInput(BaseModel):
    url: str = Field(..., description="URL to scrape/read")


class WebScrapeTool(BaseTool):
    name: str = "Web Scrape"
    description: str = (
        "Read and extract text content from any URL. "
        "Use after Web Search to read full articles, documentation, "
        "API docs, pricing pages, etc."
    )
    args_schema: Type[BaseModel] = WebScrapeInput

    def _run(self, url: str) -> str:
        try:
            from crewai_tools import ScrapeWebsiteTool

            scraper = ScrapeWebsiteTool()
            result = scraper.run(website_url=url)

            if not result:
                return f"Could not read content from: {url}"

            # Truncate if too long
            text = str(result)
            if len(text) > 8000:
                text = text[:8000] + "\n\n... [content truncated at 8000 chars]"

            return f"CONTENT FROM {url}:\n\n{text}"

        except Exception as e:
            logger.error(f"Web scrape failed: {e}")
            return f"Scrape error for {url}: {e}"
