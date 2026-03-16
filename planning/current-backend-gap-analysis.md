# Current Backend Gap Analysis

This document compares the current Dibble backend against the authoritative planning packages:

- Product source of truth: `planning/4 - revised-spec/`
- Engineering handoff and migration guidance: `planning/5 - dev-handoff-revised-spec/`
- Historical context only: `planning/1`, `planning/2`, `planning/3`

## Status Summary

The backend now covers a meaningful slice of the revised Phase 1 and early Phase 2 foundation:

- LLM orchestration, retrieval-grounded generation, validation, streaming, auth, audit logging, observability, and provider resilience are implemented.
- The API surface now includes a single current route set that implements the revised generation/profile contract without carrying `v1` and `v2` path namespaces side by side.
- Generated content now has a persisted entity with quality and provenance metadata plus a cache-backed reuse path that supports explicit warming, conservative predictive follow-up warming, and overlap-based invalidation when learner evidence changes.
- The learner summary endpoint now packages recent calibration and activity context into a frontend-ready overview instead of requiring direct audit-log reads.

The biggest remaining gaps are no longer basic plumbing. They are adaptive intelligence depth:

- true learner-state inference rather than manually supplied profile fields
- KC prerequisite graphs and misconception classification depth
- richer remedial generation and deeper generation-template selection beyond the current specialized modes
- broader cross-session use of the new run-summary calibration signals beyond the current router, learner-state, prompt, and generation-mode hooks
- richer scheduling and background execution beyond the current request-coupled predictive warm path

## Requirement Snapshot

Legend:

- `Implemented`: shipped in the current backend
- `Partial`: present in MVP form, but not at the depth expected by the revised spec
- `Missing`: still absent

| Requirement | Status | Notes |
|---|---|---|
| `LLM-001` LLM orchestration service | Implemented | Primary/secondary upstreams, failover, circuit breaker, selection strategies |
| `LLM-002` Prompt framework with versioning/A-B testing | Partial | Prompt registry now selects named templates with version and variant metadata for generation and Socratic assessment probes, observability now includes Socratic evidence aggregates plus per-template/style prompt-performance summaries, both assessment probes and the main experimented generation families can optionally prefer the stronger recent variant via audit-backed adaptive selection, generation variants can now incorporate aggregated observation-linked traces, same-session Socratic traces, and later cross-generation session outcomes, those traces are now condensed into explicit run-level outcome summaries plus confidence-weighted calibration signals, the summaries are now persisted as durable audit artifacts, prompt calibration now prefers those durable summaries before falling back to raw event-window reconstruction, and router plus generation-mode calibration can now also prefer compact cross-session profile snapshots built from those summaries, but experimentation is still minimal and there is no longer-horizon calibration loop |
| `LLM-003` RAG pipeline | Implemented | Hybrid lexical + embedding retriever with persistent embedding cache |
| `LLM-004` Safety/moderation layer | Partial | Validation and safety rules exist; no dedicated moderation workflow |
| `LLM-005` Streaming response architecture | Implemented | SSE route plus upstream chat-stream ingestion |
| `GEN-001` On-the-fly explanation generation | Implemented | Current unified generation routes produce grounded explanations |
| `GEN-002` Practice problem synthesis | Partial | Dedicated problem generation now carries difficulty-band metadata and can receive one-step difficulty nudges from persisted same-target calibration profiles or run summaries, but there is no richer calibrated difficulty model or distractor synthesis |
| `GEN-003` Worked example generation with fading | Partial | Dedicated worked-example generation now carries adaptive fading metadata, can be auto-selected from the unified generation path, and can receive one-step support adjustments from persisted same-target calibration profiles or run summaries, but the template library and fading progression are still conservative heuristics |
| `GEN-004` Remedial micro-module creation | Partial | Remedial trigger now steps through prerequisite KCs, can consume catalogued KC misconception patterns, emits structured remediation blueprints, and carries richer misconception ids/hints into generation context, but the generated module is still single-shot rather than a fuller multi-step remediation workflow |
| `GEN-005` Multi-modal synthesis | Missing | No diagram, interactive, simulation, or code generation layer |
| `PROF-001` Cognitive trait assessment | Partial | Profile schema stores traits and the observation pipeline now refreshes lightweight processing-speed, working-memory, and spatial-reasoning estimates from recent interaction patterns, but there is still no dedicated diagnostic assessment workflow or richer validation loop |
| `PROF-002` Affective state detection | Partial | Observation-driven inference now updates affective state with task-aware normalization, but the logic is still heuristic rather than a richer classifier |
| `PROF-003` Real-time cognitive load estimation | Partial | Observation-driven load inference now updates the profile with task-aware normalization, but it remains heuristic rather than calibrated from real outcome data |
| `PROF-004` KC granularity | Partial | KC mastery exists in the profile and there is now a persisted KC graph, but taxonomy depth and mastery migration are still limited |
| `PROF-005` Metacognitive tracking | Partial | Observation-driven confidence calibration and help-seeking signals now exist, are task-aware, influence routing/generation selection, can now be updated from Socratic assessment outcomes, and now also receive conservative run-summary adjustments in both router feedback and learner-state persistence, but they remain heuristic rather than calibrated |
| `ADAPT-001` Thompson Sampling router | Implemented | Thompson-style policy with safety constraints is in the production path, and a calibration wrapper now feeds compact cross-session calibration profiles, then recent same-target run summaries, back into final support selection |
| `ADAPT-002` Within-session adaptation | Partial | Streaming generation exists, but there is no continuous state-updating adaptive loop |
| `ADAPT-003` Misconception detection/classification | Partial | Misconception detection now combines rule-based mastery gaps with optional KC-level misconception catalogs, confidence scoring, remediation hints, and recommended repair targets, but it is still a lightweight heuristic taxonomy rather than a learned classifier |
| `ADAPT-004` Automatic step-back intervention | Implemented | Router and generation path support step-back content generation |
| `ADAPT-005` Conversational/Socratic assessment | Partial | A persisted Socratic assessment flow now scores the current learner response with modular evidence dimensions, stores multi-turn session state, chooses follow-up prompt style with an outcome-aware turn policy, feeds outcomes back into learner-profile mastery and metacognitive state, and can now contribute same-session plus later-session evidence to explicit generation run summaries and calibration signals that now influence router support, learner-state persistence, prompt calibration, and generation-mode selection, but it still lacks richer discourse modeling and broader outcome calibration across full learning traces |
| `API-001` `POST /api/content/generate` | Implemented | Current unified generation endpoint returns persisted generated-content metadata |
| `API-002` `POST /api/remedial/trigger` | Partial | Now returns richer misconception metadata plus a structured remediation blueprint, but still stops short of a longer-running remedial orchestration workflow |
| `API-003` `GET /api/learners/{id}/profile` | Implemented | Current unified learner-profile endpoint returns the extended dimensions |
| `API-004` `POST /api/llm/stream` | Implemented | Current unified streaming surface |
| `DATA-001` KnowledgeComponent entity and prerequisite graph | Implemented | Persisted KC entity plus prerequisite traversal API and remediation-planner integration |
| `DATA-002` Extended learner profile | Implemented | Current profile model includes cognitive, affective, load, and preference dimensions |
| `DATA-003` GeneratedContent entity with quality metadata | Implemented | Persisted generated content plus `generation_metadata` and `GeneratedContent` API envelope |
| `INFRA-003` Pre-generation and intelligent caching | Partial | Request-time generation cache and an explicit warmup endpoint now have conservative anticipatory follow-up warming, predictive request metadata, overlap-based invalidation from observation and Socratic outcomes, and telemetry coverage, but there is still no broader background scheduler, queue, or richer learned prediction policy |

## Highest-Value Next Gaps

Based on `planning/4 - revised-spec/implementation-roadmap.md` and `planning/5 - dev-handoff-revised-spec/requirements-traceability.csv`, the strongest next backend slices are:

1. `PROF-004`: expand the KC graph from a persistence/API layer into broader taxonomy coverage and mastery migration support.
2. `ADAPT-003`: evolve the new misconception signals from the current richer taxonomy and confidence scoring into a stronger learned classifier.
3. `PROF-001` + `PROF-002` + `PROF-003` + `PROF-005`: replace the new heuristic learner-state and lightweight trait inference path with stronger calibrated models trained from real outcome data.
4. `ADAPT-005` + `LLM-002`: promote the new persisted run summaries and compact calibration profiles beyond the current router, learner-state, prompt-calibration, generation-mode, and learner-summary wrappers into longer-horizon learner-outcome feedback so the Socratic-to-profile feedback loop and adaptive prompt-selection loop can learn across sessions rather than mainly within recent audit windows.
5. `INFRA-003`: evolve the new request-coupled predictive warming path into a broader background scheduler with better invalidation signals and stronger next-step prediction than the current rule-based planner.

## Recommendation

The most coherent next implementation step is now:

- extend the new run-summary and calibration-profile pipeline into broader cross-session adaptation targets
- replace more of the remaining heuristic learner-state and misconception logic with better-calibrated models trained from real outcomes
- keep building on the current predictive cache path rather than introducing a separate orchestration stack too early

That is now more achievable because the backend no longer relies only on explicit warmup calls or raw event-window reconstruction. The generation path can now warm likely next steps during normal content delivery, tag those warmed entries as predictive without fragmenting cache reuse, expire them when new same-target learner evidence arrives, and expose that behavior in telemetry. On the adaptation side, Socratic assessment and learner observations already feed learner-state updates, within-step trace aggregation, later same-session outcome tracing, explicit run-level calibration summaries, persisted run-summary audit events, compact cross-session calibration-profile events, a conservative router calibration layer, conservative learner-state calibration nudges, learner-summary API packaging, and prompt-selection plus telemetry paths that now reuse those persisted summaries before raw reconstruction. The next coherent step is to let those durable summaries and profiles drive more cross-session adaptation instead of remaining mostly local to prompt selection, route support nudges, near-term metacognitive persistence, recent-event observability, and lightweight frontend summaries.
