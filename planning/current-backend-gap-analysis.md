# Current Backend Gap Analysis

This document compares the current Dibble backend against the authoritative planning packages:

- Product source of truth: `planning/4 - revised-spec/`
- Engineering handoff and migration guidance: `planning/5 - dev-handoff-revised-spec/`
- Historical context only: `planning/1`, `planning/2`, `planning/3`

## Status Summary

The backend now covers a meaningful slice of the revised Phase 1 and early Phase 2 foundation:

- LLM orchestration, retrieval-grounded generation, validation, streaming, auth, audit logging, observability, and provider resilience are implemented.
- The API surface now includes a single current route set that implements the revised generation/profile contract without carrying `v1` and `v2` path namespaces side by side.
- Generated content now has a persisted entity with quality and provenance metadata plus a lightweight cache-backed reuse path.

The biggest remaining gaps are no longer basic plumbing. They are adaptive intelligence depth:

- true learner-state inference rather than manually supplied profile fields
- KC prerequisite graphs and misconception classification
- richer remedial generation and deeper generation-template selection beyond the current specialized modes
- proactive pre-generation beyond the current explicit warmup endpoint

## Requirement Snapshot

Legend:

- `Implemented`: shipped in the current backend
- `Partial`: present in MVP form, but not at the depth expected by the revised spec
- `Missing`: still absent

| Requirement | Status | Notes |
|---|---|---|
| `LLM-001` LLM orchestration service | Implemented | Primary/secondary upstreams, failover, circuit breaker, selection strategies |
| `LLM-002` Prompt framework with versioning/A-B testing | Partial | Prompt builders exist; no prompt registry, versioning, or experimentation layer |
| `LLM-003` RAG pipeline | Implemented | Hybrid lexical + embedding retriever with persistent embedding cache |
| `LLM-004` Safety/moderation layer | Partial | Validation and safety rules exist; no dedicated moderation workflow |
| `LLM-005` Streaming response architecture | Implemented | SSE route plus upstream chat-stream ingestion |
| `GEN-001` On-the-fly explanation generation | Implemented | Current unified generation routes produce grounded explanations |
| `GEN-002` Practice problem synthesis | Partial | Dedicated problem generation now carries difficulty-band metadata, but there is no calibrated difficulty model or distractor synthesis |
| `GEN-003` Worked example generation with fading | Partial | Dedicated worked-example generation now carries adaptive fading metadata, but the template library and fading progression are still heuristic |
| `GEN-004` Remedial micro-module creation | Partial | Remedial trigger now steps through prerequisite KCs, but misconception classification and richer module assembly are still shallow |
| `GEN-005` Multi-modal synthesis | Missing | No diagram, interactive, simulation, or code generation layer |
| `PROF-001` Cognitive trait assessment | Partial | Profile schema stores traits, but no assessment or inference pipeline populates them |
| `PROF-002` Affective state detection | Partial | Observation-driven inference now updates affective state, but the logic is still heuristic rather than a richer classifier |
| `PROF-003` Real-time cognitive load estimation | Partial | Observation-driven load inference now updates the profile, but it is still heuristic and not calibrated by domain/task type |
| `PROF-004` KC granularity | Partial | KC mastery exists in the profile and there is now a persisted KC graph, but taxonomy depth and mastery migration are still limited |
| `PROF-005` Metacognitive tracking | Partial | Observation-driven confidence calibration and help-seeking signals now exist, but they remain heuristic and are not yet tied to richer intervention policy |
| `ADAPT-001` Thompson Sampling router | Implemented | Thompson-style policy with safety constraints is in the production path |
| `ADAPT-002` Within-session adaptation | Partial | Streaming generation exists, but there is no continuous state-updating adaptive loop |
| `ADAPT-003` Misconception detection/classification | Partial | Rule-based misconception signals now guide remediation planning, but there is no richer classifier or taxonomy yet |
| `ADAPT-004` Automatic step-back intervention | Implemented | Router and generation path support step-back content generation |
| `ADAPT-005` Conversational/Socratic assessment | Missing | No conversational assessment endpoint or turn manager |
| `API-001` `POST /api/content/generate` | Implemented | Current unified generation endpoint returns persisted generated-content metadata |
| `API-002` `POST /api/remedial/trigger` | Partial | Implemented as a lightweight wrapper; deeper remedial orchestration still missing |
| `API-003` `GET /api/learners/{id}/profile` | Implemented | Current unified learner-profile endpoint returns the extended dimensions |
| `API-004` `POST /api/llm/stream` | Implemented | Current unified streaming surface |
| `DATA-001` KnowledgeComponent entity and prerequisite graph | Implemented | Persisted KC entity plus prerequisite traversal API and remediation-planner integration |
| `DATA-002` Extended learner profile | Implemented | Current profile model includes cognitive, affective, load, and preference dimensions |
| `DATA-003` GeneratedContent entity with quality metadata | Implemented | Persisted generated content plus `generation_metadata` and `GeneratedContent` API envelope |
| `INFRA-003` Pre-generation and intelligent caching | Partial | Request-time generation cache and an explicit warmup endpoint exist; anticipatory scheduling and smarter invalidation do not |

## Highest-Value Next Gaps

Based on `planning/4 - revised-spec/implementation-roadmap.md` and `planning/5 - dev-handoff-revised-spec/requirements-traceability.csv`, the strongest next backend slices are:

1. `PROF-004`: expand the KC graph from a persistence/API layer into broader taxonomy coverage and mastery migration support.
2. `ADAPT-003`: evolve the new misconception signals into a richer taxonomy and confidence-calibrated classifier.
3. `PROF-002` + `PROF-003` + `PROF-005`: replace the new heuristic learner-state inference path with stronger calibrated models and task-aware features.
4. `INFRA-003`: move from explicit warmup requests to anticipatory scheduling and smarter cache invalidation for likely next-step content.
5. `LLM-002`: add prompt versioning and experimentation support on top of the new generation-mode planning layer.

## Recommendation

The most coherent next implementation step is now:

- deepen problem and worked-example generation into first-class generation modes
- keep reusing the current generated-content entity and cache metadata instead of adding a parallel cache layer
- let the router and remediation planner choose among richer instructional formats rather than only a generic prompt path

That is now partially in place. The most coherent next step is to calibrate the new learner-state signals and connect them more directly to routing and generation selection so those richer modes are chosen using stronger evidence instead of heuristics alone.
