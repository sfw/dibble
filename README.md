# Dibble

This repository now includes a working MVP backend slice for the revised adaptive learning platform.

## What Exists

- FastAPI application in `src/dibble/`
- SQLite-backed persistence for learner profiles and curriculum resources
- Learner profile model aligned to the revised spec's richer profile design
- Adaptive routing service with curriculum/safety guardrails plus Thompson-style action selection for step-back, reteach, targeted practice, and stretch decisions
- Retrieval-grounded generation pipeline split into retriever, router, provider, and validator services
- Default retriever now uses a persistent SQLite-backed embedding index plus lexical/metadata scoring for better free-text curriculum matching
- Default provider now supports an OpenAI-compatible chat completion endpoint with secondary-provider failover and automatic mock fallback when no model credentials are configured
- Default validation now checks for missing grounding, missing instructional content, weak curriculum alignment, grade-band readability risk, accessibility density, unsafe language, and simple math errors
- Adaptive decision and generation endpoints now write audit events and expose simple local observability metrics
- Streaming generation is available over server-sent events for incremental `start`, `delta`, and `complete` delivery, and can consume real upstream OpenAI-compatible chat streams when configured
- Optional principal-based API key auth with `viewer`/`editor`/`admin` roles can protect every endpoint except `GET /health`
- Signed bearer tokens can be minted, refreshed, and revoked for request-scoped sessions
- Dynamic plugin loading for router, retriever, provider, and validator factories
- API tests covering routing, persistence, retrieval, generation, and fallback behavior

## Run It

Install dependencies:

```bash
env UV_CACHE_DIR=.uv-cache uv sync --group dev
```

Start the API:

```bash
env UV_CACHE_DIR=.uv-cache uv run uvicorn dibble.main:app --reload
```

Run tests:

```bash
env UV_CACHE_DIR=.uv-cache uv run pytest
```

## Current Endpoints

- `GET /health`
- `GET /api/v1/profiles`
- `PUT /api/v1/profiles/{student_id}`
- `GET /api/v1/profiles/{student_id}`
- `GET /api/v1/profiles/{student_id}/summary`
- `PUT /api/v1/curriculum/resources/{resource_id}`
- `GET /api/v1/curriculum/resources`
- `POST /api/v1/adaptive/decide`
- `POST /api/v1/adaptive/generate`
- `POST /api/v1/adaptive/generate/stream`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/token`
- `POST /api/v1/auth/token/refresh`
- `POST /api/v1/auth/token/revoke`
- `GET /api/v1/audit/events`
- `GET /api/v1/observability/metrics`

## Persistence

The app uses SQLite by default and stores data in `dibble.db`.

You can override the database path with:

```bash
export DIBBLE_DATABASE_PATH=/path/to/dibble.db
```

Plugin factories can also be overridden:

```bash
export DIBBLE_ROUTER_PLUGIN=dibble.plugins.defaults.router:build
export DIBBLE_RETRIEVER_PLUGIN=dibble.plugins.defaults.retriever:build
export DIBBLE_PROVIDER_PLUGIN=dibble.plugins.defaults.provider:build
export DIBBLE_VALIDATOR_PLUGIN=dibble.plugins.defaults.validator:build
```

LLM orchestration settings for the default provider:

```bash
export DIBBLE_LLM_API_BASE=https://api.openai.com/v1
export DIBBLE_LLM_API_KEY=...
export DIBBLE_LLM_MODEL=...
export DIBBLE_LLM_TIMEOUT_SECONDS=20
export DIBBLE_LLM_SECONDARY_API_BASE=https://api.openai.com/v1
export DIBBLE_LLM_SECONDARY_API_KEY=...
export DIBBLE_LLM_SECONDARY_MODEL=...
export DIBBLE_LLM_SECONDARY_TIMEOUT_SECONDS=20
export DIBBLE_LLM_ALLOW_MOCK_FALLBACK=true
```

If the primary LLM provider fails, the default provider can fail over to the configured secondary provider before falling back to the deterministic mock provider for local development. When configured, the stream endpoint can consume upstream OpenAI-compatible chat SSE deltas and translate NDJSON chunk output into Dibble block-stream events. The stream endpoint emits server-sent events named `start`, `delta`, and `complete`.

Embedding settings for the default retriever:

```bash
export DIBBLE_EMBEDDING_API_BASE=https://api.openai.com/v1
export DIBBLE_EMBEDDING_API_KEY=...
export DIBBLE_EMBEDDING_MODEL=...
export DIBBLE_EMBEDDING_DIMENSIONS=256
export DIBBLE_EMBEDDING_TIMEOUT_SECONDS=15
export DIBBLE_EMBEDDING_ALLOW_LOCAL_FALLBACK=true
```

If `DIBBLE_EMBEDDING_API_KEY` or `DIBBLE_EMBEDDING_MODEL` is unset, the default retriever uses a deterministic local embedder and stores resource vectors in SQLite for offline development.

Authentication settings:

```bash
export DIBBLE_AUTH_ENABLED=true
export DIBBLE_AUTH_API_KEYS=secret-one,secret-two
export DIBBLE_AUTH_PRINCIPALS=viewer-key:viewer-user:viewer,editor-key:editor-user:editor,admin-key:admin-user:admin
export DIBBLE_AUTH_HEADER_NAME=X-API-Key
export DIBBLE_AUTH_TOKEN_SECRET=replace-me
export DIBBLE_AUTH_TOKEN_ISSUER=dibble
export DIBBLE_AUTH_TOKEN_TTL_SECONDS=3600
export DIBBLE_AUTH_REFRESH_TTL_SECONDS=604800
```

When auth is enabled, all API routes except `GET /health` require a valid key in the configured header. If `DIBBLE_AUTH_PRINCIPALS` is set, keys resolve to named principals and roles. Route access is split so viewers can read, editors can mutate/generate, and admins can access audit and observability endpoints. If `DIBBLE_AUTH_TOKEN_SECRET` is set, authenticated principals can exchange API-key access for signed bearer tokens via `POST /api/v1/auth/token`, rotate them with `POST /api/v1/auth/token/refresh`, and revoke sessions with `POST /api/v1/auth/token/revoke`.

## Suggested Next Build Steps

1. Replace or augment SQLite with production persistence such as Redis/PostgreSQL or Redis/Cassandra.
2. Replace the SQLite embedding cache with a production vector store and background indexing pipeline while keeping the retriever plugin contract stable.
3. Add prompt versioning, richer generation metadata, and provider failover on top of the LLM orchestration layer.
4. Add richer curriculum alignment scoring, domain-specific validators, stronger session management like issuer rotation and per-device controls, and provider health/circuit-breaker behavior on top of the new failover chain.
