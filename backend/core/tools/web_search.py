"""
core/tools/web_search.py
------------------------
Tavily search wrapper with automatic exponential-backoff retry.
Returns an empty list on permanent failure (graceful degradation).
"""
import asyncio
import logging
from typing import Optional

from config.constants import MAX_NODE_RETRIES, RETRY_BASE_DELAY, MAX_SEARCH_RESULTS_PER_QUERY

logger = logging.getLogger(__name__)


async def tavily_search(
    query: str,
    max_results: int = MAX_SEARCH_RESULTS_PER_QUERY,
    search_depth: str = "advanced",
) -> list[dict]:
    """
    Search via Tavily API.

    Args:
        query:        The search query string.
        max_results:  How many results to return per query.
        search_depth: "basic" or "advanced".

    Returns:
        List of result dicts with keys: title, url, content, score.
        Returns [] on failure (never raises).
    """
    # Import lazily so missing key doesn't crash app startup
    try:
        from tavily import AsyncTavilyClient
    except ImportError:
        logger.error("tavily-python not installed. Run: pip install tavily-python")
        return []

    from config.settings import settings

    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY not configured — skipping web search")
        return []

    client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    for attempt in range(MAX_NODE_RETRIES + 1):
        try:
            response = await client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
            )
            results = response.get("results", [])
            logger.info(
                f"Tavily search OK: {len(results)} results for '{query[:60]}'"
            )
            return results

        except Exception as exc:
            logger.warning(
                f"Tavily attempt {attempt + 1}/{MAX_NODE_RETRIES + 1} failed "
                f"for '{query[:60]}': {exc}"
            )
            if attempt == MAX_NODE_RETRIES:
                logger.error(f"Tavily exhausted retries for: '{query[:60]}'")
                return []
            await asyncio.sleep(RETRY_BASE_DELAY ** attempt)

    return []
