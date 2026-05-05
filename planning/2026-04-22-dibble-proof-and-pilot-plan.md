# Dibble Proof, Deployment, and Pilot Plan

This document defines the next chapter for Dibble after the harness re-architecture work. The architecture thesis has largely been implemented. The remaining work is no longer "add missing core harnesses." It is to prove that the system works end to end in the way the POC promised, package it in the intended deployment shape, and harden the highest-value operator and parent workflows enough to support a real pilot.

It is intentionally proof-biased rather than architecture-biased. The question here is not "what other major subsystem should we add?" but "what evidence do we need, and what packaging and product work do we need, to show that Dibble actually delivers the household-first autonomous teaching thesis?"

## Executive Pivot

We should now treat the harness implementation plan as substantially complete.

What is already true in the codebase:

- The backend owns pedagogical logic and exposes typed contracts.
- The privacy boundary is real: provider-facing and library-facing content flows are curriculum-shaped, not learner-shaped.
- The major harness boundaries are now explicit in the runtime: profile, evidence, modality routing, content generation, planning, within-session control, autonomous teacher, curriculum intake, and curriculum evolution.
- Parent and household flows, rollout controls, observability, simulation, and governance surfaces are real.
- Curriculum versioning, publish, diff, and migration are real enough to operate.

That means the biggest remaining risks are no longer architecture risks. They are proof risks:

- Can a parent actually run Dibble in the intended household/container deployment shape?
- Can we demonstrate the POC's visible learning thesis in a small set of convincing end-to-end scenarios?
- Is the current modality set sufficient to prove the modality thesis, or do we need one more materially different modality?
- Is the system operationally ready for a controlled pilot, not just locally testable?

This plan pivots us from building the platform shape to proving, packaging, and validating it.

## New North Star

The new north star is:

> A parent can run Dibble in a household deployment, create and manage learners, observe goal-directed teaching sessions, see adaptation and trajectory revision over time, approve or constrain autonomous behavior, and safely benefit from a shared curriculum-shaped content library without exposing learner-private data.

That north star implies four things must be true together:

1. The deployment story must be real.
2. The visible learning experience must be convincing.
3. The parent/operator governance story must be understandable and usable.
4. The pilot and support story must be operationally credible.

## What Is In Scope Now

This phase is about:

- end-to-end proof
- deployment and packaging
- thesis-complete scenario rehearsal
- pilot-readiness validation
- product and operations hardening in service of the above

This phase is not about:

- adding another large architecture layer for its own sake
- broadening institutional or classroom workflows
- solving generalized compliance or enterprise tenancy
- adding many more modalities just because the plugin system can support them

## Current State Assessment

### Strong areas

- The system now has explicit harness ownership and typed contracts across the teaching runtime.
- Long-horizon planning, within-session control, autonomous teacher behavior, and parent governance exist as real subsystems.
- The cloud-library path, rollout controls, simulation, auditability, and readiness inspection exist.
- Curriculum ingestion, publish, alignment, version evolution, and migration planning exist.
- A usable operator/parent trust surface now exists in the frontend.

### Remaining thesis gaps

- The deployment shape described in the POC has not yet been treated as the main product artifact. The system architecture is strong, but the household-container story needs to be made explicit and proven.
- The visible modality thesis may still be under-proven depending on the target audience. `text`, `narrative`, and `diagram` are real, but we have not yet decided whether the POC requires an additional materially different modality such as `audio` or `widget`.
- We have strong test confidence, but we still need stronger proof confidence: concrete end-to-end learner and parent scenarios that can be rehearsed and demonstrated without explanation doing all the work.
- Governance and readiness surfaces are good enough to support operators, but still need to be exercised in realistic flows rather than only validated as isolated features.

## Workstream 1: Household Deployment Proof

### Goal

Make the POC deployment story real, documented, repeatable, and operator-friendly.

### Why it matters

The POC is explicitly household-first and container-first. If we cannot show a parent-managed deployment shape, then the most distinctive product claim remains theoretical even if the application architecture is excellent.

### Deliverables

- A documented household deployment path using the intended runtime shape.
- Clear environment and secret configuration for model providers, cloud-library connectivity, and persistence.
- Persistent storage behavior that is easy to explain and verify.
- Startup, readiness, and failure guidance suitable for a technically capable parent or operator.
- A short deployment runbook for first-run setup, upgrades, backup expectations, and rollback expectations.

### Success criteria

- A fresh machine can run Dibble using the documented deployment path.
- A household can be created and configured without undocumented manual steps.
- Learner and household state persist cleanly across restarts.
- Degraded external dependency behavior is visible and understandable from the operator surface.

## Workstream 2: Thesis-Complete Scenario Proof

### Goal

Define and rehearse a small number of end-to-end scenarios that demonstrate the actual thesis, not just the existence of subsystems.

### Why it matters

At this point, the system can do many things. What we need is a compact set of demonstrations that prove the right things:

- learner-private state stays private
- routing and planning visibly adapt
- parent governance matters
- the cloud library compounds safely
- the autonomous teacher feels real rather than decorative

### Scenario set

At minimum, define and rehearse these scenarios:

1. New household onboarding.
   - Parent sets up the household.
   - Parent creates one or more learners.
   - A first goal and trajectory are created.
   - First-session readiness and approvals are visible.

2. Adaptive learning and modality change.
   - A learner attempts content in one modality.
   - Outcomes are weak or stall.
   - The system changes modality or composition in a visible way.
   - Follow-up outcomes improve or the strategy changes again.

3. Parent-governed autonomy.
   - The autonomous teacher proposes or initiates a meaningful action.
   - Parent approvals, denials, or constraints visibly change what happens next.
   - The explanation and preview surfaces make that change legible.

4. Cross-session planning revision.
   - Outcomes across multiple sessions trigger a trajectory revision.
   - Revisit density, pacing, or scaffolding changes.
   - The revision is inspectable and attributable to accumulated evidence.

5. Shared library reuse without privacy leakage.
   - A curriculum-shaped artifact is reused or published through the library path.
   - Provenance is visible.
   - No learner-private fields appear in the shared contract.

### Success criteria

- Each scenario can be run end to end without bespoke code edits.
- Each scenario demonstrates a clear before/after change that a non-developer can understand.
- Each scenario has a short script and an expected-observation checklist.

## Workstream 3: Modality Thesis Decision

### Goal

Explicitly decide whether the current modality set is enough for the POC, and if not, add exactly one additional modality that materially strengthens the proof.

### Why it matters

The POC's claim is not merely that Dibble can render text with variations. It is that the system can route across modalities in a meaningful, learner-beneficial way. The current `text`, `narrative`, and `diagram` paths may be enough, but we should decide that intentionally rather than by drift.

### Decision framework

The question is not "can we add another plugin?" It is:

- Does the current modality set produce clearly different learning experiences?
- Is that difference obvious enough in the demo scenarios?
- Would one more modality significantly strengthen the proof?

### Preferred next modality if needed

If the answer is "we need one more," prefer a modality that is materially distinct and feasible in the current architecture:

- `audio` if the goal is accessibility, engagement, and obvious multi-sensory differentiation.
- `widget` if the goal is interactive manipulation and stronger demonstration of active practice.

Do not add both unless the proof clearly requires it.

### Success criteria

- We have an explicit go/no-go decision for another modality.
- If we add one, it is exercised in at least one canonical scenario and integrated with current routing, verification, and observability.

## Workstream 4: Pilot Readiness

### Goal

Turn the current system into something we could responsibly put in front of a small, operator-managed cohort.

### Why it matters

Architecture completion is not pilot readiness. A pilot requires supportable setup, understandable failure modes, safe rollout controls, and clear operator expectations.

### Deliverables

- A pilot checklist covering environment setup, rollout policy defaults, kill-switch defaults, review queues, and support expectations.
- Recommended conservative defaults for autonomy, cloud-library behavior, non-text modalities, and migration execution.
- A small support runbook for interpreting readiness signals, degraded traces, and blocked approvals or migrations.
- A defined notion of pilot success and pilot stop conditions.

### Success criteria

- We can name the exact guardrails that would be on for the first cohort.
- We can explain what an operator should monitor daily or weekly.
- We can explain what would trigger rollback, pause, or narrower rollout.

## Workstream 5: Hardening and Productization

### Goal

Polish the highest-value rough edges that directly affect proof quality, operator confidence, or pilot safety.

### Why it matters

At this stage, rough edges matter disproportionately. The system can already do a great deal, but confidence is lost quickly if the last mile is awkward or confusing.

### Likely focus areas

- saved simulation snapshots and stronger review history
- deeper drilldowns from readiness panels into affected subjects and actions
- clearer confirmation and dry-run review flows
- deployment documentation and upgrade ergonomics
- performance and bundle-size follow-up where it affects demo or pilot experience
- curated seed data or demo fixtures for repeatable scenario rehearsal

### Success criteria

- The most common operator and parent review flows feel intentional rather than API-shaped.
- Demo and pilot rehearsals do not depend on tribal knowledge.
- The product feels like a coherent system, not a collection of good subsystems.

## Suggested Phase Plan

This work is better expressed as phases than as another long architecture milestone ladder.

### Phase A: Deployment Proof

- household deployment path
- environment and persistence docs
- startup and readiness validation
- operator runbook draft

### Phase B: Scenario Proof

- define canonical demo scenarios
- build any missing fixtures or scripts
- rehearse end-to-end flows
- tighten explanation and review surfaces where demos expose confusion

### Phase C: Modality Decision

- decide whether the current modality set is sufficient
- if not, add one additional modality and wire it through the existing architecture
- include it in at least one canonical scenario

### Phase D: Pilot Readiness

- pilot defaults and guardrails
- support and rollback runbooks
- operator checklist
- cohort definition and launch criteria

### Phase E: Hardening Before Exposure

- close the highest-value product rough edges
- improve drilldowns and saved reviews where needed
- address any deployment or performance blockers revealed by rehearsal

## Exit Criteria

This pivot is complete when all of the following are true:

- Dibble has a documented and proven household deployment path aligned with the POC.
- A compact set of end-to-end scenarios demonstrates the core thesis without relying on architectural explanation to carry the story.
- Parent governance, autonomous teacher behavior, planning revision, modality adaptation, and library reuse are all visible in those scenarios.
- We have an explicit answer on whether the current modality set is sufficient for the POC.
- A small pilot could be launched with clear defaults, guardrails, and support guidance.

## Open Questions

These questions should be answered explicitly during this phase rather than left implicit:

- Is `text + narrative + diagram` enough to prove the modality thesis, or does the POC need one more materially different modality?
- What is the minimum acceptable cloud-library deployment and monitoring posture for a real pilot?
- What is the exact threshold for calling the household deployment story "proved"?
- What pilot size, duration, and guardrails count as sufficient evidence for the POC?
- Which product rough edges are actually pilot blockers, and which are acceptable follow-up work?

## Recommended Immediate Next Moves

If we want the fastest path to POC completion, the next moves should be:

1. Treat deployment proof as the primary workstream, not a side chore.
2. Define the canonical scenario set and expected observations.
3. Decide whether another modality is needed before adding one.
4. Write the first pilot-readiness checklist while scenario rehearsal is happening, not after.

That keeps us focused on proving the right thing: not that Dibble has many parts, but that the parts now compose into the household-first autonomous teaching system the POC set out to demonstrate.
