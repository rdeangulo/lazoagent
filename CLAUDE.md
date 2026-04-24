# Lazo Agent — CLAUDE.md

AI Agent Training Platform. Create, train, and deploy AI agents with their own personas, tools, and knowledge bases. External CRMs call `POST /api/v1/chat` to get a response from a configured agent.

## Project Overview

This repo is the **headless brain** — given `agent_id + message + thread_id`, it returns `{response, tool_calls}`. The conversation management layer (threads, channels, escalation, inbox, operator CRM) lives in a **separate system** that calls into this one.

**What lives here:**
- Admin authoring: creating agents, editing system prompts, uploading knowledge docs, configuring tools, picking LLM provider/model.
- Runtime: a LangGraph loop that takes a message, runs the agent with its configured tools, returns a response.
- Knowledge base (pgvector RAG) attached to agents.
- Training playground for testing agent behavior before shipping.
- API-key-authenticated inference endpoint for external callers.

**What does NOT live here:**
- Thread/channel management (WhatsApp, web chat, email, WebSocket)
- Human operator CRM, escalation flows, inbox, SLA tracking
- Customer contact data beyond what's passed in `context` per request

## Architecture

### Tech Stack
- **Backend**: Python 3.13, FastAPI, SQLAlchemy (async + asyncpg), PostgreSQL 16 + pgvector, Redis 7
- **AI orchestration**: LangGraph + LangChain
- **LLM providers**: OpenAI (default) and Anthropic (both supported; per-agent config)
- **Embeddings**: OpenAI `text-embedding-3-small` (1536 dims)
- **Prompt management**: optional Langfuse (agent can reference `langfuse_prompt_name` to fetch prompt at runtime)
- **External integrations**: Shopify (Admin GraphQL + Storefront MCP), B2Chat (historical import)
- **Deployment**: Docker / Render

### High-level request flow
```
External CRM
  │ POST /api/v1/chat  { agent_id, message, thread_id, context }
  │ X-API-Key: ...
  ▼
Inference API  ── resolves Agent record (agent_id/slug)
  │
  ▼
Agent bridge  ── builds agent_config from the Agent row
  │             (system_prompt, llm_provider, llm_model, enabled_tools, …)
  ▼
LangGraph   START → agent → [tools → agent]* → END
  │
  ├─ agent_node       ── binds only the tools listed in enabled_tools
  │                      to the LLM; invokes once per turn
  └─ tool_node        ── executes whichever tool the LLM called
                         (knowledge search, Shopify, product lookup, …)
  ▼
ChatResponse  { response, tool_calls, agent_id, thread_id }
```

### Directory Structure
```
lazoagent/
├── app/
│   ├── main.py                # FastAPI app + lifespan
│   ├── config.py              # pydantic-settings v2, all env vars
│   ├── api/
│   │   ├── __init__.py        # Router aggregation (mounted at /api)
│   │   ├── auth.py            # Admin login (JWT)
│   │   ├── agents.py          # Agent CRUD + config
│   │   ├── knowledge.py       # Document upload / chunking / search
│   │   ├── training.py        # Test playground endpoint
│   │   ├── api_keys.py        # API keys for external callers
│   │   ├── inference.py       # POST /v1/chat (external integration point)
│   │   ├── b2chat.py          # B2Chat historical conversation ingestion
│   │   └── health.py
│   ├── core/
│   │   ├── database.py        # Async SQLAlchemy engine + sessions
│   │   ├── redis.py           # Graceful-degradation Redis client
│   │   ├── security.py        # JWT, API-key lookup, password hashing
│   │   └── agents/
│   │       ├── bridge.py      # process_message(): single entry into the graph
│   │       ├── graph.py       # LangGraph definition
│   │       ├── state.py       # AgentState + message sanitization
│   │       ├── nodes.py       # agent_node + tool_node + TOOL_REGISTRY
│   │       ├── llm.py         # Anthropic/OpenAI factory
│   │       ├── prompt_registry.py  # Langfuse-with-local-fallback
│   │       └── tools/
│   │           ├── knowledge_tools.py          # search_knowledge_base
│   │           ├── common_tools.py             # thread_complete
│   │           ├── shopify_tools.py            # check_order_status
│   │           └── shopify_storefront_tools.py # search_products, get_product_details, search_policies
│   ├── models/
│   │   ├── base.py            # Base + TimestampMixin + UUIDMixin
│   │   ├── admin.py           # Admin user (JWT login)
│   │   ├── agent.py           # Agent (persona, tools, LLM config)
│   │   ├── api_key.py         # External-caller API keys
│   │   ├── knowledge.py       # KnowledgeDocument + KnowledgeChunk (pgvector)
│   │   └── training.py        # TrainingSession (playground records)
│   ├── services/
│   │   ├── agent_service.py              # Agent CRUD + config resolution
│   │   ├── knowledge_service.py          # Upload / chunk / embed / search
│   │   ├── training_service.py           # Playground runs
│   │   ├── b2chat_service.py             # B2Chat API client
│   │   ├── b2chat_ingestion.py           # Import conversations into knowledge
│   │   ├── shopify_service.py            # Shopify Admin GraphQL (orders)
│   │   └── shopify_storefront_service.py # Shopify Storefront MCP (catalog, policies)
│   ├── schemas/                # Pydantic request/response models
│   ├── middleware/             # CORS, rate limiting
│   ├── prompts/                # Local prompt fallback when Langfuse unavailable
│   └── static/                 # Admin UI build (if present)
├── alembic/                    # Database migrations
├── scripts/
│   ├── shopify_oauth_install.py  # One-shot OAuth helper for capturing offline Shopify token
│   └── refresh_shopify_token.sh  # Fallback CLI token refresher (not needed for offline tokens)
├── tests/
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Key Concepts

### Agent
The central entity (`app.models.agent.Agent`). Each agent has:
- `name`, `slug`, `status` (draft/active/paused/archived)
- `system_prompt` (or `langfuse_prompt_name` to fetch from Langfuse)
- `llm_provider` (`openai` or `anthropic`), `llm_model`, `temperature`, `max_tokens`
- `enabled_tools` — JSONB list of tool names; only these are bound to the LLM at runtime
- `knowledge_doc_types` — optional filter restricting which documents this agent can search
- `knowledge_search_limit`, `knowledge_score_threshold` — RAG tuning

The Agent row is the full configuration; the runtime never reads hardcoded constants for persona or tools.

### LangGraph runtime
Simple loop defined in `app/core/agents/graph.py`:
```
START → agent → tools_condition ── END
                │
                └─ tools → agent (loop)
```
- `agent_node` reads `state.meta_data["agent_config"]`, picks tools from `TOOL_REGISTRY`, binds them to the LLM, invokes.
- `tool_node` (ToolNode) executes the requested tool and loops back.
- No hardcoded intent routing — the LLM decides when to call tools based on tool docstrings.
- Circuit breaker in `bridge.py`: 5 failures → open for 60s → auto-degrades.

### Tool Registry
Defined in `app/core/agents/nodes.py`. Currently:

| Name | Purpose |
|---|---|
| `search_knowledge_base` | RAG over uploaded documents (pgvector cosine similarity) |
| `check_order_status` | Shopify Admin GraphQL — order lookup by name or email |
| `search_products` | Shopify Storefront MCP — live product catalog search |
| `get_product_details` | Shopify Storefront MCP — detail + variant-specific lookup |
| `search_policies` | Shopify Storefront MCP — shop policies & FAQ |
| `thread_complete` | Mark conversation resolved |

To add a tool: create a `@tool`-decorated async function in `app/core/agents/tools/`, register it in `TOOL_REGISTRY`, then any agent can opt in by adding its name to `enabled_tools`.

### Knowledge Base (RAG)
- Admin uploads a document → `KnowledgeDocument` row
- Background task chunks (1000 char / 200 overlap), embeds via OpenAI, stores vector in `KnowledgeChunk.embedding` (pgvector)
- `search_knowledge_base` tool does cosine similarity (`<=>` operator) filtered by the agent's `knowledge_doc_types` if set

### Shopify Integration (current setup for LAZO)
Two surfaces:
1. **Admin GraphQL API** (`app/services/shopify_service.py`) — authenticated with an offline `shpca_…` access token obtained via the Peregrino Partner org's Custom Distribution app. Cost-aware retry on `THROTTLED` responses.
2. **Storefront MCP** (`app/services/shopify_storefront_service.py`) — public `/api/mcp` JSON-RPC endpoint, no auth needed. Used for customer-facing catalog/policy queries.

The OAuth install for the Admin token is a one-shot via `scripts/shopify_oauth_install.py`. If it ever needs re-running, see the script docstring.

## Commands

### Development
```bash
# Infra
docker compose up db redis -d

# Venv + deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Env
cp .env.example .env   # Fill in API keys

# DB
alembic upgrade head

# Dev server
uvicorn app.main:app --reload --port 3000

# Tests
pytest

# Lint
ruff check app/
```

### Docker (full stack)
```bash
docker compose up --build
# API at http://localhost:3000
# Docs at http://localhost:3000/api/docs
```

### Migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

## Conventions

### Code Style
- Python 3.13+ features welcome (type hints, match, etc.)
- Async everywhere
- `from __future__ import annotations` at top of files
- Services instantiated as module-level singletons
- Models use UUID primary keys + TimestampMixin
- JSONB columns via `MutableDict.as_mutable(JSONB)` / `MutableList.as_mutable(JSONB)` for in-place mutation detection

### Naming
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Database tables: plural `snake_case` (`agents`, `knowledge_chunks`)

### Error handling
- Services raise; API routes catch and return HTTP errors
- Background tasks use fire-and-forget (`asyncio.create_task`) for non-critical work
- Circuit breaker in `bridge.py` prevents runaway failures to the LLM provider

### Database
- Always async sessions (`AsyncSession`)
- `get_db_context()` for non-FastAPI consumers
- pgvector for embeddings — cosine similarity via `<=>`

## Environment Variables

See `.env.example`. Minimum to run:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres (asyncpg) |
| `DATABASE_URL_SYNC` | Yes | Postgres (sync, for Alembic) |
| `REDIS_URL` | No | Redis (gracefully absent) |
| `SECRET_KEY` | Yes | JWT signing |
| `OPENAI_API_KEY` | Yes* | Default LLM + embeddings |
| `ANTHROPIC_API_KEY` | Yes* | If any agent uses provider=anthropic |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | No | Remote prompt management + tracing |
| `SHOPIFY_STORE_URL` | No | Shopify `*.myshopify.com` domain |
| `SHOPIFY_ACCESS_TOKEN` | No | Offline `shpca_…` token for Admin API |
| `SENTRY_DSN` | No | Error tracking |

\* At least one LLM provider key is required.

## Common Tasks

### Add a new AI tool
1. Write a `@tool`-decorated async function in `app/core/agents/tools/` with a clear docstring (the LLM reads it to decide when to invoke).
2. Register it in `TOOL_REGISTRY` in `app/core/agents/nodes.py`.
3. Add the tool name to the relevant agents' `enabled_tools` list.

### Add a new Agent (via DB)
Typically done through the admin UI. For one-off/SQL:
```sql
INSERT INTO agents (id, name, slug, status, system_prompt, llm_provider, llm_model, enabled_tools)
VALUES (gen_random_uuid(), 'LAZO Customer Service', 'lazo-cs', 'active',
        '...', 'openai', 'gpt-4.1-mini',
        '["search_products","check_order_status","search_policies","search_knowledge_base","thread_complete"]'::jsonb);
```

### Modify agent persona / system prompt
- **Preferred**: edit in Langfuse if `langfuse_prompt_name` is set on the Agent — changes propagate within the prompt cache TTL.
- **Otherwise**: update `agents.system_prompt` directly (admin UI or SQL).

### Call the inference API from an external CRM
```bash
curl -X POST http://localhost:3000/api/v1/chat \
  -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_slug": "lazo-cs",
    "message": "dónde está mi pedido?",
    "thread_id": "customer-123",
    "language": "es",
    "context": {"customer_email": "x@y.com"}
  }'
```

Response includes `{response, tool_calls, agent_id, thread_id}`. The CRM decides what to do with it (deliver to channel, escalate, capture lead, etc.).

## Design Decisions

### Why headless (no CRM/escalation here)?
Separation of concerns. The conversation management platform handles threading, channels, operator handoff, and SLA — which are operationally complex and often org-specific. This repo stays focused on agent authoring + inference so both sides can evolve independently.

### Why per-agent config in the DB (not YAML)?
Non-technical users can create/iterate on agents via the admin UI without code deploys. The tool names, prompt, and LLM choice are all data.

### Why LangGraph's simple agent loop instead of explicit intent routing?
Tool docstrings + a strong system prompt let the LLM route itself. Adding an intent-classifier layer is extra latency + failure points for negligible quality gain at current tool counts. If the tool surface grows substantially (>15), revisit.

### Why pgvector instead of a dedicated vector DB?
Single database to operate. For target scale (tens of thousands of chunks per tenant), pgvector is fast enough. Migrate to a specialized store only if/when this stops being true.

### Why two Shopify clients (Admin GraphQL and Storefront MCP)?
They do different things. Admin GraphQL needs auth and surfaces order/customer data. Storefront MCP is public and surfaces the shopper-facing catalog. Mixing them into one client would conflate two permission models.
