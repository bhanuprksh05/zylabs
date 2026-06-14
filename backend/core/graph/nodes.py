"""
core/graph/nodes.py
--------------------
Pure node functions for the LangGraph research workflow.

Design principles:
  - Each function receives the full ResearchState and returns a PARTIAL state update dict.
  - Nodes have NO direct DB access — DB updates happen in the workflow runner.
  - Nodes gracefully handle errors: they log, update the `errors` field, and continue.
  - `last_completed_node` is always set to the current node's name on completion.

Routing functions (not nodes):
  - route_after_planner()       : planner → competitor_research OR web_research
  - route_after_quality_check() : quality_check → generate_report OR analyze (retry)
"""
import logging

from core.graph.state import ResearchState
from core.agents.researcher import ResearcherAgent
from core.agents.summarizer import SummarizerAgent
from config.constants import QUALITY_THRESHOLD, MAX_QUALITY_RETRIES

logger = logging.getLogger(__name__)


# ── Routing functions ────────────────────────────────────────────────────────

def route_after_planner(state: ResearchState) -> str:
    """
    Branch: does the plan require competitor research?
      Yes → "competitor_research"
      No  → "web_research"
    """
    plan = state.get("research_plan", {})
    if plan.get("include_competitors") and plan.get("competitor_queries"):
        logger.info("Route: planner → competitor_research")
        return "competitor_research"
    logger.info("Route: planner → web_research (competitors skipped)")
    return "web_research"


def route_after_quality_check(state: ResearchState) -> str:
    """
    Branch: is the analysis quality sufficient?
      score ≥ QUALITY_THRESHOLD → "generate_report"
      score < QUALITY_THRESHOLD AND retries remaining → "analyze" (loop)
      retries exhausted → "generate_report" (best-effort)
    """
    score = state.get("quality_score", 0.0)
    retries = state.get("retry_count", 0)

    if score >= QUALITY_THRESHOLD:
        logger.info(f"Route: quality_check → generate_report (score={score:.2f} ✓)")
        return "generate_report"

    if retries >= MAX_QUALITY_RETRIES:
        logger.warning(
            f"Route: quality_check → generate_report (max retries={retries} exhausted, "
            f"score={score:.2f})"
        )
        return "generate_report"

    logger.info(
        f"Route: quality_check → analyze (score={score:.2f} < {QUALITY_THRESHOLD}, "
        f"retry {retries}/{MAX_QUALITY_RETRIES})"
    )
    return "analyze"


# ── Node functions ────────────────────────────────────────────────────────────

async def planner_node(state: ResearchState) -> dict:
    """
    PLANNER (Node 1)
    ----------------
    Analyses the research objective and produces a structured research plan
    that drives all downstream decisions (what to search, depth, competitors).
    """
    logger.info(f"[planner] company={state['company_name']}")
    agent = ResearcherAgent()

    plan = await agent.plan_research(
        company_name=state["company_name"],
        website=state["website"],
        objective=state["objective"],
    )

    logger.info(f"[planner] done | focus={plan.get('focus_areas')} depth={plan.get('depth')}")
    return {
        "research_plan": plan,
        "last_completed_node": "planner",
    }


async def competitor_research_node(state: ResearchState) -> dict:
    """
    COMPETITOR RESEARCH (Node 2 — conditional)
    ------------------------------------------
    Only runs when planner sets include_competitors=True.
    Gathers competitor intelligence before the main web research.
    """
    logger.info(f"[competitor_research] company={state['company_name']}")
    agent = ResearcherAgent()

    competitor_data = await agent.search_competitors(
        company_name=state["company_name"],
        competitor_queries=state["research_plan"].get("competitor_queries", []),
    )

    count = len(competitor_data.get("competitors", []))
    logger.info(f"[competitor_research] done | {count} competitors found")
    return {
        "competitor_data": competitor_data,
        "last_completed_node": "competitor_research",
    }


async def web_research_node(state: ResearchState) -> dict:
    """
    WEB RESEARCH (Node 3)
    ----------------------
    Runs targeted Tavily searches and scrapes the company website.
    Gracefully degrades: if all data retrieval fails, continues with empty content.
    """
    logger.info(f"[web_research] company={state['company_name']}")
    agent = ResearcherAgent()

    queries = state["research_plan"].get("search_queries", [
        f"{state['company_name']} company overview",
        f"{state['company_name']} products pricing",
    ])

    search_results, scraped_content = await agent.search_company(
        company_name=state["company_name"],
        queries=queries,
        website=state["website"],
    )

    errors = list(state.get("errors", []))
    error_count = state.get("error_count", 0)

    if not search_results and not scraped_content:
        msg = f"[web_research] No data retrieved for {state['company_name']}"
        logger.warning(msg)
        errors.append(msg)
        error_count += 1

    logger.info(
        f"[web_research] done | {len(search_results)} results, "
        f"{len(scraped_content)} chars scraped"
    )
    return {
        "raw_search_results": search_results,
        "scraped_content": scraped_content,
        "errors": errors,
        "error_count": error_count,
        "last_completed_node": "web_research",
    }


async def summarize_content_node(state: ResearchState) -> dict:
    """
    SUMMARIZE CONTENT (Node 4)
    --------------------------
    Compresses raw search results and scraped website text into a structured,
    focused summary. Bridges raw data → structured extraction.
    """
    logger.info("[summarize_content] compressing raw research")
    agent = SummarizerAgent()

    summary = await agent.summarize(
        raw_search_results=state.get("raw_search_results", []),
        scraped_content=state.get("scraped_content", ""),
        company_name=state["company_name"],
        research_plan=state.get("research_plan", {}),
    )

    logger.info(f"[summarize_content] done | {len(summary)} chars")
    return {
        "content_summary": summary,
        "last_completed_node": "summarize_content",
    }


async def structured_insights_node(state: ResearchState) -> dict:
    """
    STRUCTURED INSIGHTS (Node 5)
    -----------------------------
    Extracts typed, structured facts from the summary:
    executives, products, pricing, funding, tech, competitors.
    Produces a clean JSON object consumed by the analysis stage.
    """
    logger.info("[structured_insights] extracting structured facts")
    agent = SummarizerAgent()

    structured_data = await agent.extract_structured_insights(
        content_summary=state.get("content_summary", ""),
        company_name=state["company_name"],
        scraped_content=state.get("scraped_content", ""),
        competitor_data=state.get("competitor_data", {}),
    )

    logger.info(f"[structured_insights] done | {len(structured_data)} categories")
    return {
        "structured_data": structured_data,
        "last_completed_node": "structured_insights",
    }


async def analyze_node(state: ResearchState) -> dict:
    """
    ANALYZE (Node 6)
    ----------------
    Synthesises all gathered research into meeting-ready intelligence:
    talking points, pain points, opportunities, stakeholder intel, agenda.
    On retry (quality_issues present), addresses specific gaps identified.
    """
    retry_num = state.get("retry_count", 0)
    logger.info(f"[analyze] attempt={retry_num + 1} company={state['company_name']}")
    agent = SummarizerAgent()

    analysis = await agent.analyze(
        company_name=state["company_name"],
        objective=state["objective"],
        content_summary=state.get("content_summary", ""),
        structured_data=state.get("structured_data", {}),
        research_plan=state.get("research_plan", {}),
        quality_issues=state.get("quality_issues", []),
        retry_count=retry_num,
    )

    logger.info("[analyze] done")
    return {
        "analysis": analysis,
        "last_completed_node": "analyze",
    }


async def quality_check_node(state: ResearchState) -> dict:
    """
    QUALITY CHECK (Node 7)
    -----------------------
    Validates the analysis on 5 criteria (0.2 each → max 1.0).
    Identifies specific gaps and decides whether to pass or retry.
    retry_count is incremented only when a retry is warranted.
    """
    logger.info("[quality_check] validating analysis quality")
    agent = SummarizerAgent()

    score, issues = await agent.check_quality(
        analysis=state.get("analysis", {}),
        objective=state["objective"],
        structured_data=state.get("structured_data", {}),
    )

    current_retry = state.get("retry_count", 0)
    # Increment retry_count only if we're going to loop back
    new_retry = (
        current_retry + 1
        if score < QUALITY_THRESHOLD and current_retry < MAX_QUALITY_RETRIES
        else current_retry
    )

    logger.info(
        f"[quality_check] done | score={score:.2f}, issues={len(issues)}, "
        f"retry={current_retry}→{new_retry}"
    )
    return {
        "quality_score": score,
        "quality_issues": issues,
        "retry_count": new_retry,
        "last_completed_node": "quality_check",
    }


async def generate_report_node(state: ResearchState) -> dict:
    """
    GENERATE REPORT (Node 8 — terminal)
    ------------------------------------
    Produces the final structured research briefing report.
    Combines all state data into a comprehensive, professional output.
    On LLM failure, falls back to assembling the report from existing state.
    """
    logger.info(f"[generate_report] company={state['company_name']}")
    agent = SummarizerAgent()

    report = await agent.generate_report(
        company_name=state["company_name"],
        website=state["website"],
        objective=state["objective"],
        research_plan=state.get("research_plan", {}),
        structured_data=state.get("structured_data", {}),
        analysis=state.get("analysis", {}),
        quality_score=state.get("quality_score", 0.0),
    )

    logger.info(f"[generate_report] done | {len(str(report))} chars")
    return {
        "report": report,
        "last_completed_node": "generate_report",
    }
