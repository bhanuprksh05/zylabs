# AI Research Copilot — Engineering Decisions

> **Document Purpose:** Documents the key architectural and technical decisions made during the build, the reasoning behind each, tradeoffs accepted, current technical debt, and what would be tackled with more time.

---

## 1. Major Engineering Decisions

---

### Decision 1 — PostgreSQL over MongoDB for Data Persistence

**Context:**
The application needs to store research sessions, generated reports, follow-up chat history, and eventually user accounts, billing records, and usage logs. The choice of database shapes every layer of the stack — schema design, query patterns, ORM choice, and future scalability approach.

**Decision:**
Use **PostgreSQL** as the primary data store.

**Reasoning:**

The core data in this application is inherently relational. A research session belongs to a user. A report belongs to a session. Follow-up chat messages belong to both a session and a report. These ownership chains are natural foreign key relationships — exactly what a relational database is designed for.

PostgreSQL also gives us ACID transactions out of the box. When a LangGraph workflow completes and we need to write the report, update the session status, and decrement a user's credit balance atomically, a transactional database makes that safe. With MongoDB, you either build your own transaction logic or accept eventual inconsistency.

Additionally, PostgreSQL's JSONB column type means we don't give up flexibility where we need it. The raw LangGraph workflow output — which has variable structure depending on the research path taken — can be stored as JSONB inside a relational row. We get the structure of SQL where structure exists, and the flexibility of document storage where it doesn't.

Finally, PostgreSQL is the default choice in most managed cloud platforms (Supabase, Neon, Railway, RDS), which reduces operational overhead significantly.

**Alternatives Considered:**

| Option | Reason Rejected |
|---|---|
| **MongoDB** | Schema flexibility wasn't needed enough to justify losing joins and transactions. Our data model is relational, not document-native. |
| **SQLite** | Fine for local development but not viable for concurrent multi-user production workloads. Not horizontally scalable. |
| **DynamoDB** | Excellent at scale, but requires upfront access-pattern design and makes ad-hoc querying painful. Premature for this stage. |
| **Supabase (Postgres-as-a-service)** | Considered as a platform, not an alternative to Postgres itself. Would be a valid hosting choice. |

**Tradeoffs Made:**

- ✅ Strong data integrity, relational queries, and ACID compliance
- ✅ JSONB gives document-style flexibility for variable workflow outputs
- ✅ Ecosystem maturity — ORMs, migration tools, monitoring all first-class
- ⚠️ Schema migrations required as the data model evolves (more discipline needed than MongoDB)
- ⚠️ Vertical scaling limit before sharding becomes necessary (not a concern at current scale)
- ⚠️ Full-text search is possible in Postgres but less powerful than Elasticsearch for large report corpora

---

### Decision 2 — Tavily API for Web Search over LLM-Native Knowledge

**Context:**
The core value of this product is generating a research briefing grounded in *current*, *real-world* information about a company — recent funding rounds, leadership changes, product launches, press releases, and competitive moves. The question was: where does that information come from?

**Decision:**
Use **Tavily API** as the web search and retrieval layer, feeding real-time web results into the LLM prompt as context — rather than relying on the LLM's parametric (baked-in training) knowledge.

**Reasoning:**

LLMs have a training cutoff. Claude, GPT-4, and Gemini all have knowledge that is months to over a year stale. For a sales intelligence product, a funding round from 6 months ago or a CEO departure from last quarter is not historical trivia — it's critical meeting context. Relying on the LLM's internal knowledge for this would produce confidently stated but potentially outdated information, which is worse than no information at all.

Tavily is purpose-built for LLM-integrated search. Unlike raw Google Search API or SerpAPI, Tavily returns pre-processed, relevance-ranked, clean text snippets rather than raw HTML — which means less prompt bloat, lower token cost, and better retrieval quality. It also supports domain-specific search, which lets us filter results to news sources, company websites, or LinkedIn when appropriate.

The architectural pattern this enables is **Retrieval-Augmented Generation (RAG)** at the session level: search → retrieve → inject into prompt → generate. This keeps the LLM in its role as a reasoning and synthesis engine, while Tavily handles the information retrieval role it's better suited for.

**Alternatives Considered:**

| Option | Reason Rejected |
|---|---|
| **LLM parametric knowledge only** | Stale data. A sales briefing based on 12-month-old knowledge is a liability, not an asset. |
| **SerpAPI / Google Search API** | Returns raw HTML and metadata. Requires additional parsing and cleaning before usable in prompts. Higher token cost and more preprocessing work. |
| **Bing Search API** | Similar parsing overhead to SerpAPI. Less developer-friendly than Tavily for LLM pipelines. |
| **Exa (formerly Metaphor)** | Excellent semantic search quality, especially for finding similar companies or topics. More expensive per call and better suited for discovery use cases than structured company research. Worth revisiting for future "find competitors" features. |
| **Self-hosted web scraper (BeautifulSoup / Playwright)** | Maximum control but significant infrastructure cost — headless browser management, bot detection, rate limit handling, proxy rotation. A distraction at this stage. |

**Tradeoffs Made:**

- ✅ Real-time, current information — reports reflect what happened last week, not last year
- ✅ Clean text output optimized for LLM consumption — lower token cost vs raw HTML
- ✅ Fast integration — Tavily's Python client is minimal boilerplate
- ✅ Source URLs returned with each result — enables citation in reports
- ⚠️ External API dependency — Tavily outage or rate limit directly impacts research quality
- ⚠️ Per-search cost adds up at scale — need to model cost per session carefully
- ⚠️ Search quality is only as good as what's indexed — obscure private companies may return sparse or low-quality results
- ⚠️ No control over what gets returned — adversarial SEO or low-quality pages can pollute context if not filtered

---

### Decision 3 — Claude API (Anthropic) as the Primary LLM

**Context:**
The LLM is the reasoning core of the product. Every research synthesis, report generation, and follow-up chat response flows through it. The choice of provider affects output quality, latency, context window size, cost, and the reliability of structured output generation.

**Decision:**
Use **Anthropic's Claude API** (specifically Claude 3.5 Sonnet or equivalent) as the primary LLM, configured via environment variable.

**Reasoning:**

Claude was chosen primarily for three reasons: long context window, instruction-following quality, and structured output reliability.

**Long context window:** A research session can accumulate significant token volume — multiple Tavily search results, scraped page content, prior chat turns, and a long system prompt. Claude's 200K context window means we rarely need to truncate or chunk inputs, which preserves research coherence. Truncating context mid-research is a silent quality killer.

**Instruction following:** Generating a structured research briefing (with specific sections, consistent formatting, and constrained tone) requires an LLM that reliably follows detailed system prompts. Claude consistently outperforms on tasks requiring structured, multi-section document generation with strict formatting constraints.

**Reduced hallucination tendency on grounded tasks:** When given real source material (from Tavily), Claude is less likely to blend in fabricated facts compared to some alternatives. For a product where factual accuracy is the core value proposition, this matters.

The decision to configure the model via environment variable (rather than hardcoding) was deliberate — it gives us the flexibility to swap providers without a code change, and sets up the future multi-model selector feature.

**Alternatives Considered:**

| Option | Reason Rejected |
|---|---|
| **OpenAI GPT-4o** | Excellent quality, similar context window. Slightly higher cost at volume. More restrictive rate limits at lower API tiers. Would be a strong alternative and is a natural fallback option. |
| **Google Gemini 1.5 Pro** | 1M token context window is impressive. JSON output mode is strong. Less battle-tested in production LangGraph pipelines at the time of this decision. |
| **Mistral / Llama 3 (self-hosted)** | Eliminates per-token API cost. But requires GPU infrastructure, model management, and fine-tuning work to match Claude-quality structured output. Not practical at this stage. |
| **Cohere Command R+** | Strong RAG performance and grounding. Smaller ecosystem and less community tooling around it. |

**Tradeoffs Made:**

- ✅ Best-in-class structured output generation for long, multi-section reports
- ✅ 200K context window handles large research sessions without chunking
- ✅ Strong instruction adherence — system prompts reliably shape report format
- ✅ Env-var configuration enables future model flexibility without code changes
- ⚠️ Single provider dependency — Anthropic API outage takes down the product
- ⚠️ Per-token cost is real at scale — no free tier for production workloads
- ⚠️ Data residency: all research content passes through Anthropic's API — may block regulated enterprise customers (finance, healthcare, government)
- ⚠️ Model versioning: Claude versions deprecate, requiring periodic prompt regression testing when upgrading

---

## 2. Top Technical Debt Items

### TD1 — No Request Queue / Job Worker Architecture
LangGraph workflows are currently executed synchronously within the request lifecycle. This means the HTTP request stays open while the entire research pipeline runs — which can take 30–90 seconds. Under concurrent load, this will exhaust server threads and create cascading timeouts. The correct architecture is: accept the request → enqueue a job → return a job ID immediately → client polls or subscribes via WebSocket for progress. **Priority: High. Must fix before scaling.**

### TD2 — No Retry or Error Recovery on Workflow Steps
If Tavily returns a 429 or Claude returns a 500 mid-workflow, the entire session fails silently or with a generic error. There is no retry logic, no partial result recovery, and no structured error state per workflow step. Users lose their session progress entirely on transient failures. **Priority: High. Directly impacts user trust.**

### TD3 — Prompts are Hardcoded in Application Code
System prompts, research instructions, and report templates are embedded directly in Python files. Changing prompt wording requires a code deploy. This blocks rapid iteration on prompt quality and makes A/B testing report formats impossible without engineering involvement. Prompts should live in a configurable store (database, config file, or a dedicated prompt management layer). **Priority: Medium.**

### TD4 — No Input Validation or Sanitization on Research Parameters
Company name and website URL fields are passed into the workflow with minimal validation. A malformed URL, an extremely long company name, or a prompt injection attempt in the "research objective" field could cause unexpected behavior downstream. Input sanitization, length limits, and basic prompt injection guards are missing. **Priority: Medium-High.**

### TD5 — No Caching for Repeat Company Lookups
If two users research the same company on the same day, the system runs the full Tavily search + LLM pipeline twice, duplicating cost and latency. A simple Redis cache keyed on `(normalized_company_domain, date)` could serve repeat lookups instantly and reduce per-session cost by an estimated 20–40% at modest scale. **Priority: Medium.**

### TD6 — Database Has No Migration Strategy
Schema changes are being applied manually or via ad-hoc scripts. There is no versioned migration system (Alembic, Flyway, or similar). As the schema evolves to support users, billing, credits, and admin features, unmanaged migrations become a data integrity risk. **Priority: Medium. Must formalize before the auth/billing sprint.**

---

## 3. Biggest Technical Risk

### Risk: Single LLM Provider with No Fallback

The entire product's core functionality — report generation, follow-up chat, structured research synthesis — depends on a single call to the Anthropic API. There is no fallback provider, no graceful degradation mode, and no circuit breaker.

**Why this is the biggest risk:**

Anthropic, like all LLM API providers, has periodic service disruptions. These are not hypothetical — every major LLM provider (OpenAI, Anthropic, Google) has had multi-hour outages that were widely reported. When this happens, the AI Research Copilot becomes a form with a submit button that returns an error. There is nothing to fall back to.

Unlike a slow database or a Tavily hiccup, an LLM outage doesn't degrade the product — it zeroes it. A salesperson who relies on this tool before a meeting at 8am and finds it broken at 7:50am doesn't forgive that easily.

**Compounding factors:**
- The model is set via a single environment variable with no fallback chain
- There is no circuit breaker to detect provider health and reroute
- There is no cached "last known good" report to serve during an outage
- Users have no visibility into outage status within the product

**Mitigation Plan:**
1. Implement a provider fallback chain: Claude → GPT-4o → cached result
2. Add a circuit breaker (e.g., using `tenacity` with exponential backoff)
3. Surface an in-app status banner when the LLM provider is degraded
4. For follow-up chat specifically, allow read-only mode (users can re-read the report) even when generation is offline
5. Subscribe to Anthropic's status page via webhook and auto-update the product's health indicator

---

## 4. What Would Be Improved with 2 Additional Weeks

### Week 1 — Reliability & Production Hardening

**Async Job Queue for Workflow Execution**
Migrate workflow execution from synchronous HTTP to an async job queue (Celery + Redis or BullMQ). The API returns a `session_id` immediately. The client subscribes via WebSocket or polls a `/status` endpoint. This eliminates request timeouts, enables background retries, and makes the product stable under concurrent load. This is the highest-leverage engineering change available.

**Retry Logic + Partial Result Recovery**
Wrap every external API call (Tavily, Claude) in retry logic with exponential backoff using `tenacity`. Store intermediate workflow state to the database as each step completes, so a failure at step 4 of 6 can resume from step 4 rather than restarting entirely. Surface clear error states to the user with actionable messaging ("Research paused — retrying in 30 seconds").

**LLM Fallback Provider**
Implement a provider fallback chain. If the Claude API returns 5xx errors or exceeds timeout, automatically retry the same prompt against GPT-4o. Add a circuit breaker that trips after 3 consecutive failures and routes all traffic to the fallback until the primary recovers. This eliminates the single biggest reliability risk in the product.

---

### Week 2 — Developer Velocity & Observability

**Prompt Management System**
Move all system prompts and report templates out of application code and into a database-backed prompt store. Build a minimal internal UI to edit, version, and A/B test prompts without a code deploy. Tag each generated report with the prompt version that produced it. This turns prompt iteration from a 2-day engineering cycle into a 10-minute experiment.

**Structured Logging + Alerting**
Integrate structured logging (JSON logs via `structlog` or similar) with a log aggregation platform (Datadog, Logtail, or self-hosted Grafana + Loki). Define alerts for: error rate > 5% over 5 minutes, p95 session generation time > 120 seconds, Tavily or Claude API error rate spike, and daily token cost exceeding threshold. The team should learn about outages from an alert, not from a user complaint.

**Alembic Migration Setup + Schema Formalization**
Introduce Alembic for versioned database migrations. Document the current schema with full column types, constraints, and indexes. Add missing indexes on `session.user_id`, `session.created_at`, and `report.session_id` — these will become table scans at scale without them. This sets the foundation for the auth and billing sprint to proceed safely.

---

*Document Version: 1.0 | Prepared for internal engineering review*