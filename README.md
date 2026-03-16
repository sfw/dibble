# Dibble

This repository now includes a working MVP backend slice for the revised adaptive learning platform.

## What Exists

- FastAPI application in `src/dibble/`
- SQLite-backed persistence for learner profiles and curriculum resources
- Learner profile model aligned to the revised spec's richer profile design
- Observation-driven affective, cognitive-load, and metacognitive state inference folded into the learner profile and adaptive routing decisions
- Adaptive routing service with curriculum/safety guardrails plus Thompson-style action selection for step-back, reteach, targeted practice, and stretch decisions
- Retrieval-grounded generation pipeline split into retriever, router, provider, and validator services
- Default retriever now uses a persistent SQLite-backed embedding index plus lexical/metadata scoring for better free-text curriculum matching
- Default provider now supports an OpenAI-compatible chat completion endpoint with configurable ordered, round-robin, or latency-aware provider selection, secondary-provider failover, circuit-breaker protection, persistent provider-health warm starts, and automatic mock fallback when no model credentials are configured
- Prompt template selection is now versioned and variant-aware, with deterministic experiment bucketing for generation and Socratic assessment probes, and prompt metadata persisted on generated responses
- Socratic assessment probes can now optionally use recent audit outcomes to adaptively prefer the stronger-performing prompt variant instead of only fixed bucketing
- Experimented generation families such as explanations, worked examples, and practice problems can now also use recent content-generation outcomes to adaptively prefer the stronger prompt variant
- The generation-side adaptive selector now weights nearby `learner.observe` outcomes when available, so prompt variants can be nudged by downstream learner response signals instead of only immediate generation quality
- Observations can now optionally carry `generation_id`, content type, and target KC/LO context so downstream calibration can prefer exact or context-compatible matches over loose time proximity
- Generation requests and observations can now also carry `learning_session_id` so prompt calibration can prefer same-session matches without fragmenting the generation cache
- Socratic assessment now uses modular continuous evidence scoring plus an outcome-aware turn policy instead of a last-turn threshold check
- Socratic assessment outcomes now fold back into learner mastery and metacognitive signals so later routing can react to conversational evidence
- Generation prompt calibration can now also learn from same-session Socratic assessment evidence, not just follow-up observation events
- Generation prompt calibration now aggregates the strongest linked observation and Socratic follow-ups into small session traces instead of relying on only one downstream event
- Generation prompt calibration can now also look across later generated steps in the same learning session and fold those downstream outcomes back into the earlier prompt variant
- Generation prompt calibration now turns those linked traces into explicit run-level summaries with outcome scores, confidence, and positive/mixed/negative calibration signals so selector decisions rely less on raw event-window counts alone
- The production router is now wrapped with a calibration layer that reads recent same-target run summaries, exposes a route-level calibration summary, and conservatively raises or relaxes support when durable evidence is clearly negative or positive
- The learner observation pipeline now reuses those run summaries to conservatively nudge metacognitive state updates, so stored confidence calibration, help-seeking, and self-monitoring rely a little less on single-observation heuristics alone
- Those run summaries are now also persisted as `learning.run.summary` audit events when new observation or Socratic evidence arrives, and downstream calibration services, prompt selection, and prompt telemetry prefer those durable summaries before falling back to raw event-window reconstruction
- The backend now also compacts recent matching run summaries into cross-session `learning.calibration.profile` audit events, and the router prefers those profile snapshots before falling back to per-run summaries or raw trace reconstruction
- Default validation now checks for missing grounding, missing instructional content, weak curriculum alignment, instruction-level grounding coverage, grade-band readability risk, accessibility density, unsafe language, and simple math errors
- Adaptive decision and generation endpoints now write audit events and expose simple local observability metrics
- Observability metrics now include durable provider-health telemetry for upstream failures and circuit-open state
- Streaming generation is available over server-sent events for incremental `start`, `delta`, and `complete` delivery, and can consume real upstream OpenAI-compatible chat streams when configured
- Generated content is now persisted with quality/provenance metadata and reused through a lightweight SQLite-backed generation cache
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
- `GET /api/learners`
- `PUT /api/learners/{student_id}/profile`
- `GET /api/learners/{student_id}/profile`
- `POST /api/learners/{student_id}/observations`
- `GET /api/learners/{student_id}/state`
- `GET /api/learners/{student_id}/summary`
- `PUT /api/curriculum/resources/{resource_id}`
- `GET /api/curriculum/resources`
- `PUT /api/knowledge-components/{kc_id}`
- `GET /api/knowledge-components`
- `GET /api/knowledge-components/{kc_id}/prerequisites`
- `POST /api/router/decide`
- `POST /api/content/generate`
- `POST /api/content/warm`
- `POST /api/explanations/generate`
- `POST /api/problems/generate`
- `POST /api/worked-examples/generate`
- `POST /api/assessments/socratic`
- `GET /api/assessments/socratic/{session_id}`
- `POST /api/remedial/trigger`
- `POST /api/llm/stream`
- `GET /api/auth/me`
- `POST /api/auth/token`
- `POST /api/auth/token/refresh`
- `POST /api/auth/token/revoke`
- `GET /api/audit/events`
- `GET /api/observability/metrics`

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
export DIBBLE_LLM_CIRCUIT_BREAKER_THRESHOLD=2
export DIBBLE_LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS=30
export DIBBLE_LLM_SELECTION_STRATEGY=ordered
export DIBBLE_LLM_ALLOW_MOCK_FALLBACK=true
export DIBBLE_PROMPT_LIBRARY_VERSION=1.0
export DIBBLE_PROMPT_EXPERIMENT_ENABLED=false
export DIBBLE_PROMPT_ADAPTIVE_SELECTION_ENABLED=false
export DIBBLE_PROMPT_VARIANT=
```

If the primary LLM provider fails, the default provider can fail over to the configured secondary provider before falling back to the deterministic mock provider for local development. Repeated failures can temporarily open a circuit for the failing provider so the system stops retrying it until the cooldown window passes. `DIBBLE_LLM_SELECTION_STRATEGY=ordered` preserves explicit primary failback, `round_robin` balances across currently healthy upstream providers, and `latency_aware` gives each healthy provider an initial sample before favoring the strongest recent success-rate and latency profile. Provider-health telemetry is persisted in SQLite and now warms those routing decisions back into memory when the app restarts. The prompt layer now selects named templates like `micro_explanation.baseline` or `worked_example.guided_reflection`, tracks their version, and can deterministically bucket supported content types into a simple experiment when `DIBBLE_PROMPT_EXPERIMENT_ENABLED=true`. If `DIBBLE_PROMPT_ADAPTIVE_SELECTION_ENABLED=true`, Socratic assessment probes and the main experimented generation families can also use recent audit outcomes to prefer the better-performing prompt variant once enough evidence exists, with generation-side calibration now summarized into explicit run outcomes plus confidence-weighted positive/mixed/negative signals before selector ranking and router-side calibration now consuming those same summaries before final support selection. When configured, the stream endpoint can consume upstream OpenAI-compatible chat SSE deltas and translate NDJSON chunk output into Dibble block-stream events. The stream endpoint emits server-sent events named `start`, `delta`, and `complete`.

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
export DIBBLE_GENERATION_CACHE_TTL_SECONDS=3600
```

When auth is enabled, all API routes except `GET /health` require a valid key in the configured header. If `DIBBLE_AUTH_PRINCIPALS` is set, keys resolve to named principals and roles. Route access is split so viewers can read, editors can mutate/generate, and admins can access audit and observability endpoints. If `DIBBLE_AUTH_TOKEN_SECRET` is set, authenticated principals can exchange API-key access for signed bearer tokens via `POST /api/auth/token`, rotate them with `POST /api/auth/token/refresh`, and revoke sessions with `POST /api/auth/token/revoke`.

Generated responses now include `generation_id` plus `generation_metadata` with validation status, quality score, provider provenance, prompt-template provenance, latency, and cache-hit state. The current revised-spec generation routes wrap that response in a `GeneratedContent` record so the API contract aligns with the authoritative planning package. `POST /api/content/warm` can proactively pre-generate the same content shape and prime the SQLite-backed cache for expected remedial or practice requests. Observability snapshots now summarize prompt-template usage counts, Socratic assessment aggregates such as evidence-score averages and profile-update counts, per-template/style Socratic prompt performance summaries, and generation prompt-performance summaries that combine immediate quality with explicit run-level outcome summaries, confidence-weighted calibration signals, persisted-summary coverage, aggregated learner-observation traces, same-session Socratic traces, and later cross-generation session outcomes, including average trace depth, so prompt experiments and conversational assessment behavior are inspectable without digging through raw audit events. Those same durable run summaries are now also written into the audit log as first-class `learning.run.summary` events, compacted into cross-session `learning.calibration.profile` events, and reused by prompt calibration and route calibration before the system falls back to raw window reconstruction.

Knowledge Components are now first-class persisted entities with prerequisite links, and the remedial trigger uses that graph plus misconception signals to step back through weaker prerequisite KCs before returning to the requested target. Remediation responses now include the detected misconception signals and rationale in `request_context`, and audit logs capture the same planning metadata. The learner API also now accepts observed interaction signals and infers affective state, cognitive load, and metacognitive state back into the stored profile, including confidence calibration and help-seeking behavior. Observations can now carry task context such as `task_type`, `support_level`, `expected_duration_ms`, and optional linkage fields such as `generation_id`, `learning_session_id`, `observed_content_type`, and target KC/LO ids, so an assessment attempt is interpreted differently from a scaffolded worked example and downstream prompt calibration can prefer exact, same-session, or context-compatible observation matches. Those same linkage fields now also let learner-state updates reuse recent same-target run summaries before persisting metacognitive state, so confidence calibration and help-seeking are not driven only by the latest raw observation window. The router now uses those metacognitive signals to hold back stretch when the learner still appears to need modeled support, and it now also returns a calibration summary on route decisions so recent same-target run outcomes can conservatively increase or relax scaffolding before delivery. The generation path also supports first-class worked-example fading and practice difficulty bands through the same unified engine, and the generic `/api/content/generate` path can now auto-select a worked example when learner-state signals favor modeled support before freer explanation. There is also now a persisted conversational assessment flow at `POST /api/assessments/socratic` that scores the current learner response before choosing the next prompt, exposes continuous evidence dimensions such as lexical alignment, reasoning signal, confidence alignment, progression, and misconception risk, and uses an outcome-aware prompt-style policy such as `diagnostic`, `clarification`, `scaffolded_step_back`, or `transfer_check` across multi-turn sessions. Strong Socratic turns now also update target KC/LO mastery plus metacognitive readiness in the stored profile so later router decisions can respond to conversational evidence rather than treating assessment as an isolated side channel, and those same-session assessment outcomes can now feed generation prompt calibration as part of an aggregated downstream trace that can continue across later generated steps in the same learning session. Sessions can be reloaded with `GET /api/assessments/socratic/{session_id}`. Observability snapshots now include cache-hit counts, warm-request totals, generated-content cache inventory, prompt-template usage, and generation prompt-performance summaries so pre-generation and prompt experiments are visible without extra instrumentation.

## Suggested Next Build Steps

1. Replace or augment SQLite with production persistence such as Redis/PostgreSQL or Redis/Cassandra.
2. Replace the SQLite embedding cache with a production vector store and background indexing pipeline while keeping the retriever plugin contract stable.
3. Calibrate the new learner-state signals with stronger evidence so routing and content-mode selection rely less on heuristics.
4. Extend the new persisted run-summary and calibration-profile layers into broader learner-history adaptation so the system can move from recent cross-session snapshots toward richer long-horizon signals.
