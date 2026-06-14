"""
core/tools/scraper.py
---------------------
Async website scraper using httpx + BeautifulSoup.
- Strips script/style/nav/footer noise
- Truncates to MAX_SCRAPED_CHARS to avoid token overflow
- Retries up to MAX_NODE_RETRIES times with exponential back-off
- Returns "" on permanent failure (graceful degradation)
"""
import asyncio
import logging

from config.constants import MAX_NODE_RETRIES, RETRY_BASE_DELAY, MAX_SCRAPED_CHARS

logger = logging.getLogger(__name__)

_SCRAPE_TIMEOUT = 15  # seconds
_NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def scrape_website(url: str) -> str:
    """
    Scrape visible text from *url*.

    Args:
        url: Full URL to scrape (must start with http/https).

    Returns:
        Cleaned, whitespace-normalised text (max MAX_SCRAPED_CHARS).
        Returns "" on failure (never raises).
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError as exc:
        logger.error(f"Missing dependency for scraper: {exc}. pip install httpx beautifulsoup4")
        return ""

    verify_ssl = True
    for attempt in range(MAX_NODE_RETRIES + 1):
        try:
            response_text = None
            try:
                async with httpx.AsyncClient(
                    timeout=_SCRAPE_TIMEOUT,
                    follow_redirects=True,
                    verify=verify_ssl,
                ) as client:
                    response = await client.get(url, headers=_HEADERS)
                    response.raise_for_status()
                    response_text = response.text
            except Exception as exc:
                # Check for SSL/Certificate verification failure
                exc_str = str(exc).lower()
                is_ssl_error = "cert" in exc_str or "ssl" in exc_str
                
                if is_ssl_error and verify_ssl:
                    logger.warning(
                        f"SSL verification failed for {url} ({exc}). "
                        f"Retrying immediately with SSL verification disabled."
                    )
                    verify_ssl = False
                    async with httpx.AsyncClient(
                        timeout=_SCRAPE_TIMEOUT,
                        follow_redirects=True,
                        verify=False,
                    ) as client:
                        response = await client.get(url, headers=_HEADERS)
                        response.raise_for_status()
                        response_text = response.text
                else:
                    raise exc

            soup = BeautifulSoup(response_text, "html.parser")

            # Remove boilerplate / non-content tags
            for tag in soup(_NOISE_TAGS):
                tag.decompose()

            text = soup.get_text(separator=" ", strip=True)
            # Collapse repeated whitespace
            text = " ".join(text.split())

            logger.info(
                f"Scraped {len(text)} chars from {url} "
                f"(truncated to {MAX_SCRAPED_CHARS})"
            )
            return text[:MAX_SCRAPED_CHARS]

        except Exception as exc:
            logger.warning(
                f"Scrape attempt {attempt + 1}/{MAX_NODE_RETRIES + 1} "
                f"failed for {url}: {exc}"
            )
            if attempt == MAX_NODE_RETRIES:
                logger.error(f"Scraper exhausted retries for: {url}")
                return ""
            await asyncio.sleep(RETRY_BASE_DELAY ** attempt)

    return ""
