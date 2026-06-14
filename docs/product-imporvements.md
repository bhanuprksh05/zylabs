# AI Research Copilot — Product Improvements & Strategy

> **Document Purpose:** Critical analysis of current product weaknesses, prioritized roadmap, GTM strategy, and 90-day ownership plan.

---

## 1. Product Weaknesses (Identified)

### W1 — No Authentication / User Module
There is no login or signup system. Anyone with access to the portal can use it freely. This means zero personalization, no session ownership, no audit trails, and no way to tie usage to individual accounts. This is a foundational gap that blocks monetization, security, and multi-tenant use.

### W2 — No Rate Limiting
The API is fully open with no throttling. A single user or bot could flood the system with requests, burning through LLM tokens, degrading performance for all users, and creating runaway infrastructure costs. There is no protection layer at the request, IP, or user level.

### W3 — No Admin Module / Observability Dashboard
There is no internal tooling for the team to monitor the system. Error logs, token consumption, session counts, workflow success/failure rates, and user activity are all invisible. Operating this product blind makes debugging, cost management, and product decisions extremely difficult.

### W4 — No Monetization Layer (Credits / Subscriptions)
The product has no payment or access-control mechanism. Without a subscription tier or credit system, there is no revenue path and no way to limit access based on plan type. This is critical for any commercial launch.

### W5 — No Visual / Summary Layer (Low Attention Design)
Research reports are rendered as plain text or basic structured output. There are no visual summaries, charts, highlighted call-outs, or attention-guiding layouts. Users doing pre-meeting prep need to absorb information fast — walls of text fail that use case. No company logo, visual header, or infographic-style summary exists.

### W6 — LLM Provider is Hardcoded via Environment Variable
The model is fixed at the infrastructure level. Users cannot choose between GPT-4, Claude, Gemini, or a local model. Enterprise buyers often have model preferences due to data residency, cost, or existing contracts. This rigidity limits the product's appeal and creates a single point of failure.

### W7 — No Collaboration or Sharing Features
Sessions are isolated to whoever created them. There is no way to share a research briefing with a teammate, export it to Slack, email, or Google Docs, or collaborate in real-time. Sales teams are inherently collaborative — this is a significant missing workflow.

### W8 — No Session History or Knowledge Continuity
Once a session is completed, there is no mechanism to build upon prior research. If you researched a company last week and they updated their pricing page, you cannot diff the new output against the old. Institutional memory is lost.

---

## 2. Top 3 Improvements to Build Next

### Priority 1 — Authentication & User Module
**Why first:** Every other improvement (billing, admin, rate limiting, personalization) depends on knowing who the user is. Without identity, nothing else can be tied to an account. Implement JWT-based auth with email/password and optional Google OAuth. Each session, report, and usage event gets a `user_id`. This unlocks the entire product surface.

**Scope:** Registration, login, password reset, user profile, session ownership.

---

### Priority 2 — Subscription & Credit System
**Why second:** Once users exist, revenue can flow. Implement a tiered credit model — free users get 3 research sessions/month, Pro users get unlimited sessions with priority queuing, Enterprise gets SSO + custom model config + admin panel access. Use Stripe for billing. Credits gate LLM calls so token costs are controlled per user.

**Scope:** Stripe integration, plan tiers (Free / Pro / Enterprise), credit ledger per user, access control middleware, upgrade prompts.

---

### Priority 3 — Admin Dashboard + Observability
**Why third:** As paying users come in, the team needs visibility. Build an internal admin panel with: daily active users, sessions created, LLM token usage by model and user, error logs with stack traces, workflow success rates, and revenue metrics. Use this to catch runaway costs, debug failures, and make data-driven product decisions.

**Scope:** Admin role, usage logs table, error log viewer, token cost tracker, session analytics, simple dashboard UI.

---

## 3. Who Buys, Who Uses, and Why They Pay

### The Buyer
**Title:** VP of Sales, Head of Business Development, Revenue Operations Lead, or Founder at a growth-stage B2B company.

**Situation:** Their sales team spends 30–90 minutes before each important meeting manually Googling prospects, reading LinkedIn, skimming press releases, and piecing together a context brief. This is expensive, inconsistent, and often skipped entirely under time pressure.

**Pain:** Reps walk into calls underprepared. Enterprise deals get lost because a salesperson didn't know about a competitor acquisition last month, or missed that the company just raised a Series C.

**Why they pay:** They pay because a tool that saves 45 minutes of research per meeting and increases meeting quality across 20 reps is an easy ROI calculation. $50–200/month per seat is trivial compared to the cost of a missed enterprise deal.

---

### The User
**Title:** Account Executive, Sales Development Rep, Business Development Manager, or Founder doing their own sales.

**Situation:** They have 5 calls tomorrow and 30 minutes tonight to prepare for all of them. They need fast, structured, credible context — not a search engine.

**What they want:** A one-click briefing that tells them: what does this company do, who leads it, what's their current strategy, what are their pain points, what did they recently announce, and what should I ask or avoid.

**Why they keep using it:** It makes them look sharp in meetings without doing the grunt work. It becomes a pre-meeting ritual.

---

### Why They Pay (Value Props)

| Value Driver | Impact |
|---|---|
| Time saved per meeting prep | 45–90 minutes recovered |
| Increased meeting quality | Higher conversion rates |
| Consistency across teams | Every rep equally prepared |
| Reduced missed context | Fewer embarrassing knowledge gaps |
| Scales with meeting volume | More meetings = more value |

---

## 4. Success Metrics

### Acquisition Metrics
- **Signups per week** — growth rate of new users
- **Trial-to-paid conversion rate** — % of free users upgrading within 14 days
- **Cost per acquisition (CPA)** — marketing efficiency

### Engagement Metrics
- **Sessions per user per week** — product stickiness
- **Report completion rate** — % of initiated sessions that produce a full report
- **Follow-up chat messages per session** — measures depth of engagement
- **D7 / D30 retention** — are users returning after first week and first month?

### Revenue Metrics
- **Monthly Recurring Revenue (MRR)** — primary business health indicator
- **Average Revenue Per User (ARPU)** — by plan tier
- **Churn rate** — monthly subscription cancellations
- **Expansion revenue** — users upgrading plans or buying more credits

### Quality Metrics
- **Report accuracy score** (via user rating per report) — is the AI output trustworthy?
- **Workflow success rate** — % of LangGraph runs completing without error
- **Median report generation time** — speed matters for pre-meeting use
- **LLM token cost per session** — margins

### NPS / Qualitative
- **Net Promoter Score** — would users recommend this?
- **Qualitative feedback on report usefulness** — open-text after each session

---

## 5. 4-Week AI Feature Roadmap

### Week 1 — Smarter Research Extraction
- Upgrade the web scraping pipeline to extract structured signals: funding rounds, leadership changes, recent product launches, job postings (as a proxy for strategic direction), and customer reviews.
- Add source citation to every claim in the report so users trust the output.
- Output a confidence score per section based on source freshness and volume.

### Week 2 — Personalized Briefing Intelligence
- Allow users to set a "research profile" — their role (AE, founder, investor), their objective (close deal, partnership, due diligence), and their company context.
- Use this profile to customize report structure. An AE gets "pain points and buying signals." An investor gets "revenue model and competitive moat."
- Add a "What to ask in this meeting" section generated from the research.

### Week 3 — Visual Report Layer
- Generate a one-page visual summary (PDF-exportable) with company logo, key metrics in callout boxes, a sentiment indicator, and a "3 things to know" section at the top.
- Add a competitive landscape mini-map if competitors are mentioned.
- Enable highlight export: pull the 5 most important sentences from the report for quick scanning.

### Week 4 — LLM Flexibility + Model Comparison
- Build a model selector UI: GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro.
- Allow users on Pro/Enterprise plans to select their preferred model per session.
- Add a "compare mode" that runs the same research prompt through two models and shows the outputs side by side for quality evaluation.

---

## 6. Biggest Cost, Scaling, and Reliability Risks

### Cost Risks
- **Token runaway:** Without rate limiting and per-user credit caps, a single power user or a malfunctioning workflow loop can burn thousands of dollars in API calls in minutes. This is the single highest-urgency cost risk.
- **Web scraping at scale:** Scraping company websites and news sources for every session requires either expensive third-party APIs (Diffbot, Exa) or heavy compute for a self-hosted pipeline. Cost per session can balloon as report depth increases.
- **LLM cost per session at scale:** At 1,000 sessions/day with a 10K token average, you're at ~10M tokens/day. At $3/million tokens input, that's $30/day in LLM costs alone — manageable, but must be modeled and controlled by tier.

### Scaling Risks
- **LangGraph workflow bottleneck:** If the workflow executor is synchronous or runs on a single server thread, concurrent session requests will queue and timeout. Need a job queue (Celery, BullMQ, or similar) with horizontal worker scaling.
- **No caching layer:** If two users research the same company on the same day, the system runs the full pipeline twice. A Redis-based cache keyed on (company_domain + date) could cut redundant LLM calls by 30–50%.
- **Database connection pooling:** As sessions scale, unmanaged DB connections will become a bottleneck. PgBouncer or equivalent connection pooler needed before 10K+ sessions/day.

### Reliability Risks
- **LLM provider outages:** The system has a single LLM provider. When OpenAI or Anthropic has an incident (which happens), the entire product goes down. Need a fallback provider or graceful degradation mode.
- **No retry logic on workflow failures:** If a step in the LangGraph workflow fails (network timeout, API rate limit), the entire session may fail silently. Need retry with exponential backoff and partial result recovery.
- **No monitoring or alerting:** There are no alerts for elevated error rates, slow response times, or token cost anomalies. The team would find out about an outage from a user complaint, not a PagerDuty alert.

---

## 7. Feature to Remove and Why

### Remove: Manual Website Field Input

**Current behavior:** The user manually enters a company website URL as part of creating a research session.

**Why remove it:** This creates unnecessary friction and introduces error. Users shouldn't need to know or look up the exact URL — they know the company name. A proper company resolution layer (using a business data API like Clearbit, Apollo, or a web search step) should automatically resolve the company name to its canonical domain, LinkedIn page, Crunchbase profile, and news sources.

**What replaces it:** A single "Company Name" field. The system resolves the rest. If disambiguation is needed (e.g., "Apple" — the tech company or the record label), show a dropdown. This reduces session creation from a 3-field form to a 2-field form and cuts user error on research quality.

---

## 8. Feature to Add and Why

### Add: Meeting Intelligence Integration (Calendar + CRM Sync)

**What it is:** Connect the product to Google Calendar or Outlook. Automatically detect upcoming meetings where the attendee is from an external company. Surface a one-click "Research This Company" prompt 24 hours before the meeting. After the meeting, allow the user to log notes back to Salesforce or HubSpot with the briefing attached.

**Why add it:** This transforms the product from a tool users have to remember to use into a proactive workflow assistant that shows up at the right moment. Pre-meeting research has a natural trigger — the calendar event. Removing the "remember to research" burden dramatically increases usage frequency and habit formation.

**Business impact:** This is the feature that turns a productivity tool into a workflow platform — which is a fundamentally higher-value category and justifies enterprise pricing. It also creates deep integration stickiness (hard to churn when it's woven into the daily workflow).

---

## 9. First 90-Day Roadmap

### Days 1–30: Foundation & Monetization Readiness

| Week | Focus | Deliverables |
|---|---|---|
| 1 | Auth System | User registration, login, JWT, Google OAuth |
| 2 | Session Ownership | Tie all sessions/reports to user_id, user dashboard |
| 3 | Billing Integration | Stripe setup, Free/Pro plans, credit ledger |
| 4 | Rate Limiting + Admin | Per-user request throttling, internal admin panel v1 |

**Goal:** Product is secure, monetizable, and the team has visibility. First paying users by end of Week 4.

---

### Days 31–60: Quality & Retention

| Week | Focus | Deliverables |
|---|---|---|
| 5 | Visual Reports | One-page visual summary, PDF export, company logo fetch |
| 6 | Report Personalization | User research profile, role-based report structure |
| 7 | Reliability | Retry logic, LLM fallback provider, job queue for workflows |
| 8 | Analytics & Feedback | Session ratings, NPS prompt, usage analytics dashboard |

**Goal:** Users find reports more useful and visually compelling. Retention improves. D30 retention target: 40%+.

---

### Days 61–90: Growth & Scale

| Week | Focus | Deliverables |
|---|---|---|
| 9 | LLM Model Selector | Multi-model support, Pro/Enterprise model choice |
| 10 | Calendar Integration | Google Calendar sync, pre-meeting research trigger |
| 11 | Sharing & Collaboration | Share report via link, export to Notion/Slack/email |
| 12 | Performance & Caching | Redis cache for repeat company lookups, DB pooling |

**Goal:** Product is shareable, faster, and hooks into users' existing workflows. Pipeline for enterprise deals is open.

---

## 10. If I Owned This Product — What I'd Change First and Why

**I would implement user authentication and the credit system simultaneously, in the first sprint — not sequentially.**

Here's why this changes everything:

The instinct is to build auth first, then billing later. But that ordering is a trap. Every user who signs up during the "auth only" window becomes accustomed to free, unlimited access. When you introduce billing later, you're taking something away — and churn follows. You also lose the signal of what users are willing to pay for, because you've never asked.

By shipping auth and a freemium credit tier together on day one, you immediately learn:
- Who is willing to enter a credit card (your real customers)
- Which features drive upgrade intent
- What the natural usage ceiling is before users hit the free tier limit

The technical lift isn't much larger — Stripe's API is straightforward, and the middleware to check credits before executing a workflow is 50 lines of code. The business learning unlocked is enormous.

The second thing I'd change is the **report output format**. Right now, the report is probably a wall of structured text. I would immediately add a "TL;DR card" at the top of every report — three bullet points, a sentiment signal (Bullish / Neutral / Cautious), and one bold "what to know before you walk in" insight. This takes 15 minutes of reading and turns it into 60 seconds of scanning. That is the product's core value proposition: fast, credible, meeting-ready intelligence. The format should scream that, not bury it.

Speed of adoption, quality of first impression, and willingness to pay — these three unlock everything else on this roadmap.

---

*Document Version: 1.0 | Prepared for internal product planning*