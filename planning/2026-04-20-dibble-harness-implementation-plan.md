# Dibble Harness POC Review and Implementation Plan

This document reviews [`planning/2026-04-20-dibble-harness-poc.md`](./2026-04-20-dibble-harness-poc.md) against the current Dibble implementation and turns the proposed nine-harness architecture into subsystem-specific implementation plans.

It is intentionally implementation-biased. The question here is not "is the harness thesis good?" but "how do we get from the current codebase to that thesis with the least waste and the clearest boundaries?"

## Executive Review

The POC direction is compatible with the current codebase, but the system is not organized around those nine harness boundaries yet.

What already fits well:

- The backend already owns pedagogical decisions.
- The codebase already has strong typed contracts in Pydantic models and a broad service layer.
- Socratic assessment, learner profile updates, within-session adaptation signals, progression summaries, content validation, moderation, and teacher/learner read models are already substantial and well tested.
- The plugin mechanism and dependency injection are already real, even if they are still coarse-grained.

What does not fit yet:

- The current generation path still carries `LearnerProfile` into router, retriever, provider, prompting, and cache layers. That violates the new POC's strongest rule: content must be curriculum-shaped, never learner-shaped.
- The current plugins are capability-wide (`router`, `retriever`, `provider`, `validator`), not modality plugins plus model-provider plugins.
- Long-horizon planning is missing. The codebase has progression summaries and target-redirection logic, but not explicit learner goals, trajectories, checkpoints, or revision history.
- Autonomous Teacher is mostly absent. The current product is still teacher/classroom-centric, not parent/household-centric.
- The runtime orchestration is distributed across many services rather than exposed as the nine visible planner/executor/verifier/state harnesses from the POC.

## Current-to-POC Mapping

| Harness | Current implementation | Readiness | Main gap |
| --- | --- | --- | --- |
| 1. Curriculum Intake & Alignment | `curriculum_routes.py`, curriculum stores, `admin_academic_catalog.py`, `scripts/seed_alberta_math7.py` | Partial | No import pipeline, versioned source registry, review queue, or cross-framework alignment edges |
| 2. Curriculum Planning | `learner_progression_service.py`, `progression_ownership.py`, `kc_sequence_planner.py`, `predictive_next_step_planner.py` | Partial | No learner goals, multi-session trajectory, expected durations, checkpoints, or revision history |
| 3. Learner Profile | `profile_store`, `observation_store`, `observation_profile_update.py`, `state_inference.py`, `cognitive_trait_inference.py`, `socratic_profile_update.py`, snapshots and signal recorders | Strong | Single-writer boundary is implicit, not enforced through a dedicated harness API |
| 4. Modality Routing | `adaptive_router.py`, `calibrated_router.py`, generation mode calibration, modality affinity in profile | Weak/Partial | Routes intervention/scaffolding, not modality plugins or compositions |
| 5. Content Generation | `generation_engine.py`, `content_workflow.py`, moderation, validation, `generated_content_store.py`, current plugin loader | Partial | No modality host, no cloud library, no curriculum-only contract, no standardized artifact provenance/accessibility |
| 6. Assessment & Evidence | observation ingestion, misconception detection, remediation planner, outcome trackers, profile updaters | Partial | Evidence is inferred through side effects, not first-class evidence bundles with extractor/verifier contracts |
| 7. Socratic Dialogue | `socratic_assessment.py`, `socratic_policy.py`, `socratic_evidence.py`, session store, frontend Socratic workspace | Strong | Needs to be re-homed under the new harness boundary and upgraded to explicit verifier/termination semantics |
| 8. Within-Session Control | `within_session_adaptation.py`, controller store, `learner_flow_service.py`, portions of `content_workflow.py` | Partial | No explicit session action planner/service owning the outer loop |
| 9. Autonomous Teacher | teacher dashboards, teacher intervention actions, eager lesson generation in `learner_workspace_service.py` | Weak | No scheduling, parent relationship, approval gates, re-engagement, or soft escalation subsystem |

## Cross-Cutting Revisions Required First

Before tackling harness-by-harness work, four architecture changes should be treated as foundation work.

### 1. Split private learner state from curriculum-shaped generation contracts

Today, `RouterPlugin`, `RetrieverPlugin`, and `ProviderPlugin` all receive `LearnerProfile`, and prompt construction uses affect, load, pace, modality preferences, example domains, and accommodations directly.

That is the single biggest mismatch with the POC.

Implementation direction:

- Keep `LearnerProfile` as an internal/private model.
- Introduce a routing-only projection, for example `LearnerRoutingProfile`, that the routing harness can read.
- Introduce a separate `CurriculumContentRequest` that contains only curriculum-safe fields: KC targets, misconception target, pedagogical move, theme family, locale, scaffolding level, accessibility requirements, and modality plan.
- Remove `student_id` and `LearnerProfile` from modality plugin inputs.
- Move learner-specific cache keys out of generated artifact storage and into delivery/event tables.

### 2. Add explicit harness facades without rewriting the existing services

The current services are already modular. The problem is not that the logic is missing; it is that the top-level ownership boundaries are unclear.

Implementation direction:

- Add a new `src/dibble/services/harnesses/` package.
- Start each harness as a facade over existing services rather than a rewrite.
- Give each harness four clear concerns:
  - planner
  - executor
  - verifier
  - durable state access
- Migrate routes and higher-level services to depend on harness facades first, then refactor internals behind them.

### 3. Separate modality plugins from model-provider plugins

The current plugin model is useful, but it mixes orchestration capabilities with provider capabilities.

Implementation direction:

- Keep the existing provider integration and prompt system as the first text-generation provider plugin.
- Introduce modality plugins as first-class runtime units:
  - text
  - narrative
  - diagram
  - audio
  - widget
- Introduce model-provider capability plugins:
  - text generation
  - code generation
  - TTS
  - image/SVG generation
  - embeddings
- Let modality plugins declare the provider capabilities they need.

### 4. Reframe the product surface from classroom-first to household-first for the POC

The current app has `learner`, `teacher`, and `admin/staff` surfaces. The POC document describes a parent-managed household deployment.

Implementation direction:

- Add `parent` or `household_admin` role support to auth and user models.
- Preserve teacher/admin views for internal operations and future product directions.
- Add a parent-facing setup and progress surface as the main POC UI.
- Treat teacher workflows as optional overlays, not the primary narrative of the POC.

## Subsystem Implementation Plans

## 1. Curriculum Intake & Alignment

### Current implementation

- Runtime curriculum entities already exist as typed models: `Course`, `Strand`, `Outcome`, and `KnowledgeComponent`.
- CRUD APIs and SQLite stores already exist for strands, outcomes, and KCs.
- Alberta Math 7 can already be seeded via `scripts/seed_alberta_math7.py`.
- The system already understands prerequisite KCs and misconception catalogs.

### Primary gaps

- No source-of-truth object for a curriculum framework import.
- No import job state, provenance, review workflow, or version history.
- No alignment/crosswalk edges across frameworks.
- No distinction between "raw source import" and "runtime published curriculum snapshot."

### Implementation plan

1. Add framework import models and stores.
   - New models: `CurriculumFramework`, `FrameworkImport`, `FrameworkImportArtifact`, `AlignmentEdge`, `AlignmentReviewDecision`.
   - New stores: `framework_store.py`, `framework_import_store.py`, `alignment_edge_store.py`.

2. Build the harness facade.
   - `curriculum_intake_harness.py`
   - planner: choose import adapter
   - executor: parse/import source
   - verifier: schema, graph sanity, confidence thresholds
   - state: framework/import/alignment stores

3. Convert seed scripts into import adapters.
   - Alberta seed becomes a structured adapter that writes through the harness instead of calling runtime APIs directly.
   - Preserve existing runtime stores as the published read model.

4. Add a publish step.
   - Imported artifacts should land in import/version tables first.
   - A publish action writes the approved version into the runtime curriculum tables used by the learner flow.

5. Add alignment as a second phase.
   - Start with `equivalent_to` and `overlaps_with` edges only.
   - Keep low-confidence alignments in `review_required` state.

6. Add tests.
   - schema validation
   - cycle detection
   - import idempotency
   - publish workflow
   - alignment review flow

## 2. Curriculum Planning

### Current implementation

- `LearnerProgressionService` computes outcome readiness, blocked prerequisites, active outcomes, and mastered outcomes.
- `ProgressionOwnershipService` redirects requested targets across repair, bridge, target, and transfer stages.
- `KcSequencePlanner` already reasons about prerequisites and bridge KCs.
- `PredictiveNextStepPlanner` already forecasts likely next content types.

### Primary gaps

- No learner goal model.
- No long-horizon trajectory through curriculum.
- No expected duration estimates or checkpoint schedule.
- No trajectory revision history.
- No explicit spaced-practice rhythm owned by a planning subsystem.

### Implementation plan

1. Introduce goal and trajectory contracts.
   - New models: `LearnerGoal`, `TrajectoryPlan`, `TrajectoryNode`, `TrajectoryCheckpoint`, `TrajectoryRevision`.
   - New stores: `learner_goal_store.py`, `trajectory_store.py`.

2. Build a planning harness on top of existing progression logic.
   - `curriculum_planning_harness.py`
   - reuse `LearnerProgressionService` as the current-state classifier
   - reuse `KcSequencePlanner` for local cluster ordering
   - add a new `trajectory_planner.py` for week-scale sequencing

3. Add goal entry and review APIs.
   - learner/parent selects a curriculum goal
   - system creates initial trajectory
   - trajectory revisions are stored, not overwritten

4. Add spaced-practice planning.
   - Keep initial implementation rule-based
   - derive revisit nodes from mastery volatility, time-since-practice, and outcome criticality

5. Expose planning read models.
   - learner-facing "current trajectory"
   - parent-facing "goal progress"
   - teacher/staff read model can remain optional for the POC

6. Keep current progression summary endpoints alive.
   - `LearnerCurriculumProgressionSummary` becomes the short-horizon read model backed by the new trajectory state.

## 3. Learner Profile

### Current implementation

- Learner profile state is rich: mastery, affect, cognitive load, metacognition, learning preferences, accommodations, and cognitive traits.
- Observation ingestion, state inference, cognitive trait inference, Socratic profile updates, mastery snapshots, and multiple calibration/profile recorders already exist.
- This is one of the strongest parts of the current codebase.

### Primary gaps

- The single-writer rule is social, not enforced by API shape.
- Historical reconstruction relies on mixed mechanisms instead of an explicit profile event stream.
- Contradiction/quarantine flows are not surfaced as first-class profile update outcomes.
- Downstream generation still receives the full profile instead of a routing-only projection.

### Implementation plan

1. Create a learner-profile harness facade.
   - `learner_profile_harness.py`
   - command handlers: `apply_observation`, `apply_assessment_evidence`, `apply_socratic_evidence`, `apply_declared_update`

2. Add explicit profile update result types.
   - `ProfileUpdateDecision`
   - `ProfileUpdateUncertainty`
   - `ProfileUpdateConflict`

3. Add a dedicated profile event store.
   - Every accepted or quarantined update becomes a typed event.
   - `profile_store` remains the latest-state projection.

4. Split outbound views.
   - private internal profile
   - routing profile projection
   - learner/parent/teacher read models

5. Route all profile writes through the harness.
   - update learner routes and assessment routes to call the harness, not stores directly

6. Add verification and calibration hooks.
   - retain current calibrators
   - formalize "hold update" and "request more evidence" outcomes

## 4. Modality Routing

### Current implementation

- `AdaptiveRouter` and `CalibratedRouter` choose intervention type, delivery mode, and scaffolding.
- Profiles already contain `modality_affinity` and example-domain preferences.
- Session and strategy calibration already influence routing.

### Primary gaps

- No routing by modality plugin identity.
- No composition plan across multiple modalities.
- No explicit translation boundary from learner-specific preferences to curriculum-shaped request parameters.
- `delivery_mode` is too coarse to express the new action space.

### Implementation plan

1. Introduce routing-specific contracts.
   - `PedagogicalMove`
   - `ModalityDirective`
   - `PluginSelection`
   - `CompositionPlan`
   - `CurriculumThemeSelection`

2. Build a modality-routing harness.
   - `modality_routing_harness.py`
   - planner: bandit/plugin selection
   - executor: choose plugin ordering/composition
   - verifier: eligibility and outcome fit
   - state: routing priors store

3. Preserve the current router as the stage-one pedagogical move selector.
   - Phase 1: existing router picks `step_back`, `reteach`, `stretch`, etc.
   - Phase 2: modality routing chooses which plugin realizes that move.

4. Add the translation boundary.
   - learner-specific input: "engages with pets", "needs lower load", "prefers slower pace"
   - output: curriculum-safe request fields such as theme family, scaffolding level, locale, and modality choice

5. Add routing outcome feedback.
   - update priors from evidence bundles and session outcomes, not just content-generation success

6. Start with one default plugin.
   - First route everything to `text` so the new harness can ship without waiting on all five plugins.

## 5. Content Generation

### Current implementation

- `GenerationEngine` already handles retrieval, routing, provider generation, validation, moderation, caching, and persistence.
- `ContentWorkflowService` already wraps generation, remediation, predictive warming, and workflow summaries.
- Validation and moderation are already meaningful.
- Streaming already exists.

### Primary gaps

- The current pipeline is learner-shaped end to end.
- Stored generated artifacts are keyed and persisted per learner.
- There is no cloud library abstraction.
- Provider plugins are not modality plugins.
- Artifact contracts do not yet carry the provenance/accessibility surface described in the POC.

### Implementation plan

1. Introduce content-host contracts.
   - `CurriculumContentRequest`
   - `ContentArtifact`
   - `ArtifactProvenance`
   - `ArtifactAccessibility`
   - `VerifierReport`

2. Build a content-generation harness facade.
   - `content_generation_harness.py`
   - planner: cache/library lookup plus composition plan
   - executor: dispatch modality plugins
   - verifier: plugin self-checks plus host-level checks
   - state: local artifact cache plus library client

3. Split plugin layers.
   - modality plugins: text, narrative, diagram, audio, widget
   - provider capability plugins: text generation, code generation, TTS, embeddings, image/SVG generation

4. Adapt the current implementation instead of replacing it.
   - current provider stack becomes the text modality path
   - current retriever/validator can be reused inside the text plugin host path

5. Separate learner linkage from artifact storage.
   - artifact cache/library key becomes curriculum metadata only
   - learner-specific delivery history moves to audit/event tables

6. Add a cloud-library client abstraction.
   - stage 1: local stub with same interface
   - stage 2: remote read/write adapter
   - stage 3: upload only verified curriculum-shaped artifacts

7. Tighten verification.
   - keep current validator/moderation
   - add independent artifact verifier result object
   - add composition-coherence verification once multimodal outputs exist

## 6. Assessment & Evidence

### Current implementation

- Observation ingestion already updates mastery and learner-state fields.
- `MisconceptionDetector` and remediation planning already exist.
- Outcome trackers and mastery-quality gates already exist.
- Socratic evidence exists, but only inside the Socratic subsystem.

### Primary gaps

- There is no first-class evidence bundle for ordinary learner responses.
- Extraction logic is distributed across observation/profile update code paths.
- Evidence quality and verifier disagreements are not stored as reusable evidence objects.
- Widget traces and richer response types have no dedicated extractor interface yet.

### Implementation plan

1. Create explicit evidence contracts.
   - `EvidenceBundle`
   - `EvidenceClaim`
   - `EvidenceDimension`
   - `EvidenceQuality`
   - `EvidenceVerdict`

2. Add an assessment-and-evidence harness.
   - `assessment_evidence_harness.py`
   - planner: choose extractors by response type
   - executor: run deterministic and model-based extractors
   - verifier: confirm evidence sufficiency
   - state: `evidence_store.py`

3. Preserve existing logic as extractors.
   - misconception detector becomes a misconception extractor
   - observation profile heuristics become an interaction-trace extractor
   - rubric-based depth scoring becomes a free-response extractor

4. Change learner observation flow.
   - learner observation route creates an evidence bundle first
   - learner-profile harness consumes the evidence bundle second

5. Unify evidence across channels.
   - standard generated content responses
   - remediation steps
   - widget traces
   - Socratic dialogue results

6. Add evidence read models.
   - learner/private evidence trail
   - parent summary view
   - harness observability view for debugging

## 7. Socratic Dialogue

### Current implementation

- This is already one of the most complete POC-aligned subsystems.
- The codebase has turn policy, evidence scoring, session persistence, profile updates, API routes, and frontend support.

### Primary gaps

- It is still framed as "assessment" rather than as its own harness.
- Prompt generation is still coupled to the old generation engine contract.
- Session states like paused, stalled, and resumable are not first-class enough.
- Evidence sufficiency and independent verification need stronger formalization.

### Implementation plan

1. Re-home it under a dedicated harness facade.
   - `socratic_dialogue_harness.py`
   - keep current service internals initially

2. Strengthen session state.
   - explicit status enum: `in_progress`, `paused`, `stalled`, `complete`, `abandoned`
   - explicit termination reason

3. Route prompt generation through the new content-generation harness.
   - dialog text becomes a modality/sub-mode, not a special-case generation call

4. Emit unified evidence bundles.
   - Socratic outputs should write to the same evidence store as other assessments

5. Add verifier and sufficiency rules.
   - separate policy decision from evidence sufficiency decision
   - block completion when evidence is still thin

6. Preserve the current API/UI shape where possible.
   - existing learner experience is already good scaffolding for the POC demo

## 8. Within-Session Control

### Current implementation

- `WithinSessionAdaptationService` already computes phase, support bias, streaks, stuck-loop risk, and session arc.
- `LearnerFlowService` already builds strong read models for the current learner flow.
- `ContentWorkflowService` already orchestrates a significant portion of the session-time actions.

### Primary gaps

- There is no single subsystem that clearly owns the active session loop.
- Action planning, content orchestration, and flow summarization are spread across multiple services.
- The action space from the POC is only partially explicit.

### Implementation plan

1. Create a dedicated session-control harness.
   - `within_session_control_harness.py`
   - planner: choose next action
   - executor: dispatch to routing, generation, Socratic, evidence, or close session
   - verifier: stuck-loop and coherence checks
   - state: current controller store plus new session-command log if needed

2. Keep `WithinSessionAdaptationService` as the signal engine.
   - do not delete it
   - make it an input to the new planner rather than the outer-loop owner

3. Move orchestration out of `ContentWorkflowService` over time.
   - content generation remains downstream
   - session sequencing moves into the harness

4. Expand the action enum to match the POC.
   - continue
   - reteach
   - step_back
   - stretch
   - swap_modality
   - invoke_socratic
   - consolidate
   - end_session

5. Add explicit session APIs.
   - start session
   - request next action
   - record response/evidence
   - close session

6. Keep `LearnerFlowService` as the primary read model.
   - it already works well as the learner-facing current-session summary

## 9. Autonomous Teacher

### Current implementation

- Teacher-facing section dashboards, intervention proposals, and learner workspace summaries already exist.
- Setup/auth/admin flows already exist for local deployment.
- The current system can surface what the learner should do next, but it does not decide when to start sessions or how to manage the learner relationship across weeks.

### Primary gaps

- No autonomous session cadence.
- No parent/household role.
- No parent notification or approval gate system.
- No long-horizon relationship memory.
- No re-engagement or soft-escalation path.

### Implementation plan

1. Introduce household and parent models.
   - `Household`
   - `ParentProfile`
   - `ParentPreference`
   - `LearnerRelationshipState`

2. Add the autonomous-teacher harness.
   - `autonomous_teacher_harness.py`
   - planner: schedule, next focus, re-engagement, escalation triggers
   - executor: start session, request trajectory revision, notify parent
   - verifier: cadence, relationship coherence, goal alignment
   - state: relationship store, schedule store, notification log

3. Add parent-facing APIs and UI.
   - household setup
   - learner summaries
   - approval settings
   - "I need your help" events

4. Start small.
   - daily/weekly session suggestions
   - weekly summary
   - persistent-stall notification
   - no need for full messaging infrastructure in phase one

5. Preserve current teacher tooling as secondary.
   - teacher views can remain valuable for debugging and future product expansion
   - the POC demo should emphasize parent-managed autonomy

## Recommended Delivery Sequence

The implementation should not begin with Autonomous Teacher. The highest-leverage path is:

1. Boundary hardening
   - curriculum-shaped generation contract
   - harness facades
   - plugin split design

2. Middle-loop architecture
   - learner profile harness
   - assessment/evidence harness
   - modality routing harness
   - content-generation harness

3. Control-plane architecture
   - curriculum planning harness
   - within-session control harness

4. Product orchestration
   - autonomous teacher
   - parent/household surfaces
   - cloud library integration

## Suggested Initial Milestones

### Milestone 1: Architectural invariants

- Add harness facade package and wire existing routes through facades where practical
- Introduce `CurriculumContentRequest`
- Stop passing full `LearnerProfile` into provider-facing generation code
- Add local-only content library client abstraction

### Milestone 2: Re-platform the active learning loop

- Land learner-profile harness
- Land assessment/evidence harness
- Land modality-routing harness with text plugin only
- Land content-generation harness as host over the current text stack

### Milestone 3: Make planning explicit

- Add learner goals and trajectories
- Make within-session control a dedicated orchestrator
- Rebind learner workspace and continue actions to explicit session and trajectory state

### Milestone 4: Finish the POC shape

- Add parent role and household setup
- Add autonomous-teacher scheduling and notifications
- Add cloud library read/write path
- Add additional modality plugins beyond text

## Closing Recommendation

The right move is not to replace the current system with nine new monoliths named after harnesses. The current codebase already contains many of the hard parts in good, testable slices.

The right move is to:

- preserve the fine-grained services
- add explicit harness ownership layers above them
- enforce the privacy/content boundary early
- then grow the missing long-horizon and parent-facing subsystems around the strong learner-profile, Socratic, and session-adaptation foundations that already exist
