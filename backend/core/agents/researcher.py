"""
core/agents/researcher.py
--------------------------
ResearcherAgent — handles all data-gathering tasks:
  - plan_research():       LLM-driven research plan from objective
  - search_company():      Tavily multi-query + website scrape
  - search_competitors():  Conditional competitor intelligence gathering
"""
import json
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import settings
from core.tools.web_search import tavily_search
from core.tools.scraper import scrape_website

logger = logging.getLogger(__name__)

_FALLBACK_PLAN_QUERIES = [
    "{company} company overview",
    "{company} products and services",
    "{company} pricing plans",
    "{company} leadership team CEO",
    "{company} latest news 2024 2025",
]


class ResearcherAgent:
    """
    Research agent that combines LLM reasoning with Tavily search and
    web scraping to gather targeted company intelligence.
    """

    def __init__(self) -> None:
        self.llm = ChatAnthropic(
            model=settings.anthropic_model,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=0.2,
            max_tokens=2000,
        )

    # ── Public methods ─────────────────────────────────────────────────────

    async def plan_research(
        self,
        company_name: str,
        website: str,
        objective: str,
    ) -> dict:
        """
        Analyse the research objective and produce a structured research plan.

        Returns a dict:
            focus_areas       : list of research areas to prioritise
            include_competitors: bool
            depth             : "quick" | "standard" | "deep"
            search_queries    : 5–8 targeted Tavily queries
            competitor_queries: 3–5 competitor queries (or [])
            key_questions     : 3–5 questions this research must answer
        """
        system = (
            "You are an expert business research planner. "
            "Analyse the meeting objective and produce a precise, targeted research plan. "
            "Respond with valid JSON only — no markdown fences, no extra text."
        )
        user = f"""Company: {company_name}
Website: {website}
Research Objective: {objective}

Produce a JSON research plan with this exact structure:
{{
  "focus_areas": ["area1", ...],
  "include_competitors": true_or_false,
  "depth": "quick|standard|deep",
  "search_queries": ["query1", "query2", ...],
  "competitor_queries": ["query1", ...],
  "key_questions": ["question1", ...]
}}

Rules:
- focus_areas: pick from [product, pricing, competitors, leadership, funding, news, technology, culture, customers]
- include_competitors: true when objective mentions sales, competitive analysis, or market position
- depth: "deep" for enterprise sales, "standard" for general prep, "quick" for intro calls
- search_queries: 5–8 specific queries targeting the focus_areas (include year for news)
- competitor_queries: 3–5 queries ONLY if include_competitors=true, else []
- key_questions: 3–5 specific questions this research must definitively answer
"""
        try:
            response = await self.llm.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            plan = self._parse_json(response.content)
            logger.info(
                f"Research plan for {company_name}: "
                f"focus={plan.get('focus_areas')}, "
                f"competitors={plan.get('include_competitors')}, "
                f"depth={plan.get('depth')}"
            )
            return plan
        except Exception as exc:
            logger.error(f"plan_research failed: {exc} — using fallback plan")
            return self._fallback_plan(company_name)

    async def search_company(
        self,
        company_name: str,
        queries: list[str],
        website: str,
    ) -> tuple[list[dict], str]:
        """
        Run targeted Tavily searches and scrape the company website.

        Returns:
            (search_results, scraped_content)
            Both gracefully degrade to empty on failure.
        """
        all_results: list[dict] = []

        # Run up to 5 queries to avoid rate limits
        for query in queries[:5]:
            hits = await tavily_search(query, max_results=4)
            all_results.extend(hits)

        # Scrape company website
        scraped = await scrape_website(website)

        # Fallback: website scrape failed → Tavily site search
        if not scraped:
            logger.warning(f"Website scrape failed for {website} — using Tavily fallback")
            fallback = await tavily_search(
                f'"{company_name}" company information products',
                max_results=3,
            )
            scraped = " ".join(r.get("content", "") for r in fallback)

        logger.info(
            f"search_company done: {len(all_results)} results, "
            f"{len(scraped)} chars scraped"
        )
        return all_results, scraped

    async def search_competitors(
        self,
        company_name: str,
        competitor_queries: list[str],
    ) -> dict:
        """
        Gather competitor intelligence.

        Returns a dict with keys: competitors (list), market_summary (str).
        """
        raw_results: list[dict] = []
        for query in competitor_queries[:4]:
            hits = await tavily_search(query, max_results=3)
            raw_results.extend(hits)

        if not raw_results:
            return {"competitors": [], "market_summary": "Competitor data unavailable"}

        # Ask LLM to extract structured competitor info
        combined = "\n".join(
            f"- {r.get('title', '')}: {r.get('content', '')[:250]}"
            for r in raw_results[:8]
        )
        system = (
            "You are a business analyst. Extract competitor info from search results. "
            "JSON only."
        )
        user = f"""Company being researched: {company_name}
Search results:
{combined}

Extract as JSON:
{{
  "competitors": [
    {{
      "name": "Competitor Name",
      "description": "One-line description",
      "key_differentiator": "What sets them apart vs {company_name}"
    }}
  ],
  "market_summary": "Brief competitive landscape overview (2–3 sentences)"
}}"""
        try:
            response = await self.llm.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            result = self._parse_json(response.content)
            logger.info(
                f"Competitor research: {len(result.get('competitors', []))} competitors found"
            )
            return result
        except Exception as exc:
            logger.error(f"search_competitors extraction failed: {exc}")
            return {
                "competitors": [],
                "market_summary": "Competitor extraction failed",
                "raw_snippets": [r.get("title", "") for r in raw_results[:5]],
            }

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Strip markdown fences and parse JSON."""
        text = text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            # parts[1] contains the content after the opening fence
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    @staticmethod
    def _fallback_plan(company_name: str) -> dict:
        return {
            "focus_areas": ["product", "pricing", "leadership", "news"],
            "include_competitors": False,
            "depth": "standard",
            "search_queries": [
                q.format(company=company_name)
                for q in _FALLBACK_PLAN_QUERIES
            ],
            "competitor_queries": [],
            "key_questions": [
                f"What does {company_name} do?",
                f"Who are the key decision makers at {company_name}?",
                f"What is {company_name}'s market position and pricing?",
            ],
        }
