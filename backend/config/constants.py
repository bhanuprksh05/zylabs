from typing import Final

# ---------------------------------------------------------------------------
# Workflow nodes — in expected execution order
# ---------------------------------------------------------------------------

ALL_WORKFLOW_NODES: Final[list[str]] = [
    "planner",
    "competitor_research",
    "web_research",
    "summarize_content",
    "structured_insights",
    "analyze",
    "quality_check",
    "generate_report",
]

# ---------------------------------------------------------------------------
# Quality control
# ---------------------------------------------------------------------------

QUALITY_THRESHOLD: Final[float] = 0.8   # Minimum score to pass quality check
MAX_QUALITY_RETRIES: Final[int] = 2     # Max analyze → quality_check loops

# ---------------------------------------------------------------------------
# Research limits
# ---------------------------------------------------------------------------

MAX_SEARCH_QUERIES: Final[int] = 5      # Max Tavily queries per search phase
MAX_SEARCH_RESULTS_PER_QUERY: Final[int] = 4
MAX_SCRAPED_CHARS: Final[int] = 8000    # Max chars from website scrape
MAX_SEARCH_RESULTS_FOR_PROMPT: Final[int] = 10  # Max results fed to LLM

# ---------------------------------------------------------------------------
# Retry / back-off
# ---------------------------------------------------------------------------

MAX_NODE_RETRIES: Final[int] = 2        # Max retries for external API calls
RETRY_BASE_DELAY: Final[float] = 1.5   # Base seconds for exponential backoff
