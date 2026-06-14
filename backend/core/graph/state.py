"""
core/graph/state.py
-------------------
ResearchState TypedDict — the single shared state object that flows through
every node of the LangGraph research workflow.

Design notes:
- All fields are optional-safe: nodes only write their own keys.
- `last_completed_node` acts as a checkpoint for resume logic.
- `retry_count` drives the quality-check loop back to analyze.
- `errors` accumulates non-fatal errors for debugging without crashing the run.
"""
from typing import TypedDict


class ResearchState(TypedDict):
    # ── Input (set before graph starts) ──────────────────────────────────
    company_name: str
    website: str
    objective: str
    session_id: str     # str UUID — for logging only; nodes are DB-agnostic
    run_id: str         # str UUID — for logging only

    # ── Planner output ────────────────────────────────────────────────────
    research_plan: dict
    # Expected shape:
    # {
    #   "focus_areas": [...],
    #   "include_competitors": bool,
    #   "depth": "quick|standard|deep",
    #   "search_queries": [...],
    #   "competitor_queries": [...],
    #   "key_questions": [...],
    # }

    # ── Web research data ─────────────────────────────────────────────────
    raw_search_results: list       # List of Tavily result dicts
    scraped_content: str           # Raw text from company website
    competitor_data: dict          # Competitor search results (if applicable)

    # ── Intermediate processing ───────────────────────────────────────────
    content_summary: str           # Compressed summary of raw research
    structured_data: dict          # Extracted typed facts (executives, pricing, etc.)

    # ── Analysis ─────────────────────────────────────────────────────────
    analysis: dict                 # Meeting-ready intelligence

    # ── Quality control ───────────────────────────────────────────────────
    quality_score: float           # 0.0 – 1.0
    quality_issues: list           # Issues identified by quality check
    retry_count: int               # Number of analyze → quality_check retries so far

    # ── Final output ──────────────────────────────────────────────────────
    report: dict                   # Final structured briefing report

    # ── Recoverability ────────────────────────────────────────────────────
    last_completed_node: str       # Checkpoint: name of the last node that finished
    error_count: int               # Total non-fatal errors accumulated
    errors: list                   # Error messages keyed by node name
