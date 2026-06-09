# Dibble Retention Scheduler Design

**Date:** June 8, 2026  
**Source risk:** `R12` in [2026-05-05-risk-register.md](/Users/sfw/Development/dibble/planning/2026-05-05-risk-register.md)  
**Related plan:** [2026-05-07-risk-reduction-execution-plan.md](/Users/sfw/Development/dibble/planning/2026-05-07-risk-reduction-execution-plan.md)

## Purpose

This note defines the smallest useful retention / spaced-repetition design that fits Dibble's current planning and warm-content architecture.

Short version:

- Dibble already has a few retention-shaped pieces.
- Dibble does **not** yet have a real review scheduler or due-review queue.
- The right next move is not a full SM2 transplant.
- The right next move is a **retention candidate + due-review scheduler** that plugs into:
  - KC mastery and `kc_last_practiced`
  - ordinary mastery durability signals
  - trajectory planning
  - predictive warm scheduling
  - household-safe autonomous suggestions

## What already exists

The current system is not starting from zero.

### 1. Time-aware mastery honesty already exists

[mastery_decay.py](/Users/sfw/Development/dibble/src/dibble/services/mastery_decay.py) discounts stale KC mastery at read time.

That means Dibble already acknowledges:

- mastery fades with time
- stale success should not unlock future work forever

This is a good base, but it is still passive. It discounts stale mastery after the fact instead of actively scheduling review before the learner drifts.

### 2. Trajectories can already insert explicit review nodes

[trajectory_planner.py](/Users/sfw/Development/dibble/src/dibble/services/trajectory_planner.py) inserts `spaced_review` nodes via `_insert_review_nodes(...)`.

That means Dibble already supports the idea that:

- retention should be explicit
- trajectories can contain review, not only forward progression

But today this is still structural and static:

- review nodes are inserted by revisit density
- they are not tied to actual due dates
- they are not nominated from forgetting risk

### 3. Predictive warming already supports near-term follow-up generation

[predictive_content_warming.py](/Users/sfw/Development/dibble/src/dibble/services/predictive_content_warming.py) and [predictive_warm_scheduler.py](/Users/sfw/Development/dibble/src/dibble/services/predictive_warm_scheduler.py) can queue/generated likely next content.

This is important because a retention scheduler does **not** need its own generation mechanism. It can nominate review requests and let the existing warm queue do the execution.

### 4. Planning already has risk and revisit concepts

[planning.py](/Users/sfw/Development/dibble/src/dibble/models/planning.py) already includes:

- `active_revisit_density`
- concept-cluster risk markers
- recovery patterns
- trajectory revision adjustments such as `increase_revisit_density`

So the retention layer can fit inside the planning model rather than fighting it.

## What is missing today

The current gap is clear.

Dibble has:

- stale-mastery discounting
- trajectory review nodes
- immediate next-step warming

Dibble does **not** yet have:

- a durable review candidate model
- due-at timestamps for retention review
- an explicit scheduler deciding when review should surface
- prioritization across multiple review candidates
- a bridge from retention risk into household/autonomous suggestion flows

So the real missing component is a **review scheduler**, not more generation infrastructure.

## Design goal

Add retention behavior without reopening architecture.

The scheduler should:

- stay local-first and backend-owned
- reuse current learner evidence rather than inventing a separate learner model
- nominate only a small number of high-value review candidates
- avoid overwhelming active goal progression
- feed review work into existing planning and warm pipelines
- remain explainable to operators and parents

## Proposed model

### New concept: Retention review candidate

Introduce a lightweight durable model, conceptually like:

- learner id
- KC ids
- optional outcome id / cluster key
- review reason
- retention strength tier
- due at
- last reviewed at
- last successful review at
- review count
- last outcome score
- status: `scheduled`, `due`, `completed`, `expired`, `suppressed`

This should stay smaller and simpler than a full SM2 state machine.

### How candidates should be nominated

Candidates should come from existing evidence, not manual authoring.

Primary nomination sources:

1. **Recently strengthened target KCs**
   Source:
   - observation writeback in [observation_profile_update.py](/Users/sfw/Development/dibble/src/dibble/services/observation_profile_update.py)
   - same-session / recent learning summaries

   Why:
   - once the learner shows emerging or durable success, that is exactly when retention review becomes valuable.

2. **Outcomes newly treated as mastered or near-mastered**
   Source:
   - [learner_progression_service.py](/Users/sfw/Development/dibble/src/dibble/services/learner_progression_service.py)

   Why:
   - review should verify that "mastered" stays true across time.

3. **Concept clusters with moderate/high relapse risk**
   Source:
   - [planning_adaptation.py](/Users/sfw/Development/dibble/src/dibble/services/planning_adaptation.py)
   - trajectory adaptation state

   Why:
   - some learning looks good short-term but remains unstable.

4. **Recovery wins after a stall**
   Source:
   - recent `learning.run.summary`
   - progression outcome loops
   - planning recovery patterns

   Why:
   - after a hard-won recovery, a scheduled check is often more valuable than more forward expansion.

### How candidates should be suppressed

Not every KC needs a review candidate.

Suppress candidates when:

- the learner is already in active repair on the same KC cluster
- the learner is currently blocked on prerequisites and forward repair is higher priority
- there is already a pending/due candidate for the same KC cluster
- recent evidence remains `fragile` or `support_dependent`
- the learner has very high current overload / frustration and the review is not urgent

## Suggested scheduling logic

Keep the first version rule-based and bounded.

### Retention tiers

Use three simple tiers:

1. `light`
   For:
   - durable-looking success
   - low relapse risk
   - stronger independent evidence

   Initial due window:
   - around 3-5 days

2. `standard`
   For:
   - normal emerging-to-durable success
   - average evidence confidence

   Initial due window:
   - around 2-3 days

3. `urgent`
   For:
   - recent recovery after stall
   - declining trend recently stabilized
   - mastery likely to regress without a check

   Initial due window:
   - around 1 day

This is intentionally modest. We do not need full individualized forgetting curves yet.

### What should determine the tier

Signals to use:

- `kc_last_practiced`
- ordinary mastery signal:
  `durable_mastery`, `emerging_mastery`, `fragile`, `support_dependent`
- ordinary mastery confidence
- mastery volatility
- concept-cluster risk level
- recent progression outcome history
- whether the learner just recovered from a stall

Simple mapping:

- durable + low volatility + low cluster risk -> `light`
- emerging or moderate risk -> `standard`
- recovery-after-stall or high relapse risk -> `urgent`

## Where it should plug in

### 1. Planning

The scheduler should inform planning in two ways:

- if a due review exists for the active cluster, let planning surface or insert an explicit review step ahead of lower-priority expansion
- if the review is not due yet, keep the candidate only as scheduled state and leave the trajectory alone

This preserves the existing `spaced_review` node concept while making it data-driven.

### 2. Predictive warm queue

Due review candidates should be able to enqueue review-oriented generation requests into the existing warm queue.

That means the scheduler can nominate requests such as:

- `practice_problem` on prior target KCs
- `assessment_probe` when the learner is ready for a retention check
- `worked_example` only when the review should begin with support

The queue/scheduler path already exists; we just need retention candidates to feed it.

### 3. Household / autonomous teacher flows

When a due review is meaningful but not urgent, the autonomous-teacher layer can use it as:

- a session suggestion reason
- a weekly-summary note
- an approval-aware recommendation when the household cadence is low

This keeps retention work product-visible instead of hidden in backend decay.

## What should not happen

The retention scheduler should **not**:

- create a second mastery model
- fight progression ownership by forcing review constantly
- generate large review queues with no prioritization
- revive long-stale mastered content forever
- bypass household approval or rollout controls

The goal is focused review, not an always-on backlog.

## First implementation shape

The smallest implementation that fits current architecture is:

1. add a `RetentionReviewCandidate` model and store
2. add `RetentionSchedulerService`
3. nominate/update candidates after:
   - observation writeback
   - progression/mastery transitions
   - learning run summaries
4. expose a `due_reviews_for_student(...)` query
5. let curriculum planning and/or predictive warm consume due reviews

If we want to keep the first slice especially small, we can stage it:

### Stage 1

- durable candidate store
- nomination rules
- due-review query
- inspection/admin visibility

### Stage 2

- planning integration
- predictive warm integration
- autonomous-teacher suggestion integration

## Why this is the right size

This design is intentionally smaller than the original platform-root SM2 idea.

Why:

- Dibble already has strong KC state, durability signals, and planning infrastructure
- the bigger need is "when should we review?" not "how do we calculate a textbook spaced-repetition interval?"
- a due-review queue will let us learn from real behavior before adopting a more formal retention algorithm

In other words:

- first add explicit review scheduling
- then decide later whether the interval logic itself needs to become more sophisticated

## Recommended success criteria

The first retention slice should count as successful if:

- Dibble can surface a small, explainable set of due review candidates per learner
- those candidates are nominated from real mastery/progression evidence
- review work can be fed into planning or warm generation without manual intervention
- operators can explain why a review is due
- the scheduler does not overwhelm active forward progress

## Concrete recommendation

Proceed with a **lightweight retention scheduler**, not a full SM2/BKT hybrid.

The system already has the ingredients:

- KC timestamps
- mastery durability signals
- trajectory review hooks
- adaptive planning state
- warm-content infrastructure

What it lacks is the glue:

- durable review candidates
- due timing
- review prioritization

That is the next best risk-reduction slice for `R12`.
