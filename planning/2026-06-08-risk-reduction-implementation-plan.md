# Dibble Risk Reduction Implementation Plan

**Date:** June 8, 2026  
**Source decisions:**  
- [2026-05-07-risk-reduction-execution-plan.md](/Users/sfw/Development/dibble/planning/2026-05-07-risk-reduction-execution-plan.md)  
- [2026-06-08-knowledge-tracing-and-mastery-model.md](/Users/sfw/Development/dibble/planning/2026-06-08-knowledge-tracing-and-mastery-model.md)  
- [2026-06-08-modality-preference-depth-assessment.md](/Users/sfw/Development/dibble/planning/2026-06-08-modality-preference-depth-assessment.md)  
- [2026-06-08-retention-scheduler-design.md](/Users/sfw/Development/dibble/planning/2026-06-08-retention-scheduler-design.md)  
- [2026-06-08-diagram-quality-direction.md](/Users/sfw/Development/dibble/planning/2026-06-08-diagram-quality-direction.md)  
- [docs/proof/modality-decision.md](/Users/sfw/Development/dibble/docs/proof/modality-decision.md)

## Purpose

The risk-reduction plan is complete at the decision level. This document turns those decisions into an implementation roadmap.

The goal is to execute the highest-value improvements without reopening architecture or drifting into speculative platform expansion.

## Guiding principles

1. **Prefer tightening existing seams over adding new subsystems.**
2. **Use current durable learner evidence before inventing new models.**
3. **Bias toward inspectable, bounded heuristics unless pilot evidence demands heavier machinery.**
4. **Sequence work so every slice improves either pilot safety, quality confidence, or learner-specific adaptation truthfulness.**

## Current progress

Completed:

- **Milestone A / Slice 1:** diagram hardening
- **Milestone B / Slice 2:** retention scheduler stage 1

Next:

- **Milestone C / Slice 3:** context-preserving modality summaries

## Recommended order

Implement in this order:

1. **Diagram hardening**
2. **Retention scheduler, stage 1**
3. **Context-preserving modality summaries**
4. **Mastery/progression measurement pass**
5. **Retention scheduler, stage 2**

Why this order:

- diagram hardening is small, concrete, and directly improves visible content quality
- retention stage 1 creates new durable review state without entangling the runtime too early
- modality-summary refinement improves planning quality using data we already have
- mastery/progression metrics give us evidence before we make bigger KT-model decisions
- retention stage 2 is strongest once durable candidates and metrics already exist

## Slice 1 — Diagram hardening

**Status:** Complete

### Objective

Harden the current narrow SVG path rather than migrating to structured renderers now.

### Scope

- tighten the diagram prompt/constraint contract
- narrow the allowed diagram family
- add stronger SVG and composition validation
- preserve deterministic fallback as the safe floor

### Likely touch points

- [src/dibble/plugins/modalities/diagram.py](/Users/sfw/Development/dibble/src/dibble/plugins/modalities/diagram.py)
- [src/dibble/services/validation/rules.py](/Users/sfw/Development/dibble/src/dibble/services/validation/rules.py)
- [src/dibble/services/content_provider.py](/Users/sfw/Development/dibble/src/dibble/services/content_provider.py)
- tests around modality validation and generation fallback

### Concrete tasks

- define 2-3 supported diagram shapes in prompt guidance
- reject SVG bodies with unsupported complexity or missing required structure
- require title/caption/accessible label consistency
- add tests for:
  - valid simple diagram
  - missing accessible label
  - missing companion text
  - unsupported SVG constructs

### Done means

- provider-generated diagrams are more constrained
- malformed or overly broad SVG is rejected reliably
- fallback still produces a valid proof-safe diagram

### Implemented outcome

- the diagram plugin now allows only a narrow set of supported diagram shapes
- diagram prompt contracts now use the tighter visual schema when diagram mode is selected
- SVG validation now enforces accessibility structure, allowed tags/attributes, and bounded complexity
- the deterministic fallback SVG now carries the same accessibility and structural guarantees

## Slice 2 — Retention scheduler, stage 1

**Status:** Complete

### Objective

Add durable review candidates and due-review state without yet wiring review into every runtime surface.

### Scope

- add a retention candidate model/store
- nominate candidates from existing evidence
- expose due-review queries and inspectability

### Likely touch points

- new models under `src/dibble/models/`
- new service under `src/dibble/services/`
- storage wiring in SQLite-backed stores
- [src/dibble/services/observation_profile_update.py](/Users/sfw/Development/dibble/src/dibble/services/observation_profile_update.py)
- [src/dibble/services/learner_progression_service.py](/Users/sfw/Development/dibble/src/dibble/services/learner_progression_service.py)
- [src/dibble/services/planning_adaptation.py](/Users/sfw/Development/dibble/src/dibble/services/planning_adaptation.py)

### Concrete tasks

- add `RetentionReviewCandidate`
- add store/protocol and SQLite implementation
- nominate candidates from:
  - recent strengthened KC writeback
  - newly mastered/near-mastered outcomes
  - recovery-after-stall events
  - moderate/high concept-cluster risk
- implement suppression rules
- expose service methods like:
  - `upsert_candidates_for_student(...)`
  - `due_reviews_for_student(...)`
  - `scheduled_reviews_for_student(...)`

### Done means

- the system can tell us which KCs are due for retention review and why
- review candidates survive across sessions/restarts
- no planning or generation behavior changes yet unless explicitly queried

### Implemented outcome

- `RetentionReviewCandidate` is now a durable backend model with SQLite-backed persistence
- nomination now happens from observation writeback, progression summaries, and planning adaptation state
- suppression rules are implemented for active repair, prerequisite pressure, fragile/support-dependent evidence, duplicate active clusters, and high overload
- admin observability now exposes due and scheduled retention candidates
- stage 1 still does not make due review a first-class planning node, warm-generation task, or autonomous-teacher action

## Slice 3 — Context-preserving modality summaries

### Objective

Stop collapsing rich modality-routing evidence into one overly global preferred modality.

### Scope

- keep routing priors as the source of truth
- improve planning/adaptation summaries
- improve autonomous-teacher modality suggestions conservatively

### Likely touch points

- [src/dibble/services/planning_adaptation.py](/Users/sfw/Development/dibble/src/dibble/services/planning_adaptation.py)
- [src/dibble/models/planning.py](/Users/sfw/Development/dibble/src/dibble/models/planning.py)
- [src/dibble/services/autonomous_teacher_harness.py](/Users/sfw/Development/dibble/src/dibble/services/autonomous_teacher_harness.py)
- possibly [src/dibble/models/household.py](/Users/sfw/Development/dibble/src/dibble/models/household.py)

### Concrete tasks

- replace single `preferred_modality` dependence with a richer summary such as:
  - preferred modality by content family
  - preferred modality by concept-cluster risk bucket
  - preferred modality by recovery pattern where evidence exists
- keep household suggestions approval-safe and evidence-thresholded
- optionally add light recency weighting/aging when reading modality priors

### Done means

- planning can preserve contextual modality preference without creating a new subsystem
- autonomous-teacher suggestions remain simple but less globally flattened
- no regression in rollout/approval behavior

## Slice 4 — Mastery/progression measurement pass

### Objective

Add the measurement layer needed to judge whether the current heuristic KT-style stack is still good enough.

### Scope

- compute a small set of durable metrics
- make them inspectable
- do not replace the current mastery/progression model yet

### Likely touch points

- new service under `src/dibble/services/`
- observability/admin read models and routes
- audit-store-backed metric computation
- possibly [src/dibble/models/observability.py](/Users/sfw/Development/dibble/src/dibble/models/observability.py)

### Concrete tasks

- compute:
  - hold positive rate
  - transfer positive rate
  - prerequisite rebuild positive rate
  - false-positive mastery rate
  - release regret rate
  - over-hold rate
  - outcome mastery stability
- expose a bounded inspect endpoint or admin summary
- add tests that verify metric calculation from audit fixtures

### Done means

- we can evaluate the current heuristic progression model with real evidence
- future KT-model decisions can be based on observed failure patterns rather than intuition

## Slice 5 — Retention scheduler, stage 2

### Objective

Let due-review candidates influence runtime behavior in a controlled, explainable way.

### Scope

- planning integration
- predictive warm integration
- optional autonomous-teacher suggestion integration

### Likely touch points

- [src/dibble/services/trajectory_planner.py](/Users/sfw/Development/dibble/src/dibble/services/trajectory_planner.py)
- [src/dibble/services/harness/curriculum_planning.py](/Users/sfw/Development/dibble/src/dibble/services/harness/curriculum_planning.py)
- [src/dibble/services/predictive_content_warming.py](/Users/sfw/Development/dibble/src/dibble/services/predictive_content_warming.py)
- [src/dibble/services/predictive_warm_scheduler.py](/Users/sfw/Development/dibble/src/dibble/services/predictive_warm_scheduler.py)
- [src/dibble/services/autonomous_teacher_harness.py](/Users/sfw/Development/dibble/src/dibble/services/autonomous_teacher_harness.py)

### Concrete tasks

- let planning surface due review nodes when genuinely due
- enqueue review-oriented warm requests for due candidates
- keep active repair/prerequisite work higher priority than routine review
- optionally surface retention review as a session suggestion reason

### Done means

- due review becomes a real runtime behavior, not just stored state
- review remains bounded and explainable
- active forward learning does not get overwhelmed

## What we are explicitly not doing in this roadmap

- no full BKT/DKT migration yet
- no broad modality-ML subsystem
- no structured diagram renderer migration yet
- no new audio or interactive modality in this slice
- no heavy SM2 clone unless the lighter retention scheduler proves insufficient

## Verification expectations per slice

Every slice should include:

- backend tests for new services/stores
- backend tests for changed runtime behavior
- `uv run ruff check src/dibble tests`
- targeted pytest on touched areas

If a slice changes frontend-visible contracts, update frontend types and run:

- `cd frontend && npm test`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`

## Suggested milestone packaging

If we want to hand this to implementation agents in clean chunks:

1. **Milestone A:** Diagram hardening
2. **Milestone B:** Retention scheduler stage 1
3. **Milestone C:** Context-preserving modality summaries
4. **Milestone D:** Mastery/progression metrics
5. **Milestone E:** Retention scheduler stage 2

## Immediate next step

Execute **Milestone C**: preserve contextual modality preference in planning and autonomous-teacher summaries without adding a new modality-learning subsystem.

Start with **Milestone A: Diagram hardening**.

It is the smallest concrete slice, improves visible content quality quickly, and stays fully aligned with the already-decided modality and pilot-proof posture.
