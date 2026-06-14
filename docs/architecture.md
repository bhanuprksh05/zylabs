# Research Copilot — Architecture

> **AI-powered company research and meeting preparation platform.**
> Given a company name, website, and meeting objective, the system autonomously researches the target company, produces a structured sales briefing report, and provides an interactive follow-up chat grounded in the report.

---

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [System Architecture Diagram](#system-architecture-diagram)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Backend Architecture](#backend-architecture)
  - [Application Layer (FastAPI)](#application-layer-fastapi)
  - [AI / Core Layer (LangGraph)](#ai--core-layer-langgraph)
  - [Data Layer](#data-layer)
  - [Infrastructure Services](#infrastructure-services)
- [Frontend Architecture](#frontend-architecture)
- [API Surface](#api-surface)
- [LangGraph Workflow — Deep Dive](#langgraph-workflow--deep-dive)
  - [Graph Topology](#graph-topology)
  - [ResearchState Schema](#researchstate-schema)
  - [Node Descriptions](#node-descriptions)
  - [Routing Logic](#routing-logic)
  - [Quality Control Loop](#quality-control-loop)
- [Data Models](#data-models)
- [Cross-Cutting Concerns](#cross-cutting-concerns)
  - [Error Handling](#error-handling)
  - [Logging & Observability](#logging--observability)
  - [Resilience & Retry](#resilience--retry)
  - [Configuration Management](#configuration-management)
- [Deployment](#deployment)

---

## High-Level Overview

The system follows a **three-tier architecture**:

1. **Frontend** — React SPA that provides the user interface for creating research sessions, monitoring workflow progress, viewing reports, and chatting with the AI assistant.
2. **Backend** — FastAPI application that exposes a RESTful API, orchestrates the AI research pipeline via LangGraph, and manages persistence.
3. **Infrastructure** — PostgreSQL (primary data store), Redis (caching / session state), and external APIs (Anthropic Claude, Tavily Search).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              User (Browser)                                  │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │ HTTP (localhost:3000 → :8000)
┌──────────────────▼───────────────────────────────────────────────────────────┐
│                        Frontend (React / CRA)                                │
│  - Session management UI                                                     │
│  - Workflow progress tracker (polling)                                        │
│  - Report viewer                                                             │
│  - Follow-up chat interface                                                  │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │ REST API (JSON)
┌──────────────────▼───────────────────────────────────────────────────────────┐
│                     Backend (FastAPI + Uvicorn)                               │
│                                                                              │
│  ┌─────────────┐  ┌───────────────┐  ┌────────────────────────────────────┐  │
│  │ API Layer   │  │  Middleware    │  │  Core / AI Pipeline (LangGraph)    │  │
│  │ (Routes,    │→ │  (Logging,    │→ │  (Agents, Graph, Tools)            │  │
│  │  Schemas)   │  │   Errors,     │  │                                    │  │
│  │             │  │   CORS)       │  │  ResearcherAgent ← Tavily + Scraper│  │
│  └──────┬──────┘  └───────────────┘  │  SummarizerAgent ← Claude LLM     │  │
│         │                            └──────────────┬─────────────────────┘  │
│  ┌──────▼──────────────────────────────────────────▼───────────────────────┐ │
│  │                    Data Layer                                           │ │
│  │  Repository Pattern → SQLAlchemy ORM → PostgreSQL (asyncpg)            │ │
│  │  Redis (aioredis) for caching                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                   │                              │
      ┌────────────▼──────────┐      ┌────────────▼────────────┐
      │  External: Anthropic  │      │  External: Tavily       │
      │  Claude Haiku 4.5     │      │  Search API             │
      │  (LLM reasoning)      │      │  (Web search)           │
      └───────────────────────┘      └─────────────────────────┘
```

---

## Technology Stack

| Layer          | Technology                    | Purpose                                           |
| -------------- | ----------------------------- | ------------------------------------------------- |
| **Frontend**   | React 19, Tailwind CSS 3      | Single-page application                           |
| **Frontend**   | Lucide React                  | Icon library                                      |
| **Backend**    | Python, FastAPI, Uvicorn      | Async REST API server                             |
| **AI Engine**  | LangGraph, LangChain          | Stateful, multi-step AI workflow orchestration     |
| **LLM**       | Anthropic Claude Haiku 4.5     | Reasoning, planning, summarization, report gen     |
| **Search**     | Tavily API                    | Real-time web search with advanced depth           |
| **Scraping**   | httpx, BeautifulSoup4         | Company website content extraction                 |
| **Database**   | PostgreSQL + asyncpg          | Primary relational data store (async)              |
| **ORM**        | SQLAlchemy 2.0 (async)        | Mapped models, relationship management             |
| **Migrations** | Alembic                       | Database schema migrations                         |
| **Cache**      | Redis (aioredis)              | Caching and session state                          |
| **Validation** | Pydantic v2, pydantic-settings| Request/response validation, config management     |
| **Logging**    | Python logging + structlog    | Structured, request-scoped logging                 |
| **Retry**      | tenacity (available)          | Exponential backoff (custom implementation used)   |

---

## Project Structure

```
zylabs/
├── backend/
│   ├── main.py                     # FastAPI app factory + Uvicorn entry point
│   ├── requirements.txt            # Python dependencies
│   ├── pyproject.toml              # Project metadata
│   ├── docker-compose.yml          # Infrastructure services
│   ├── .env / .env.example         # Environment configuration
│   │
│   ├── config/
│   │   ├── settings.py             # Pydantic BaseSettings (env-driven config)
│   │   ├── constants.py            # Workflow nodes, thresholds, limits
│   │   └── prompts.py              # LLM prompt templates (planned)
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── sessions.py         # CRUD for research sessions
│   │   │   ├── workflow.py         # Workflow run / resume / status
│   │   │   └── chat.py             # Follow-up chat endpoints
│   │   ├── schemas/
│   │   │   ├── __init__.py         # Re-exports all schemas
│   │   │   ├── session.py          # Session request/response models
│   │   │   ├── workflow.py         # Workflow request/response models
│   │   │   ├── chat.py             # Chat request/response models
│   │   │   └── common.py           # Shared models (errors, pagination)
│   │   └── middlewares/
│   │       ├── logging.py          # Request logging + DB error logging
│   │       └── errors.py           # Global exception handlers
│   │
│   ├── core/
│   │   ├── agents/
│   │   │   ├── researcher.py       # ResearcherAgent (planning, search, competitors)
│   │   │   └── summarizer.py       # SummarizerAgent (summarize, analyze, QA, report)
│   │   ├── graph/
│   │   │   ├── state.py            # ResearchState TypedDict definition
│   │   │   ├── nodes.py            # 8 node functions + 2 routing functions
│   │   │   └── workflow.py         # StateGraph construction + compilation
│   │   └── tools/
│   │       ├── web_search.py       # Tavily search with retry
│   │       └── scraper.py          # Website scraper with retry + SSL fallback
│   │
│   ├── db/
│   │   ├── session.py              # SQLAlchemy async engine + session factory
│   │   ├── models.py               # ORM models (4 tables) + enums
│   │   └── repository/
│   │       ├── __init__.py         # Re-exports + FastAPI Depends() helpers
│   │       ├── session.py          # SessionRepository
│   │       ├── workflow.py         # WorkflowRunRepository
│   │       ├── chat.py             # ChatRepository
│   │       └── error.py            # ErrorLogRepository
│   │
│   ├── services/
│   │   └── redis.py                # Redis client init / close / getter
│   │
│   └── tests/                      # Test suite
│
├── frontend/
│   ├── package.json                # React dependencies
│   ├── tailwind.config.js          # Tailwind configuration
│   ├── postcss.config.js           # PostCSS plugins
│   └── src/
│       ├── index.js                # React entry point
│       ├── App.js                  # Main application (single-file SPA)
│       ├── App.css                 # Component styles
│       ├── index.css               # Global / Tailwind base styles
│       ├── api.js                  # API client (fetch wrapper)
│       └── config.js               # API base URL constants
│
└── docs/
    ├── README.md                   # Project overview
    ├── architecture.md             # This document
    ├── engineering-decisions.md     # ADRs and design rationale
    └── product-improvements.md     # Planned improvements and backlog
```

---

## Backend Architecture

### Application Layer (FastAPI)

The backend follows a **layered architecture** with clear separation of concerns:

```
Request → Middleware → Route Handler → Repository / Core → Database / External APIs
```

#### App Factory (`main.py`)

- **`create_app()`** builds the FastAPI instance with middleware, routers, and lifecycle hooks.
- **Lifespan** context manager handles startup (DB init, Redis init) and shutdown (Redis close).
- **Middleware stack** (applied in order):
  1. `CORSMiddleware` — allows `localhost:3000` origin
  2. `LoggingMiddleware` — request-scoped logging with `X-Request-ID` tracing
  3. Global exception handlers — HTTP, validation, and unhandled errors

#### Route Groups

| Prefix                  | Router          | Purpose                               |
| ----------------------- | --------------- | ------------------------------------- |
| `/api/v1/sessions`      | `sessions.py`   | CRUD operations on research sessions  |
| `/api/v1/workflows`     | `workflow.py`   | Start, resume, and poll workflows     |
| `/api/v1/chat`          | `chat.py`       | Follow-up chat with report context    |
| `/health`               | Inline          | Health check endpoint                 |

#### Schemas (Pydantic v2)

Organized by domain in `api/schemas/` with a central `__init__.py` re-export:

- **Session** — `CreateSessionRequest`, `SessionResponse`, `SessionDetailResponse`, `SessionListResponse`
- **Workflow** — `RunWorkflowRequest`, `WorkflowStartedResponse`, `WorkflowResumeResponse`, `WorkflowStatusResponse`
- **Chat** — `ChatRequest`, `ChatResponse`, `ChatMessageResponse`, `ChatHistoryResponse`, `TokenUsage`
- **Common** — `ErrorResponse`, `SuccessResponse`, `PaginationParams`

---

### AI / Core Layer (LangGraph)

The AI pipeline is the heart of the system. It uses **LangGraph** to orchestrate a multi-step, stateful research workflow as a directed graph with conditional branching and retry loops.

#### Two-Agent Architecture

| Agent               | File                | Responsibilities                                                   | LLM Config         |
| ------------------- | ------------------- | ------------------------------------------------------------------ | ------------------- |
| **ResearcherAgent** | `agents/researcher.py` | Research planning, Tavily search, website scraping, competitor analysis | Claude 4.5, temp=0.2, 2K tokens |
| **SummarizerAgent** | `agents/summarizer.py` | Content summarization, structured extraction, analysis, quality check, report generation | Claude 4.5, temp=0.2, 3K tokens (main) / temp=0.1, 1.5K tokens (QA) |

#### Tools

| Tool             | File                | External Service | Behavior                                                      |
| ---------------- | ------------------- | ---------------- | ------------------------------------------------------------- |
| **Web Search**   | `tools/web_search.py` | Tavily API       | Async search with exponential backoff retry, returns `[]` on failure |
| **Web Scraper**  | `tools/scraper.py`    | Target website   | httpx + BeautifulSoup, SSL fallback, noise tag removal, 8K char limit |

---

### Data Layer

#### Repository Pattern

Each domain entity has a dedicated repository class injected via FastAPI `Depends()`:

```
Route Handler
  └─ Depends(get_session_repo)   → SessionRepository(db)
  └─ Depends(get_workflow_repo)  → WorkflowRunRepository(db)
  └─ Depends(get_chat_repo)      → ChatRepository(db)
```

- Repositories encapsulate all SQL queries via SQLAlchemy's async ORM.
- The workflow background task creates its own `AsyncSessionLocal()` session independently of the request lifecycle.

#### Database (PostgreSQL)

- **Engine**: `asyncpg` driver for fully async I/O.
- **Session**: `AsyncSession` with `expire_on_commit=False` for safe detached reads.
- **Schema creation**: Auto-creates tables on startup via `Base.metadata.create_all` (Alembic for production).

---

### Infrastructure Services

#### Redis

- Initialized at startup via `init_redis()`, closed at shutdown via `close_redis()`.
- Accessed via `get_redis()` singleton getter.
- Uses `redis.asyncio` for non-blocking operations.
- Currently available for caching; not yet deeply integrated.

---

## Frontend Architecture

The frontend is a **Create React App (CRA)** single-page application:

| Aspect         | Detail                                                               |
| -------------- | -------------------------------------------------------------------- |
| **Framework**  | React 19 with functional components and hooks                        |
| **Styling**    | Tailwind CSS 3 via PostCSS                                           |
| **Icons**      | Lucide React                                                         |
| **API Client** | `api.js` — thin `fetch` wrapper with centralized error handling       |
| **Config**     | `config.js` — `API_BASE_URL` pointing to `http://localhost:8000/api/v1` |
| **Structure**  | Single-file SPA (`App.js` ≈ 50KB) managing all views and state        |

### Frontend ↔ Backend Communication

- All API calls use `fetch` with JSON payloads.
- Workflow progress is tracked by **polling** `GET /api/v1/workflows/status/{id}`.
- No WebSocket or SSE currently — uses request/response polling.

---

## API Surface

### Sessions

| Method   | Endpoint                  | Description                          |
| -------- | ------------------------- | ------------------------------------ |
| `POST`   | `/api/v1/sessions/`       | Create a new research session        |
| `GET`    | `/api/v1/sessions/`       | List all sessions (paginated)        |
| `GET`    | `/api/v1/sessions/{id}`   | Get session details + report         |
| `DELETE` | `/api/v1/sessions/{id}`   | Soft-delete a session                |

### Workflows

| Method   | Endpoint                        | Description                                      |
| -------- | ------------------------------- | ------------------------------------------------ |
| `POST`   | `/api/v1/workflows/run/{id}`    | Start the research workflow for a session         |
| `POST`   | `/api/v1/workflows/resume/{id}` | Resume a failed workflow from last checkpoint     |
| `GET`    | `/api/v1/workflows/status/{id}` | Poll node-level workflow progress                 |

### Chat

| Method   | Endpoint                  | Description                              |
| -------- | ------------------------- | ---------------------------------------- |
| `POST`   | `/api/v1/chat/{id}`       | Send a follow-up question (report context) |
| `GET`    | `/api/v1/chat/{id}`       | Get full chat history for a session        |
| `DELETE` | `/api/v1/chat/{id}`       | Clear chat history                         |

### Health

| Method | Endpoint   | Description                      |
| ------ | ---------- | -------------------------------- |
| `GET`  | `/health`  | Health check (returns env info)  |

---

## LangGraph Workflow — Deep Dive

### Graph Topology

```
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
```

### ResearchState Schema

The entire workflow operates on a single shared `TypedDict` that flows through all nodes. Each node reads what it needs and returns a **partial update dict** (only the keys it modifies):

```python
class ResearchState(TypedDict):
    # Input (set before graph starts)
    company_name: str
    website: str
    objective: str
    session_id: str
    run_id: str

    # Planner output
    research_plan: dict        # focus_areas, include_competitors, depth, search_queries, ...

    # Web research data
    raw_search_results: list   # Tavily result dicts
    scraped_content: str       # Cleaned website text (max 8K chars)
    competitor_data: dict      # Structured competitor intelligence

    # Intermediate processing
    content_summary: str       # Compressed bullet-point summary
    structured_data: dict      # Typed facts (overview, products, pricing, leadership, ...)

    # Analysis
    analysis: dict             # Meeting-ready intelligence (talking points, pain points, ...)

    # Quality control
    quality_score: float       # 0.0 – 1.0 (threshold: 0.8)
    quality_issues: list       # Issues to address on retry
    retry_count: int           # analyze → quality_check loop counter

    # Final output
    report: dict               # Structured SalesBriefingReport

    # Recoverability
    last_completed_node: str   # Checkpoint for resume
    error_count: int           # Accumulated non-fatal errors
    errors: list               # Error messages
```

### Node Descriptions

| #  | Node                    | Agent            | Function                                                                              |
| -- | ----------------------- | ---------------- | ------------------------------------------------------------------------------------- |
| 1  | `planner`               | ResearcherAgent  | Analyses the objective → produces a structured research plan (focus areas, queries, depth) |
| 2  | `competitor_research`   | ResearcherAgent  | *Conditional.* Gathers competitor intelligence via Tavily + LLM extraction             |
| 3  | `web_research`          | ResearcherAgent  | Runs 5 Tavily searches + scrapes the company website                                   |
| 4  | `summarize_content`     | SummarizerAgent  | Compresses raw search results + scraped text into structured bullet-point summary       |
| 5  | `structured_insights`   | SummarizerAgent  | Extracts typed JSON facts: overview, products, pricing, leadership, funding, tech       |
| 6  | `analyze`               | SummarizerAgent  | Synthesizes all data into meeting-ready intelligence (talking points, pain points, agenda) |
| 7  | `quality_check`         | SummarizerAgent  | Validates analysis on 5 criteria (0.2 each → max 1.0). May trigger retry loop          |
| 8  | `generate_report`       | SummarizerAgent  | Produces final `SalesBriefingReport` via structured output (Pydantic schema)            |

### Routing Logic

**`route_after_planner`** — Conditional branch after planning:
- If `research_plan.include_competitors == True` AND `competitor_queries` exist → `competitor_research`
- Otherwise → `web_research` (skip competitors)

**`route_after_quality_check`** — Quality gate:
- `quality_score ≥ 0.8` → `generate_report` ✓
- `quality_score < 0.8` AND `retry_count < 2` → `analyze` (retry with quality_issues feedback)
- `retry_count ≥ 2` (exhausted) → `generate_report` (best-effort)

### Quality Control Loop

```
analyze ──→ quality_check ──→ score ≥ 0.8? ──→ generate_report
                  │
                  └── score < 0.8 & retries left ──→ analyze (with quality_issues)
                                                        │
                                                        └── max 2 retries, then force generate_report
```

The quality check scores on **5 criteria** (0.2 points each):
1. **Executive summary** — objective-specific, not generic
2. **Talking points** — ≥2 points with specific rationale
3. **Pain points** — ≥1 pain with evidence from research
4. **Discovery questions** — ≥2 specific, non-generic questions
5. **Meeting agenda** — ≥2 agenda items with context

---

## Data Models

### Entity-Relationship Diagram

```
┌─────────────────────────┐
│    ResearchSession      │
├─────────────────────────┤
│ id          UUID (PK)   │
│ company_name  VARCHAR   │
│ website       VARCHAR   │
│ objective     TEXT      │
│ status        ENUM      │──── pending | running | completed | failed
│ report        JSON      │
│ raw_research  JSON      │
│ error_message TEXT      │
│ is_active     BOOLEAN   │
│ created_at    DATETIME  │
│ updated_at    DATETIME  │
└──────┬────────┬─────────┘
       │        │
       │ 1:N    │ 1:N
       ▼        ▼
┌──────────────────┐   ┌──────────────────────┐
│  WorkflowRun     │   │    ChatMessage        │
├──────────────────┤   ├──────────────────────┤
│ id        UUID   │   │ id        UUID        │
│ session_id UUID  │   │ session_id UUID       │
│ status    ENUM   │   │ role       ENUM       │──── user | assistant
│ node_statuses JSON│   │ content    TEXT       │
│ graph_state JSON │   │ prompt_tokens  INT    │
│ error_message TEXT│   │ completion_tokens INT │
│ started_at  DT   │   │ created_at   DATETIME │
│ completed_at DT  │   │ is_active    BOOLEAN  │
│ is_active BOOL   │   └──────────────────────┘
│ created_at DT    │
└──────────────────┘

┌──────────────────────────┐
│       ErrorLog           │
├──────────────────────────┤
│ id             UUID (PK) │
│ request_id     VARCHAR   │
│ workflow_run_id UUID     │
│ error_type     VARCHAR   │
│ message        TEXT      │
│ status_code    INTEGER   │
│ path           VARCHAR   │
│ method         VARCHAR   │
│ stack_trace    TEXT      │
│ extra          JSONB     │
│ created_at     DATETIME  │
└──────────────────────────┘
```

### Key Relationships

- **ResearchSession → WorkflowRun** (1:N) — A session can have multiple workflow runs (re-runs after failure).
- **ResearchSession → ChatMessage** (1:N) — Follow-up chat tied to a completed session's report.
- **WorkflowRun.graph_state** — Stores the full LangGraph state snapshot for checkpointing and resume.
- **ErrorLog** — Standalone table for centralized error tracking, correlated by `request_id` or `workflow_run_id`.

---

## Cross-Cutting Concerns

### Error Handling

**Three-layer error strategy:**

1. **Route-level** — FastAPI `HTTPException` for client-facing errors (404, 400, 422).
2. **Middleware-level** — Global exception handlers in `errors.py`:
   - `StarletteHTTPException` → structured `ErrorResponse` JSON
   - `RequestValidationError` → detailed field-level error messages
   - `Exception` (catch-all) → 500 with debug details in non-production
3. **Node-level** — Each LangGraph node catches exceptions, logs them, appends to `state.errors`, and returns graceful fallback data. The workflow never crashes on a single node failure.

**Error persistence:** Unhandled exceptions caught by `LoggingMiddleware` are written to the `error_logs` table with full stack traces, request context, and correlation IDs.

### Logging & Observability

- **Request logging**: `LoggingMiddleware` logs start/end of every request with method, path, status code, duration, and `X-Request-ID`.
- **Node logging**: Each graph node logs entry, key metrics, and exit at `INFO` level.
- **Structured extras**: All log calls include `extra={}` dict with typed fields for downstream aggregation.
- **Request tracing**: `X-Request-ID` header is auto-generated or passed through, attached to the response, and persisted in error logs.

### Resilience & Retry

| Component         | Strategy                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| **Tavily Search** | Exponential backoff, `MAX_NODE_RETRIES=2` attempts, returns `[]` on failure |
| **Web Scraper**   | Exponential backoff, `MAX_NODE_RETRIES=2`, SSL verification fallback, returns `""` on failure |
| **LLM Calls**     | Each agent method wraps LLM calls in `try/except` with hardcoded fallback responses |
| **Workflow**      | Checkpoint-based resume — on failure, `POST /resume/{id}` replays from `last_completed_node` |
| **Quality Loop**  | `MAX_QUALITY_RETRIES=2` — prevents infinite analyze↔quality_check loops  |

### Configuration Management

All configuration is managed via **environment variables** loaded through Pydantic `BaseSettings`:

```
.env → pydantic-settings → config/settings.py → Settings singleton
```

| Variable            | Default                            | Purpose                            |
| ------------------- | ---------------------------------- | ---------------------------------- |
| `ENV`               | `development`                      | Environment name                   |
| `PORT`              | `8000`                             | Uvicorn port                       |
| `LOG_LEVEL`         | `INFO`                             | Python logging level               |
| `CORS_ORIGINS`      | `["http://localhost:3000"]`        | Allowed CORS origins               |
| `DATABASE_URL`      | `postgresql+asyncpg://...`         | Async PostgreSQL connection string |
| `REDIS_URL`         | `redis://localhost:6379`           | Redis connection string            |
| `ANTHROPIC_API_KEY` | (required)                         | Claude API key                     |
| `ANTHROPIC_MODEL`   | `claude-3-5-sonnet-latest`         | LLM model identifier              |
| `TAVILY_API_KEY`    | (required)                         | Tavily search API key              |

### Key Constants (`config/constants.py`)

| Constant                          | Value | Purpose                                  |
| --------------------------------- | ----- | ---------------------------------------- |
| `QUALITY_THRESHOLD`               | 0.8   | Minimum score to pass quality check      |
| `MAX_QUALITY_RETRIES`             | 2     | Max analyze → quality_check loops        |
| `MAX_SEARCH_QUERIES`              | 5     | Max Tavily queries per search phase      |
| `MAX_SEARCH_RESULTS_PER_QUERY`    | 4     | Results returned per Tavily query        |
| `MAX_SCRAPED_CHARS`               | 8000  | Truncation limit for scraped website text|
| `MAX_SEARCH_RESULTS_FOR_PROMPT`   | 10    | Max search results fed to LLM prompt     |
| `MAX_NODE_RETRIES`                | 2     | Retry attempts for external API calls    |
| `RETRY_BASE_DELAY`               | 1.5s  | Base delay for exponential backoff       |

---

## Deployment

### Local Development

```bash
# Backend
cd backend
cp .env.example .env           # Configure API keys
pip install -r requirements.txt
python main.py                 # Runs on :8000 with hot-reload

# Frontend
cd frontend
npm install
npm start                      # Runs on :3000 with CRA dev server
```

### Infrastructure Requirements

| Service       | Port  | Purpose                                         |
| ------------- | ----- | ----------------------------------------------- |
| PostgreSQL    | 5432  | Primary data store (database: `research_copilot`) |
| Redis         | 6379  | Caching / session state                          |
| Backend       | 8000  | FastAPI + Uvicorn (async)                        |
| Frontend      | 3000  | React dev server                                 |

### Production Considerations

- **Database migrations**: Use Alembic instead of `create_all()` auto-migration.
- **API docs**: `/docs` and `/redoc` are disabled when `ENV=production`.
- **CORS**: Restrict `CORS_ORIGINS` to the actual frontend domain.
- **Secrets**: Use a secrets manager instead of `.env` files.
- **Scaling**: The workflow runs as a FastAPI `BackgroundTask` — for horizontal scaling, consider moving to Celery or a task queue.
