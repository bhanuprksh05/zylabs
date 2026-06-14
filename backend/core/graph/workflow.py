"""
core/graph/workflow.py
-----------------------
Builds and compiles the LangGraph StateGraph for the Research Copilot.

Graph topology
--------------
                         ┌─────────────────────────────────────┐
                         │              planner                │
                         └────────────┬───────────┬────────────┘
                   include_competitors│           │ no competitors
                                      ▼           ▼
                         competitor_research   web_research
                                      │           ▲
                                      └───────────┘
                                      ▼
                                  web_research
                                      │
                               summarize_content
                                      │
                              structured_insights
                                      │
                                   analyze
                                      │
                                quality_check
                              ┌───────┴───────┐
                      score≥0.8│               │score<0.8 & retries left
                               ▼               ▼
                        generate_report   ← analyze (retry loop)
                               │
                              END

Exported singleton: `research_graph`
"""
import logging

from langgraph.graph import StateGraph, END

from core.graph.state import ResearchState
from core.graph.nodes import (
    planner_node,
    competitor_research_node,
    web_research_node,
    summarize_content_node,
    structured_insights_node,
    analyze_node,
    quality_check_node,
    generate_report_node,
    route_after_planner,
    route_after_quality_check,
)

logger = logging.getLogger(__name__)


def build_research_graph():
    """
    Assemble and compile the LangGraph research workflow.
    Returns a compiled CompiledGraph ready for .astream() or .ainvoke().
    """
    graph = StateGraph(ResearchState)

    # ── Register nodes ───────────────────────────────────────────────────
    graph.add_node("planner",             planner_node)
    graph.add_node("competitor_research", competitor_research_node)
    graph.add_node("web_research",        web_research_node)
    graph.add_node("summarize_content",   summarize_content_node)
    graph.add_node("structured_insights", structured_insights_node)
    graph.add_node("analyze",             analyze_node)
    graph.add_node("quality_check",       quality_check_node)
    graph.add_node("generate_report",     generate_report_node)

    # ── Entry point ──────────────────────────────────────────────────────
    graph.set_entry_point("planner")

    # ── Conditional: planner → competitor_research OR web_research ───────
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "competitor_research": "competitor_research",
            "web_research":        "web_research",
        },
    )

    # ── competitor_research → web_research (always, when competitor path taken)
    graph.add_edge("competitor_research", "web_research")

    # ── Linear pipeline ──────────────────────────────────────────────────
    graph.add_edge("web_research",        "summarize_content")
    graph.add_edge("summarize_content",   "structured_insights")
    graph.add_edge("structured_insights", "analyze")
    graph.add_edge("analyze",             "quality_check")

    # ── Conditional: quality_check → generate_report OR analyze (retry) ─
    graph.add_conditional_edges(
        "quality_check",
        route_after_quality_check,
        {
            "generate_report": "generate_report",
            "analyze":         "analyze",
        },
    )

    # ── Terminal ─────────────────────────────────────────────────────────
    graph.add_edge("generate_report", END)

    compiled = graph.compile()
    logger.info("Research workflow graph compiled successfully")
    return compiled


# Singleton — import this in the workflow runner
research_graph = build_research_graph()
