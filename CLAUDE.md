# Lazo Agent — CLAUDE.md

AI-powered customer service platform for Lazo (retail stores + Shopify e-commerce).

## Project Overview

Lazo Agent is a multi-channel customer service platform that combines an AI assistant with a human operator CRM. The AI handles customer inquiries using a knowledge base (RAG) and Shopify integration, escalating to human agents when needed. When no agents are online, conversations are captured in an inbox system with contact data for follow-up.

**Business context**: Lazo operates retail stores and an online Shopify store. Agents are NOT available 24/7, making the inbox system critical for capturing customer needs during off-hours.

## Architecture

### Tech Stack
- **Backend**: Python 3.13, FastAPI, SQLAlchemy (async + asyncpg), PostgreSQL 16, Redis 7
- **AI**: LangGraph + LangChain, Anthropic Claude (primary), OpenAI (fallback/embeddings)
- **Observability**: Langfuse (prompt management + tracing), Sentry (errors)
- **Channels**: Twilio (WhatsApp), Meta (Facebook/Instagram/WhatsApp Cloud API), Web Chat (WebSocket), Email (SMTP/IMAP)
- **E-commerce**: Shopify Admin API
- **CRM**: React + TypeScript + Tailwind (Vite SPA, served from FastAPI static)
- **Deployment**: Render (or Docker Compose locally)

### High-Level Data Flow
```
Customer → Channel (WhatsApp/Web/FB/IG/Email)
         → Webhook/WebSocket
         → Thread System (find or create thread)
         → AI Agent (LangGraph)
             ├── Knowledge Base (pgvector RAG)
             ├── Shopify (order lookup)
             ├── Escalation → Online Agent (WebSocket) OR Inbox (contact capture)
             └── Response → Channel (outbound delivery)
```

### Directory Structure
```
lazoagent/
├── app/
│   ├── main.py              # FastAPI app, lifespan, middleware, routes
│   ├── config.py             # pydantic-settings v2, all env vars
│   ├── api/                  # FastAPI routers
│   │   ├── __init__.py       # Router aggregation
│   │   ├── auth.py           # JWT login/logout/register
│   │   ├── threads.py        # Thread CRUD + message creation + AI processing
│   │   ├── escalation.py     # Escalation management
│   │   ├── inbox.py          # Inbox items (offline follow-ups)
│   │   ├── knowledge.py      # Knowledge base CRUD + search
│   │   ├── channels.py       # Channel management
│   │   ├── shopify.py        # Shopify order lookup (CRM-facing)
│   │   ├── analytics.py      # Dashboard metrics
│   │   ├── operators.py      # Operator management
│   │   ├── health.py         # Health checks
│   │   ├── websockets.py     # WS endpoints (thread + global CRM)
│   │   └── webhooks/         # External service webhooks
│   │       ├── twilio.py     # WhatsApp via Twilio
│   │       ├── meta.py       # Facebook/Instagram/WhatsApp Cloud API
│   │       └── shopify_wh.py # Shopify order events
│   ├── core/                 # Infrastructure layer
│   │   ├── database.py       # Async SQLAlchemy engine + sessions
│   │   ├── redis.py          # Redis client with graceful degradation
│   │   ├── security.py       # JWT, password hashing, webhook verification
│   │   ├── websocket_manager.py  # WS connections + Redis pub/sub
│   │   ├── exceptions.py     # Structured exception hierarchy
│   │   └── agents/           # AI agent system
│   │       ├── graph.py      # LangGraph definition (START → agent ↔ tools → END)
│   │       ├── state.py      # AgentState TypedDict + message sanitization
│   │       ├── nodes.py      # Agent node + tool node + routing logic
│   │       ├── bridge.py     # Entry point for all channels → AI processing
│   │       ├── llm.py        # Multi-provider LLM factory (Anthropic/OpenAI)
│   │       ├── prompt_registry.py  # Langfuse prompts with local fallback
│   │       └── tools/        # LangChain tools
│   │           ├── knowledge_tools.py   # search_knowledge_base
│   │           ├── shopify_tools.py     # check_order_status, get_order_history
│   │           ├── escalation_tools.py  # escalate_to_agent, capture_contact_info
│   │           └── common_tools.py      # thread_complete
│   ├── models/               # SQLAlchemy models (PostgreSQL)
│   │   ├── base.py           # Base, TimestampMixin, UUIDMixin
│   │   ├── customer.py       # Customer (contact data, Shopify link)
│   │   ├── operator.py       # Operator (agent) + OperatorLog
│   │   ├── channel.py        # Channel types + operator_channels M2M
│   │   ├── thread.py         # Thread (active/escalated/taken/inbox/closed)
│   │   ├── message.py        # Messages (customer/assistant/operator/system)
│   │   ├── escalation.py     # Escalation + EscalationNote
│   │   ├── inbox.py          # InboxItem (offline follow-up with SLA)
│   │   ├── knowledge.py      # KnowledgeDocument + KnowledgeChunk (pgvector)
│   │   └── shopify.py        # ShopifyOrder cache + WebhookLog
│   ├── schemas/              # Pydantic request/response models
│   ├── services/             # Business logic layer
│   │   ├── shopify_service.py     # Shopify Admin API client
│   │   ├── knowledge_service.py   # RAG: upload, chunk, embed, search
│   │   ├── escalation_service.py  # Route to agent or inbox
│   │   ├── inbox_service.py       # Inbox CRUD + SLA tracking
│   │   ├── channel_service.py     # Outbound message delivery
│   │   ├── operator_service.py    # Login/logout/status management
│   │   └── analytics_service.py   # Metrics computation
│   ├── middleware/           # CORS, rate limiting
│   ├── prompts/              # Local prompt files (Langfuse fallback)
│   ├── templates/            # Email templates
│   └── static/               # Built CRM SPA files
├── alembic/                  # Database migrations
├── crm/                      # React CRM SPA (Vite + TypeScript + Tailwind)
├── tests/                    # Pytest test suite
├── scripts/                  # Maintenance scripts
├── docker-compose.yml        # Local development (PostgreSQL + Redis + API)
├── Dockerfile                # Production container
├── render.yaml               # Render Blueprint deployment
└── requirements.txt          # Python dependencies
```

## Key Concepts

### Thread Lifecycle
```
ACTIVE → AI is handling the conversation
  ├── ESCALATED → Agent is online, waiting for pickup
  │     └── TAKEN → Agent has taken over, AI is silent
  ├── INBOX → No agent online, contact captured for follow-up
  └── CLOSED → Resolved (by AI or agent)
```

### Escalation Flow
1. AI calls `escalate_to_agent` tool (or auto-escalates on error)
2. System checks for online operators
3. **Agent online** → Create Escalation record, set thread to ESCALATED, notify via WebSocket
4. **No agent** → AI asks for contact info, calls `capture_contact_info`, creates InboxItem with SLA deadline
5. When agent logs in, they see pending inbox items and escalations

### Knowledge Base (RAG)
1. Admin uploads document via CRM → `KnowledgeDocument` created
2. Background task chunks text (1000 char chunks, 200 overlap)
3. OpenAI generates embeddings → stored in `KnowledgeChunk.embedding` (pgvector)
4. AI tool `search_knowledge_base` does cosine similarity search
5. Results injected into agent context for response generation

### LangGraph Agent
Simple but effective graph: `START → agent → [tools → agent]* → END`
- Single agent node (no intent routing — simpler than Nexus)
- Tools: knowledge search, Shopify orders, escalation, contact capture
- Circuit breaker: 5 failures → open for 60s → auto-escalate
- Langfuse callbacks for full LLM trace observability

### Prompt Management
- **Primary**: Langfuse (production label, 60s cache)
- **Fallback**: Local `.md` files in `app/prompts/`
- **Security**: Prompt injection detection + input sanitization
- **Context**: Dynamic injection of datetime, language, channel, customer info

## Commands

### Development
```bash
# Start infrastructure (PostgreSQL + Redis)
docker compose up db redis -d

# Create virtual environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Copy environment config
cp .env.example .env  # Edit with your API keys

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 3000

# Run tests
pytest

# Run linter
ruff check app/
```

### Docker (full stack)
```bash
docker compose up --build
# API at http://localhost:3000
# Docs at http://localhost:3000/api/docs
```

### Database Migrations
```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "description of change"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

### Deployment (Render)
Push to main branch triggers auto-deploy. Manual:
```bash
render deploy
```

## Conventions

### Code Style
- Python 3.13+ features welcome (type hints, match statements, etc.)
- Async everywhere — all DB operations, HTTP calls, and service methods are async
- Use `from __future__ import annotations` in all files
- Services are singletons instantiated at module level
- Models use UUID primary keys and TimestampMixin for created_at/updated_at
- JSONB columns use `MutableDict.as_mutable(JSONB)` for in-place mutation detection

### Naming
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- API routes: kebab-case URL paths, snake_case query params
- Database tables: plural `snake_case` (e.g., `inbox_items`, `knowledge_chunks`)
- Enums: `PascalCase` class, `UPPER_CASE` values

### Error Handling
- Use the exception hierarchy in `app/core/exceptions.py`
- Services raise domain exceptions; API routes catch and return HTTP errors
- Background tasks use fire-and-forget (`asyncio.create_task`) for non-critical operations
- Circuit breaker in bridge.py auto-escalates on repeated AI failures

### API Patterns
- All protected routes require JWT via `Depends(get_current_operator)`
- Pagination: `limit` + `offset` query params, response includes `total`
- List endpoints return `{"items": [...], "total": N}` or named lists
- Webhook endpoints verify signatures before processing
- WebSocket endpoints at `/ws/{thread_id}` and `/ws/global`

### Database
- Always use async sessions (`AsyncSession`)
- Use `get_db_context()` context manager outside FastAPI routes
- pgvector for knowledge base embeddings (cosine similarity: `<=>`)
- All models in `app/models/` and re-exported from `app/models/__init__.py`

### Testing
- Pytest with `pytest-asyncio` (auto mode)
- Use `httpx.AsyncClient` with `ASGITransport` for API tests
- Test files mirror source structure: `tests/test_api/`, `tests/test_services/`

## Environment Variables

See `.env.example` for the full list. Critical ones:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection (asyncpg) |
| `REDIS_URL` | No | Redis (graceful degradation if missing) |
| `SECRET_KEY` | Yes | JWT signing key |
| `ANTHROPIC_API_KEY` | Yes | Primary LLM provider |
| `OPENAI_API_KEY` | Yes | Embeddings + fallback LLM |
| `LANGFUSE_PUBLIC_KEY` | No | Prompt management + tracing |
| `LANGFUSE_SECRET_KEY` | No | Prompt management + tracing |
| `SHOPIFY_STORE_URL` | No | Shopify store domain |
| `SHOPIFY_ACCESS_TOKEN` | No | Shopify Admin API token |
| `TWILIO_ACCOUNT_SID` | No | WhatsApp via Twilio |
| `TWILIO_AUTH_TOKEN` | No | WhatsApp via Twilio |
| `META_APP_SECRET` | No | Facebook/Instagram/WhatsApp Cloud |

## Common Tasks

### Add a new AI tool
1. Create tool function in `app/core/agents/tools/` with `@tool` decorator
2. Add clear docstring (the LLM reads this to decide when to use it)
3. Import and add to `AGENT_TOOLS` list in `app/core/agents/nodes.py`
4. Add corresponding service method if the tool needs business logic

### Add a new channel
1. Add enum value to `ChannelType` in `app/models/channel.py`
2. Add webhook handler in `app/api/webhooks/`
3. Add delivery method in `app/services/channel_service.py`
4. Register webhook route in `app/api/webhooks/__init__.py`

### Add a new model
1. Create model file in `app/models/`
2. Import in `app/models/__init__.py`
3. Run `alembic revision --autogenerate -m "add model_name"`
4. Review and apply: `alembic upgrade head`

### Modify the AI prompt
1. Edit in Langfuse (preferred) — changes take effect within 60s
2. Or edit `app/prompts/base_agent.md` (local fallback)
3. For structural changes to prompt composition, edit `app/core/agents/prompt_registry.py`

## Design Decisions

### Why single agent instead of multi-agent (like Nexus)?
Lazo's needs are simpler — general customer service + order tracking. No need for sales/support/transfer specialization. A single agent with the right tools is more maintainable and less latency.

### Why pgvector instead of a dedicated vector DB?
Keeps the stack simple — one database for everything. For Lazo's scale (thousands of knowledge chunks, not millions), pgvector is performant enough. Easy to migrate to Pinecone/Weaviate later if needed.

### Why inbox system instead of just queue?
Agents aren't 24/7. The inbox captures contact data (email/phone) so agents can proactively follow up later, even through a different channel. SLA tracking ensures nothing falls through the cracks.

### Why Langfuse for prompts?
Versioned prompts with production labels mean you can A/B test prompt changes, roll back instantly, and trace exactly which prompt version generated which response. The local fallback ensures the system works even if Langfuse is down.
