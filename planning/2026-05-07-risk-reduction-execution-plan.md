# Dibble Risk Reduction Execution Plan

**Date:** May 7, 2026  
**Source:** [2026-05-05-risk-register.md](/Users/sfw/Development/dibble/planning/2026-05-05-risk-register.md)

## Purpose

This plan turns the refreshed risk register into a concrete execution sequence. The goal is not to tackle every medium-risk concern at once. The goal is to reduce the highest-value live risks in an order that improves pilot safety, quality confidence, and product-thesis credibility without reopening the core architecture.

## Prioritization logic

We should work in this order:

1. **Production safety rails**
   These are the places where a misconfigured deployment could quietly produce poor quality or misleading proof.

2. **Quality gates**
   These are the places where the system can generate content that looks plausible but is not reliable enough for a math-heavy learning product.

3. **Evaluation infrastructure**
   These are the tools that let us detect regressions and tune the system intentionally rather than by anecdote.

4. **Adaptation ceiling**
   These are the longer-horizon improvements that determine whether Dibble’s learner model stays heuristic or becomes measurably stronger over time.

5. **Product-thesis expansion**
   These are the items that improve how convincingly the product matches the “many modalities” story.

## Workstream A — Production safety rails

### A1. Embedder enforcement and visibility

Addresses: `R6`

Deliverables:

- make managed/household runtime refuse a real-provider learning deployment that still relies on `LocalHashEmbedder`
- surface embedder identity and posture in `/ready`
- emit explicit degraded/readiness guidance when local-hash embedding is active

Why first:

- this is a tier-1 operational risk
- it is small enough to fix immediately
- it protects every content-grounding path

### A2. Mock/provider posture hardening

Addresses: `R14`

Deliverables:

- tighten production-mode mock gating semantics
- ensure readiness and deployment docs clearly distinguish rehearsal vs real-provider modes

## Workstream B — Quality gates

### B1. Stronger math correctness verification

Addresses: `R3`, partly `R10`

Deliverables:

- add symbolic correctness checks for arithmetic and algebraic equalities
- reject content with mismatched stated answers
- add tests for valid and invalid math content

Notes:

- the current `MathSanityRule` is a good base, but it is not enough to protect a math-forward pilot

### B2. Diagram-quality direction

Addresses: `R16`

Deliverables:

- decide whether the next step is:
  - structured DSL-backed diagrams, or
  - narrow SVG hardening plus a migration plan

Status:

- completed decision in [2026-06-08-diagram-quality-direction.md](/Users/sfw/Development/dibble/planning/2026-06-08-diagram-quality-direction.md)
- recommendation: keep the current narrow diagram path and harden SVG constraints/validation now; only migrate to structured renderers if pilot evidence shows the current path is insufficient

## Workstream C — Offline evaluation

### C1. Golden-corpus content eval harness

Addresses: `R15`

Deliverables:

- a small but real corpus keyed by `KC × grade × intervention × modality`
- expected-property checks for correctness, alignment, readability, and structure
- a repeatable regression command for prompt/model/provider changes

Why this matters:

- once we tighten math checks, we still need a broader automated content-quality gate

## Workstream D — Adaptation ceiling

### D1. Knowledge-tracing model documentation

Addresses: `R4`

Deliverables:

- document the current mastery/progression model
- name the exact heuristic components, thresholds, and evidence loops
- define what failure would look like empirically

Status:

- completed in [2026-06-08-knowledge-tracing-and-mastery-model.md](/Users/sfw/Development/dibble/planning/2026-06-08-knowledge-tracing-and-mastery-model.md)

### D2. Modality preference deepening

Addresses: `R5`, `R23`

Deliverables:

- define what “shallow” still means in the current learner-scoped modality system
- add stronger learner-specific preference state only if the current priors are not enough

Status:

- completed assessment in [2026-06-08-modality-preference-depth-assessment.md](/Users/sfw/Development/dibble/planning/2026-06-08-modality-preference-depth-assessment.md)
- recommendation: keep the current routing model, avoid a large new preference subsystem, and improve downstream planning/household summaries before adding more raw state

### D3. Retention / spaced repetition design

Addresses: `R12`

Deliverables:

- a concrete retention scheduler proposal that fits the existing planning/warm pipeline

Status:

- completed design in [2026-06-08-retention-scheduler-design.md](/Users/sfw/Development/dibble/planning/2026-06-08-retention-scheduler-design.md)
- recommendation: add a lightweight review-candidate scheduler that plugs into planning and predictive warm before considering a heavier SM2-style model

## Workstream E — Product-thesis credibility

### E1. Modality thesis decision

Addresses: `R1`

Deliverables:

- decide whether the current `text + narrative + diagram` set is sufficient for pilot positioning
- if not, add exactly one next modality with the clearest proof value

Preferred order:

1. audio
2. interactive widget / graph surface

Status:

- completed decision in [modality-decision.md](/Users/sfw/Development/dibble/docs/proof/modality-decision.md)
- recommendation: keep the current `text + narrative + diagram` set for the current pilot/proof scope and only reopen the question if rehearsal reveals a specific proof blocker

## Recommended sequence

### Phase 1 — safety and truthfulness

1. A1 embedder enforcement and `/ready`
2. A2 mock/provider posture hardening
3. B1 stronger math correctness checks

### Phase 2 — quality confidence

1. C1 offline eval harness
2. D1 knowledge-tracing documentation
3. D2 modality preference deepening assessment

### Phase 3 — product credibility

1. E1 modality thesis decision
2. B2 diagram path decision
3. D3 retention scheduler design

## Progress update

Completed so far:

- A1 embedder enforcement and `/ready`
- A2 mock/provider posture hardening
- B1 stronger math correctness checks
- B2 diagram-quality direction
- C1 offline content-quality eval harness
- D1 knowledge-tracing model documentation
- D2 modality preference deepening assessment
- D3 retention / spaced repetition design
- E1 modality thesis decision

Implementation progress since this planning pass:

- Milestone A / Slice 1 diagram hardening is implemented
- Milestone B / Slice 2 retention scheduler stage 1 is implemented

## Plan status

The originally scoped risk-reduction plan is now complete at the planning/decision level.

What it now contains:

- completed operational safety decisions
- completed quality-gate and evaluation directions
- completed adaptation-ceiling documentation and design decisions
- completed product-thesis decisions needed for the current pilot scope

The next chapter should be an implementation plan derived from the completed decisions above, not more top-level risk-plan decomposition.

That implementation plan now exists in [2026-06-08-risk-reduction-implementation-plan.md](/Users/sfw/Development/dibble/planning/2026-06-08-risk-reduction-implementation-plan.md), and the next active slice is Milestone C: context-preserving modality summaries.
