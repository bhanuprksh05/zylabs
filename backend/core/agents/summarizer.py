"""
core/agents/summarizer.py
--------------------------
SummarizerAgent — handles all synthesis, extraction, quality-checking, and
report-generation tasks using Anthropic Claude.

Methods:
  summarize()                  Raw research → concise bullet-point summary
  extract_structured_insights()  Summary → typed structured facts
  analyze()                    All data → meeting-ready intelligence
  check_quality()              Analysis → (score, issues)
  generate_report()            All state → final structured briefing
"""
import json
import logging
from typing import List, Optional

from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import settings
from config.constants import QUALITY_THRESHOLD, MAX_QUALITY_RETRIES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured Report Schema Models
# ---------------------------------------------------------------------------

class CompanyOverview(BaseModel):
    description: str = Field(description="A brief description of the company, its mission, and history.")
    industry: str = Field(description="The primary industry the company operates in.")
    size: str = Field(description="Approximate employee headcount or company size.")
    founded: str = Field(description="Year founded.")
    headquarters: str = Field(description="City and state/country.")
    business_model: str = Field(description="B2B, B2C, Marketplace, SaaS, etc.")

class ProductService(BaseModel):
    name: str = Field(description="Name of the product or service.")
    description: str = Field(description="Brief description of the product or service.")

class BusinessSignal(BaseModel):
    category: str = Field(description="Category of signal, e.g., Hiring, Funding, Expansion, Product Launch.")
    signal: str = Field(description="The specific signal or trend identified.")
    significance: str = Field(description="Why this signal is important.")

class SourceInfo(BaseModel):
    title: str = Field(description="Title or description of the source.")
    url: Optional[str] = Field(None, description="URL of the source.")

class SalesBriefingReport(BaseModel):
    company_overview: CompanyOverview = Field(description="Overview of the company.")
    products_services: List[ProductService] = Field(description="Key products and services offered.")
    target_customers: List[str] = Field(description="Identified target customers, buyer personas, or ideal customer profiles (ICP).")
    business_signals: List[BusinessSignal] = Field(description="Recent business signals, triggers, news, or indicators.")
    risks_challenges: List[str] = Field(description="Risks and challenges the company faces in their market or operationally.")
    suggested_discovery_questions: List[str] = Field(description="Suggested questions to ask during the sales discovery call.")
    suggested_outreach_strategy: List[str] = Field(description="Recommended outreach strategy, value propositions, or messaging angles.")
    unknowns: List[str] = Field(description="Areas where information was missing or unclear during research.")
    sources: List[SourceInfo] = Field(description="List of sources, websites, or search references utilized.")


class SummarizerAgent:
    """
    Synthesis and briefing-generation agent.
    Uses a main LLM for long-form tasks and a fast LLM for quality checks.
    """

    def __init__(self) -> None:
        self.llm = ChatAnthropic(
            model=settings.anthropic_model,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=0.2,
            max_tokens=3000,
        )
        # Slightly faster / cheaper model for the quality-check step
        self.fast_llm = ChatAnthropic(
            model=settings.anthropic_model,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=0.1,
            max_tokens=1500,
        )

    # ── Public methods ─────────────────────────────────────────────────────

    async def summarize(
        self,
        raw_search_results: list[dict],
        scraped_content: str,
        company_name: str,
        research_plan: dict,
    ) -> str:
        """Compress raw research into a focused, structured text summary."""
        search_text = "\n".join(
            f"[{r.get('title', 'No title')}]\n{r.get('content', '')[:300]}"
            for r in raw_search_results[:10]
        )
        focus = ", ".join(research_plan.get("focus_areas", ["general"]))
        questions = "\n".join(
            f"- {q}" for q in research_plan.get("key_questions", [])
        )

        system = (
            "You are a senior business analyst. Summarise research into concise, "
            "factual bullet points. Focus only on information relevant to the specified "
            "research areas. Be specific — no vague statements."
        )
        user = f"""Company: {company_name}
Research Focus: {focus}
Key Questions to Answer:
{questions}

WEBSITE CONTENT:
{scraped_content[:3000] or "Not available"}

SEARCH RESULTS:
{search_text}

Produce a structured summary with:
1. Company Overview (2–3 sentences of hard facts)
2. Key Facts (bullet points per focus area)
3. Direct Answers to Key Questions (state "Not found" if missing)
4. Notable Gaps (what information could not be found)

Be factual. Never invent information."""

        try:
            response = await self.llm.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            summary = response.content.strip()
            logger.info(f"Content summarised: {len(summary)} chars")
            return summary
        except Exception as exc:
            logger.error(f"summarize() failed: {exc}")
            return f"Summary generation failed for {company_name}. Raw data is available."

    async def extract_structured_insights(
        self,
        content_summary: str,
        company_name: str,
        scraped_content: str,
        competitor_data: dict,
    ) -> dict:
        """Extract structured, typed facts from the summary."""
        competitor_json = json.dumps(
            competitor_data.get("competitors", [])[:3], indent=2
        )

        system = (
            "You are a business intelligence analyst. Extract structured facts "
            "from research. JSON only — no markdown, no commentary."
        )
        user = f"""Company: {company_name}

RESEARCH SUMMARY:
{content_summary}

WEBSITE EXCERPT (first 1000 chars):
{scraped_content[:1000] or "N/A"}

COMPETITOR DATA:
{competitor_json or "[]"}

Extract as JSON (use "Unknown" / [] for missing data — NEVER fabricate facts):
{{
  "company_overview": {{
    "description": "1–2 sentence company description",
    "industry": "...",
    "company_size": "startup|SMB|mid-market|enterprise or headcount",
    "founded": "Year or Unknown",
    "headquarters": "City, Country or Unknown",
    "business_model": "B2B|B2C|B2B2C|marketplace|other"
  }},
  "products_services": [
    {{
      "name": "Product/Service name",
      "description": "Brief description",
      "target_customer": "Who buys this"
    }}
  ],
  "pricing": {{
    "model": "subscription|usage-based|freemium|custom|unknown",
    "tiers": ["tier1 name", "tier2 name"],
    "signals": "Any pricing signals found (e.g. 'starts at $X/month')"
  }},
  "leadership": [
    {{
      "name": "Full Name",
      "title": "Title",
      "background": "Notable background (1 sentence)"
    }}
  ],
  "recent_news": [
    {{
      "headline": "News headline",
      "date": "Date or 'Recent'",
      "significance": "Why this matters for the meeting"
    }}
  ],
  "funding_status": {{
    "stage": "bootstrapped|seed|series-a|series-b|series-c|public|unknown",
    "total_raised": "Amount or Unknown",
    "investors": ["Investor 1", "Investor 2"]
  }},
  "technology": {{
    "tech_stack": ["tech1", "tech2"],
    "integrations": ["integration1"],
    "technical_signals": "Any notable tech signals"
  }},
  "competitors": {competitor_json}
}}"""
        try:
            response = await self.llm.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            data = self._parse_json(response.content)
            logger.info(f"Structured insights extracted: {len(data)} categories")
            return data
        except Exception as exc:
            logger.error(f"extract_structured_insights() failed: {exc}")
            return {
                "company_overview": {"description": company_name, "industry": "Unknown"},
                "products_services": [],
                "pricing": {"model": "unknown"},
                "leadership": [],
                "recent_news": [],
                "funding_status": {"stage": "unknown"},
                "technology": {"tech_stack": []},
                "competitors": [],
            }

    async def analyze(
        self,
        company_name: str,
        objective: str,
        content_summary: str,
        structured_data: dict,
        research_plan: dict,
        quality_issues: list,
        retry_count: int,
    ) -> dict:
        """Synthesise all research into actionable meeting intelligence."""
        improvement_block = ""
        if quality_issues and retry_count > 0:
            issues_text = "\n".join(f"  - {i}" for i in quality_issues)
            improvement_block = f"""
⚠️  QUALITY ISSUES FROM PREVIOUS ATTEMPT (Retry {retry_count}/{MAX_QUALITY_RETRIES}):
{issues_text}
Please specifically address each issue in this revised analysis.
"""
        focus = ", ".join(research_plan.get("focus_areas", []))
        structured_json = json.dumps(structured_data, indent=2)

        if len(structured_json) > 3000:
            structured_json = structured_json[:3000] + "... (truncated)"

        system = (
            "You are a senior sales intelligence analyst preparing a meeting briefing. "
            "Synthesise research into specific, actionable meeting intelligence. "
            "Be concrete — avoid generic advice. JSON only."
        )
        user = f"""Company: {company_name}
Meeting Objective: {objective}
Research Focus Areas: {focus}

RESEARCH SUMMARY:
{content_summary}

STRUCTURED DATA:
{structured_json}
{improvement_block}

Produce a comprehensive meeting intelligence JSON:
{{
  "executive_summary": "2–3 sentence briefing for a busy executive (objective-specific, not generic)",
  "company_snapshot": {{
    "what_they_do": "Clear explanation of core business value prop",
    "market_position": "Where they sit relative to competitors",
    "growth_stage": "Current stage and trajectory"
  }},
  "meeting_intelligence": {{
    "key_talking_points": [
      {{
        "topic": "Topic name",
        "talking_point": "Specific point to raise",
        "rationale": "Why this resonates with them specifically"
      }}
    ],
    "pain_points": [
      {{
        "pain": "Specific pain point",
        "evidence": "What in the research led to this conclusion",
        "our_angle": "How to frame your solution around this pain"
      }}
    ],
    "opportunities": [
      {{
        "opportunity": "Specific business opportunity",
        "timing": "Why now is the right time",
        "approach": "Suggested approach to raise it"
      }}
    ]
  }},
  "stakeholder_intel": {{
    "key_contacts": [
      {{
        "name": "Name (if known)",
        "title": "Title",
        "likely_concerns": "What they typically care about in this role",
        "conversation_starter": "Specific opener for this person"
      }}
    ],
    "decision_maker": "Who likely has budget authority"
  }},
  "competitive_context": {{
    "our_differentiation": "How to differentiate from their current/alternative solutions",
    "risks": ["Competitive or deal risk 1", "Risk 2"],
    "competitor_mentions": "Any relevant competitor data points"
  }},
  "suggested_agenda": [
    "Agenda item 1 (with time estimate)",
    "Agenda item 2",
    "Agenda item 3"
  ],
  "questions_to_ask": [
    "Specific discovery question 1",
    "Specific discovery question 2",
    "Specific discovery question 3"
  ],
  "red_flags": ["Any concerns or risks about this prospect or meeting"]
}}

Must be specific and actionable. Generic talking points are unacceptable."""

        try:
            response = await self.llm.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            analysis = self._parse_json(response.content)
            logger.info(f"Analysis complete for {company_name}")
            return analysis
        except Exception as exc:
            logger.error(f"analyze() failed: {exc}")
            return {
                "executive_summary": f"Analysis for {company_name} (generation error)",
                "meeting_intelligence": {
                    "key_talking_points": [],
                    "pain_points": [],
                    "opportunities": [],
                },
                "suggested_agenda": [],
                "questions_to_ask": [],
                "red_flags": [f"Analysis generation error: {exc}"],
            }

    async def check_quality(
        self,
        analysis: dict,
        objective: str,
        structured_data: dict,
    ) -> tuple[float, list[str]]:
        """
        Score the quality of the analysis on a 0.0–1.0 scale.

        Returns:
            (quality_score, issues): Score and list of specific improvement requests.
        """
        data_availability = {
            "leadership": bool(structured_data.get("leadership")),
            "products": bool(structured_data.get("products_services")),
            "pricing_known": structured_data.get("pricing", {}).get("model") != "unknown",
            "recent_news": bool(structured_data.get("recent_news")),
            "competitors": bool(structured_data.get("competitors")),
        }

        system = (
            "You are a QA reviewer for business intelligence reports. "
            "Be strict — generic content scores low. JSON only."
        )
        user = f"""Objective: {objective}

ANALYSIS TO REVIEW:
{json.dumps(analysis, indent=2)[:3000]}

DATA AVAILABILITY:
{json.dumps(data_availability, indent=2)}

Score on 5 criteria (each 0.0–0.2):
1. executive_summary: Objective-specific and concrete (not generic)
2. talking_points: At least 2 points with specific rationale
3. pain_points: At least 1 pain with evidence from research
4. discovery_questions: At least 2 specific, non-generic questions
5. meeting_agenda: At least 2 agenda items with context

Respond:
{{
  "quality_score": 0.0-1.0,
  "criteria_scores": {{
    "executive_summary": 0.0-0.2,
    "talking_points": 0.0-0.2,
    "pain_points": 0.0-0.2,
    "discovery_questions": 0.0-0.2,
    "meeting_agenda": 0.0-0.2
  }},
  "issues": ["Specific actionable issue 1", "Issue 2"],
  "strengths": ["What is done well"]
}}"""
        try:
            response = await self.fast_llm.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            result = self._parse_json(response.content)
            score = float(result.get("quality_score", 0.5))
            issues = result.get("issues", [])
            logger.info(f"Quality check: score={score:.2f}, issues={len(issues)}")
            return score, issues
        except Exception as exc:
            logger.error(f"check_quality() failed: {exc} — defaulting to pass")
            # Default to pass on error to avoid infinite loop
            return QUALITY_THRESHOLD, []

    async def generate_report(
        self,
        company_name: str,
        website: str,
        objective: str,
        research_plan: dict,
        structured_data: dict,
        analysis: dict,
        quality_score: float,
    ) -> dict:
        """Generate the final structured research briefing report conforming to SalesBriefingReport."""
        structured_json = json.dumps(structured_data, indent=2)[:3000]
        analysis_json = json.dumps(analysis, indent=2)[:4000]

        system = (
            "You are a senior sales intelligence analyst preparing a final sales meeting briefing report. "
            "Synthesize all research and structured intelligence data into the requested structured output. "
            "Focus on actionable items relevant to the meeting objective. Do not invent any facts; "
            "if information is missing, list it in 'unknowns' and use 'Not available' or empty fields where appropriate."
        )

        user = f"""Company: {company_name}
Website: {website}
Meeting Objective: {objective}

STRUCTURED INTELLIGENCE DATA gathered so far:
{structured_json}

ANALYSIS & MEETING INTEL:
{analysis_json}
"""
        try:
            structured_llm = self.llm.with_structured_output(SalesBriefingReport)
            response = await structured_llm.ainvoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            # Response is a SalesBriefingReport instance, dump it to a dictionary
            report_dict = response.model_dump()
            logger.info(f"Report structured output generated for {company_name}")
            return report_dict
        except Exception as exc:
            logger.error(f"generate_report() structured output failed: {exc} — using assembled fallback")
            # Assembled fallback matching the new SalesBriefingReport schema
            
            # Map products
            products = []
            for p in structured_data.get("products_services", []):
                products.append({
                    "name": p.get("name", "Unknown Product"),
                    "description": p.get("description", "Not available")
                })
            
            # Map business signals
            signals = []
            for n in structured_data.get("recent_news", []):
                signals.append({
                    "category": "News/Recent Developments",
                    "signal": n.get("headline", "Not available"),
                    "significance": n.get("significance", "Not available")
                })
            
            # Map sources
            sources = []
            overview = structured_data.get("company_overview", {})
            
            return {
                "company_overview": {
                    "description": overview.get("description", f"Information about {company_name}"),
                    "industry": overview.get("industry", "Unknown"),
                    "size": overview.get("company_size", "Unknown"),
                    "founded": str(overview.get("founded", "Unknown")),
                    "headquarters": overview.get("headquarters", "Unknown"),
                    "business_model": overview.get("business_model", "Unknown")
                },
                "products_services": products,
                "target_customers": [
                    p.get("target_customer", "Unknown") 
                    for p in structured_data.get("products_services", []) 
                    if p.get("target_customer")
                ] or ["Not available"],
                "business_signals": signals,
                "risks_challenges": analysis.get("competitive_context", {}).get("risks", []) or ["Not available"],
                "suggested_discovery_questions": analysis.get("questions_to_ask", []) or ["Not available"],
                "suggested_outreach_strategy": [
                    t.get("talking_point", "")
                    for t in analysis.get("meeting_intelligence", {}).get("key_talking_points", [])
                ] or ["Not available"],
                "unknowns": ["Direct report generation failed; fallback assembled from raw insights."],
                "sources": [{"title": "Company Website", "url": website}]
            }

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Strip markdown code fences and parse JSON."""
        text = text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
