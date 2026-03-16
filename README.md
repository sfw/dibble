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
- The backend now also compacts recent matching run summaries into cross-session `learning.progress.profile` audit events so recent-vs-prior run outcome trends become durable learner-history artifacts instead of only request-time calculations
- Router calibration and generation-mode calibration now prefer those persisted progress profiles when available, so live support decisions can react to cross-session `improving` or `declining` trends instead of only current run snapshots
- The backend now also compacts recent matching run summaries into cross-session `learning.strategy.profile` audit events, producing honest heuristic recovery, plateau, relapse, and volatility signals that routing, generation-mode calibration, remediation workflows, learner summaries, and predictive follow-up warming can reuse directly
- The misconception pipeline now also compacts repeated remediation signals into richer `learning.misconception.profile` events with recurrence counts, session counts, and recurrence labels such as `recurring` or `relapsing`, and those durable signals now feed later misconception detection, per-KC misconception disambiguation, and remediation blueprint selection
- Learner-strategy signals now also produce explicit per-KC sequencing decisions such as rebuilding a prerequisite first, holding on the repair target, holding on the target KC, or attempting transfer, and those decisions now shape remediation workflow steps plus predictive follow-up targeting
- Same-session observations and Socratic assessments can now trigger a lightweight live adaptation layer, so the next generation request in the same `learning_session_id` can raise or relax support and update sequencing before the slower cross-session profiles catch up
- `GET /api/learners/{student_id}/summary` now exposes a frontend-ready learner overview with engagement, metacognitive snapshot, latest calibration summary, latest progress trend summary, latest learner-strategy summary, and recent activity counts so the UI does not need to read audit logs directly
- Predictive warming now also has a durable SQLite-backed queue plus an explicit processor path, so anticipated follow-up requests can be scheduled, canceled when new evidence arrives, and processed outside the original generation request when needed
- The predictive follow-up planner is now calibration-aware, so declining practice can warm a worked example instead of a transfer check, stronger remediation progress can warm a transfer probe sooner, and long-horizon learner-strategy signals can now escalate relapse toward prerequisite repair or break a plateau with varied modeled support
- Knowledge Components can now carry catalogued misconception patterns, and the remedial trigger uses those patterns to produce richer misconception signals plus a structured remediation blueprint instead of only a generic step-back wrapper
- Remediation is now session-backed, so `POST /api/remedial/trigger` starts a persisted multi-step workflow and later steps can be reloaded or advanced through dedicated remediation-session endpoints, those sessions now carry learner-strategy context so repeated struggle can keep prerequisite rebuild guidance explicit across steps, and recurring misconception profiles can now pull remediation back toward repeated repair targets instead of treating each attempt as isolated
- The learner observation pipeline now also refreshes cognitive trait estimates such as processing speed, working memory, and spatial reasoning from recent observation patterns, so trait fields are no longer purely static seed data
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
- `POST /api/content/warm/process`
- `POST /api/explanations/generate`
- `POST /api/problems/generate`
- `POST /api/worked-examples/generate`
- `POST /api/assessments/socratic`
- `GET /api/assessments/socratic/{session_id}`
- `POST /api/remedial/trigger`
- `GET /api/remedial/sessions/{session_id}`
- `POST /api/remedial/sessions/{session_id}/advance`
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

Generated responses now include `generation_id` plus `generation_metadata` with validation status, quality score, provider provenance, prompt-template provenance, latency, and cache-hit state. The current revised-spec generation routes wrap that response in a `GeneratedContent` record so the API contract aligns with the authoritative planning package. `POST /api/content/warm` can proactively pre-generate the same content shape and prime the SQLite-backed cache for expected remedial or practice requests, and the live generation path now also performs conservative predictive warming for likely follow-up content such as practice after a worked example or a quick assessment probe after practice. Predictive warmed entries carry durable request-context metadata, reuse the same cache key as later real requests, and are expired when new learner observations or Socratic assessment outcomes change the same learner/session target context. That predictive path now also writes follow-up requests into a durable SQLite queue, uses live route/mode calibration to adapt which follow-up content types are warmed, and exposes `POST /api/content/warm/process` so queued warm tasks can be drained explicitly outside the original generation request when needed. The same persisted cross-session calibration profiles that already influence router support selection now also feed generation-mode calibration, so worked-example fading and practice difficulty can step up or step back one level when recent matching runs are durably positive or negative. When the broader cross-session trend is available, router calibration and generation-mode calibration now prefer persisted `learning.progress.profile` events and can react to `improving` or `declining` trajectory, not just static positive/negative snapshots. Observability snapshots now summarize prompt-template usage counts, Socratic assessment aggregates such as evidence-score averages and profile-update counts, per-template/style Socratic prompt performance summaries, predictive warm activity, predictive warm queue processing and backlog counts, predictive cache invalidation totals, progress-profile trend counts, and generation prompt-performance summaries that combine immediate quality with explicit run-level outcome summaries, confidence-weighted calibration signals, persisted-summary coverage, aggregated learner-observation traces, same-session Socratic traces, and later cross-generation session outcomes, including average trace depth, so prompt experiments and conversational assessment behavior are inspectable without digging through raw audit events. Those same durable run summaries are now also written into the audit log as first-class `learning.run.summary` events, compacted into cross-session `learning.calibration.profile` and `learning.progress.profile` events, and reused by prompt calibration, route calibration, generation-mode selection, and learner-summary packaging before the system falls back to raw window reconstruction.

Knowledge Components are now first-class persisted entities with prerequisite links, optional catalogued misconception patterns, and remediation-planner integration. The remedial trigger uses that graph plus misconception signals to step back through weaker prerequisite KCs before returning to the requested target, and it now also emits a structured remediation blueprint with phases such as `step_back`, `repair`, and `return` so the generated remedial module is grounded in a more explicit plan. Remediation responses now include the detected misconception signals, misconception ids, remediation hints, per-KC primary flags, disambiguation scores, sequencing metadata, blueprint, and remediation-session metadata in `request_context`, and `POST /api/remedial/trigger` now starts a persisted workflow session whose later steps can be reloaded with `GET /api/remedial/sessions/{session_id}` and advanced with `POST /api/remedial/sessions/{session_id}/advance`. Repeated remediation classifications are now compacted into durable `learning.misconception.profile` audit events, later similar remedial requests can reuse those profile signals so persistent misconception patterns are not inferred only from the latest free-text description, and overlapping misconception matches on the same KC are now disambiguated down to a single primary repair path before blueprint selection. Learner-strategy signals now also choose a concrete KC sequence, so the remediation workflow can deliberately rebuild a prerequisite first or stay on the repair target instead of always inserting the same step-back path, and predictive warm follow-ups can now target that same sequenced KC before warming broader transfer checks. The learner API also now accepts observed interaction signals and infers affective state, cognitive load, metacognitive state, and lightweight cognitive trait updates back into the stored profile, including processing speed, working memory, and spatial reasoning estimates derived from recent observation patterns. Observations can now carry task context such as `task_type`, `support_level`, `expected_duration_ms`, and optional linkage fields such as `generation_id`, `learning_session_id`, `observed_content_type`, and target KC/LO ids, so an assessment attempt is interpreted differently from a scaffolded worked example and downstream prompt calibration can prefer exact, same-session, or context-compatible observation matches. Those same linkage fields now also let learner-state updates reuse recent same-target run summaries before persisting metacognitive state, so confidence calibration and help-seeking are not driven only by the latest raw observation window. The router now uses those metacognitive signals to hold back stretch when the learner still appears to need modeled support, and it now also returns a calibration summary on route decisions so recent same-target run outcomes can conservatively increase or relax scaffolding before delivery. There is now also a small within-session adaptation loop layered on top of that: recent `learner.observe` and `assessment.socratic` events for the same `learning_session_id` can immediately raise or relax support, hold on the current target, or move toward transfer on the next generated step instead of waiting for a later cross-session profile compaction pass. `GET /api/learners/{student_id}/summary` now rolls the current learner state together with recent generation, observation, assessment, calibration activity, and the latest durable cross-session progress trend so a frontend can render a learner overview card without replaying audit events client-side. The generation path also supports first-class worked-example fading and practice difficulty bands through the same unified engine, and those mode choices can now be nudged by persisted run-summary calibration rather than only current profile heuristics. Socratic mastery updates now also propagate conservatively through the stored KC graph, lifting prerequisites after strong evidence, damping downstream dependents after weak evidence, and recomputing affected LO mastery from the current KC set instead of treating each target KC as isolated. The generic `/api/content/generate` path can now auto-select a worked example when learner-state signals favor modeled support before freer explanation. There is also now a persisted conversational assessment flow at `POST /api/assessments/socratic` that scores the current learner response before choosing the next prompt, exposes continuous evidence dimensions such as lexical alignment, reasoning signal, confidence alignment, progression, and misconception risk, and uses an outcome-aware prompt-style policy such as `diagnostic`, `clarification`, `scaffolded_step_back`, or `transfer_check` across multi-turn sessions. Strong Socratic turns now also update target KC/LO mastery plus metacognitive readiness in the stored profile so later router decisions can respond to conversational evidence rather than treating assessment as an isolated side channel, and those same-session assessment outcomes can now feed generation prompt calibration as part of an aggregated downstream trace that can continue across later generated steps in the same learning session. Sessions can be reloaded with `GET /api/assessments/socratic/{session_id}`. Observability snapshots now include cache-hit counts, warm-request totals, predictive warm and invalidation totals, generated-content cache inventory, prompt-template usage, and generation prompt-performance summaries so pre-generation and prompt experiments are visible without extra instrumentation.

## Suggested Next Build Steps

1. Replace or augment SQLite with production persistence such as Redis/PostgreSQL or Redis/Cassandra.
2. Replace the SQLite embedding cache with a production vector store and background indexing pipeline while keeping the retriever plugin contract stable.
3. Calibrate the new learner-state signals with stronger evidence so routing and content-mode selection rely less on heuristics.
4. Deepen the new within-session adaptation layer beyond the current request-time observation and Socratic loop so it can coordinate richer multi-step arcs and recovery decisions inside an active session.
5. Expand predictive warming beyond the current rule-based follow-up planner into a broader scheduler with stronger invalidation signals and background execution options.
