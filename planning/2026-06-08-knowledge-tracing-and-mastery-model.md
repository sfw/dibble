# Dibble Knowledge-Tracing And Mastery Model

**Date:** June 8, 2026  
**Source risk:** `R4` in [2026-05-05-risk-register.md](/Users/sfw/Development/dibble/planning/2026-05-05-risk-register.md)  
**Related plan:** [2026-05-07-risk-reduction-execution-plan.md](/Users/sfw/Development/dibble/planning/2026-05-07-risk-reduction-execution-plan.md)

## Purpose

This note documents Dibble's **actual current mastery and progression model** so we can reason about its ceiling honestly.

The short version:

- Dibble does **not** currently run a formal BKT, DKT, or other probabilistic knowledge-tracing model.
- Dibble **does** maintain a durable learner knowledge state, infer mastery from session evidence, decay stale mastery over time, classify cross-session ordinary evidence, and feed progression outcomes back into later thresholds.
- The system is therefore best described as a **layered heuristic mastery-and-progression engine with durable state and outcome feedback**, not as a formal knowledge tracer.

That is a respectable place for a pilot system to be. It is also the reason `R4` is still active.

## Current architecture

The current path is split across a few cooperating backend services:

- [observation_profile_update.py](/Users/sfw/Development/dibble/src/dibble/services/observation_profile_update.py): writes learner observations back into KC/LO mastery.
- [ordinary_mastery_profiles.py](/Users/sfw/Development/dibble/src/dibble/services/ordinary_mastery_profiles.py): builds target-scoped cross-session mastery summaries such as `durable_mastery`, `emerging_mastery`, `support_dependent`, and `fragile`.
- [progression_ownership.py](/Users/sfw/Development/dibble/src/dibble/services/progression_ownership.py): decides whether to stay on target, hold, rebuild prerequisites, bridge, or attempt transfer.
- [learner_progression_service.py](/Users/sfw/Development/dibble/src/dibble/services/learner_progression_service.py): classifies curriculum outcomes as `active`, `ready`, `blocked`, or `mastered`.
- [mastery_decay.py](/Users/sfw/Development/dibble/src/dibble/services/mastery_decay.py): discounts stale KC mastery at read time.
- [progression_outcome_tracker.py](/Users/sfw/Development/dibble/src/dibble/services/progression_outcome_tracker.py): grades whether prior hold/transfer/rebuild decisions helped.
- [progression_outcome_signals.py](/Users/sfw/Development/dibble/src/dibble/services/progression_outcome_signals.py): turns those graded outcomes into bounded threshold adjustments.

## What state is durable today

The durable learner contract lives in [profile.py](/Users/sfw/Development/dibble/src/dibble/models/profile.py).

For mastery/progression, the important fields are:

- `knowledge_state.kc_mastery`: current KC-level mastery scores.
- `knowledge_state.lo_mastery`: LO-level mastery scores.
- `knowledge_state.kc_last_practiced`: timestamps used for read-time decay.
- ordinary mastery summaries emitted through audit/profile signals and then reused in later progression decisions.
- learner flow / session-control state that remembers the current phase, active target KCs, deferred return targets, and next-step intent.

This means Dibble already has **stateful adaptation**, but the state is mostly represented as scores, labels, and bounded threshold logic rather than hidden latent variables or learned transition parameters.

## How mastery writeback works

Observation writeback is the first major layer.

When a learner completes practice or remediation work, [ObservationProfileUpdater.apply](/Users/sfw/Development/dibble/src/dibble/services/observation_profile_update.py) tries to link that observation back to explicit KC/LO targets and infer an observed mastery score. The score is based on:

- completion
- learner confidence
- support level
- hints used
- error count
- pause behavior
- pace adjustment

The updater then blends the observed score into existing `kc_mastery` / `lo_mastery` values with an evidence weight that depends on:

- evidence strength
- target linkage quality
- repeated supporting observations
- low-support success vs heavy-support dependence
- the current ordinary mastery summary, when available

Important properties of the current writeback model:

- It is **target-scoped**, not a global learner score.
- It is **continuous**, not binary mastered/not-mastered.
- It is **heuristic blend logic**, not a parameterized posterior update.
- It already distinguishes stronger and weaker evidence, which is good.
- It does **not** currently estimate per-KC slip/guess/learn parameters or uncertainty intervals.

## How ordinary mastery summaries work

The second major layer is the cross-session "ordinary mastery" summary.

[ordinary_mastery_profiles.py](/Users/sfw/Development/dibble/src/dibble/services/ordinary_mastery_profiles.py) looks at recent matching `learner.observe` events over a 28-day window and builds a summary using:

- recency-weighted average observed mastery
- low-support success rate
- high-support dependency rate
- session count
- trend across recent vs older observations
- volatility of observed mastery

The summary emits one of these labels:

- `insufficient`
- `fragile`
- `support_dependent`
- `emerging_mastery`
- `durable_mastery`

The key thresholds in the current implementation are:

- fewer than 2 matched observations -> `insufficient`
- high-support dependency rate >= `0.60` and low-support success rate <= `0.35` -> `support_dependent`
- stable, multi-session evidence with average mastery >= `0.72`, low-support success >= `0.50`, and high-support dependency <= `0.25` -> `durable_mastery`
- average mastery >= `0.62` with some low-support success -> `emerging_mastery`
- average mastery < `0.52` usually -> `fragile`
- trend delta >= `0.06` -> `improving`
- trend delta <= `-0.06` -> `declining`
- volatility around `0.12+` starts to matter; `0.18+` is treated as highly unstable

This layer is one of Dibble's strongest current design choices. It gives the system a way to distinguish:

- high scores earned independently
- high scores earned only with heavy scaffolding
- unstable "looks mastered until you look closer" patterns

That is more nuanced than a plain mastery threshold, even though it is still heuristic.

## How stale mastery is handled

[mastery_decay.py](/Users/sfw/Development/dibble/src/dibble/services/mastery_decay.py) applies read-time decay to KC mastery before outcome classification:

- 0-14 days: no decay
- 15-28 days: decay toward `0.92`
- 29-56 days: decay toward `0.78`
- beyond 56 days: decay toward floor `0.60`

This helps prevent stale high mastery from silently unlocking future work forever. It is not a retention scheduler, but it is a useful honesty mechanism.

## How progression ownership works

[progression_ownership.py](/Users/sfw/Development/dibble/src/dibble/services/progression_ownership.py) decides whether the backend should:

- stay on the requested target
- hold target
- hold repair target
- hold bridge target
- rebuild prerequisite first
- attempt transfer

Inputs to that decision include:

- requested target KCs
- prerequisite graph / KC sequencing
- within-session adaptation state
- same-session progression evidence from recent observations and Socratic assessments
- durable ordinary mastery summaries
- recent graded outcomes of prior hold/transfer/rebuild decisions

Important current thresholds and behaviors:

- same-session transfer evidence usually needs average observed mastery around `0.66`, or `0.72` for stronger bridge/repair release
- stronger release also expects low-support success counts, especially on repair/bridge paths
- weak same-session evidence below roughly `0.58` to `0.62` tends to hold the learner
- ordinary mastery can trigger `hold_target` / `hold_repair_target` when support-dependence or fragility confidence crosses thresholds around `0.45` to `0.65`, then those thresholds are nudged by trend, volatility, and prior outcome reliability
- assessment requests are rewritten back into practice when the mastery gate says transfer is premature

This is the place where Dibble most clearly behaves like a heuristic control system:

- same-session evidence says whether to release
- cross-session ordinary evidence says whether the release would be durable
- prior graded outcomes slightly tighten or loosen later thresholds

## How curriculum outcomes are classified

[learner_progression_service.py](/Users/sfw/Development/dibble/src/dibble/services/learner_progression_service.py) turns KC state into curriculum-facing outcome state.

Base thresholds:

- mastery threshold: `0.80`
- prerequisite-ready threshold: `0.65`

An outcome is treated as mastered only when:

- every required KC is at least at the prerequisite threshold
- the average KC mastery meets the mastery threshold
- the outcome is not blocked by the quality gate

The quality gate uses ordinary mastery summaries so an outcome can stay `ready` instead of `mastered` when required KCs still look:

- `support_dependent`
- `fragile`

Trend also adjusts thresholds:

- improving trend lowers mastery/prerequisite thresholds slightly
- declining trend raises them slightly

This gives Dibble a useful distinction between:

- "scores are high"
- "scores are high and durable enough to unlock dependents"

Again, that is good product behavior, but it is implemented through fixed thresholds and rule interactions rather than a formal state-space model.

## How the feedback loop closes today

The current system does have a real feedback loop.

[progression_outcome_tracker.py](/Users/sfw/Development/dibble/src/dibble/services/progression_outcome_tracker.py) looks back at recent progression decisions and grades them:

- holds are positive if mastery later reaches about `0.70` or improves materially
- transfers are positive if target mastery later reaches about `0.70`
- transfers are negative if mastery drops below `0.50`
- prerequisite rebuilds are positive if mastery improves by more than `0.05`

[progression_outcome_signals.py](/Users/sfw/Development/dibble/src/dibble/services/progression_outcome_signals.py) then converts recent positive/negative rates into bounded adjustments:

- hold confidence threshold adjustment up to about `0.06`
- transfer confidence adjustment up to about `0.05`
- prerequisite threshold adjustment up to about `0.04`

This is valuable because Dibble is no longer a pure one-way rule engine. It can react to whether its own progression heuristics have recently been helping or hurting.

Still, this is **meta-tuning of heuristics**, not a learned knowledge model.

## What the current model does well

- It is inspectable. Operators can understand why the learner was held, released, or redirected.
- It distinguishes same-session evidence from cross-session durability.
- It uses KC-level state, not only coarse lesson completion.
- It discounts stale mastery.
- It guards against false-positive mastery caused by scaffolding dependence.
- It already has an outcome loop that can make the thresholds a bit less brittle.

For a pilot or small operator-managed deployment, those are meaningful strengths.

## Where the current ceiling is

The current ceiling is not that the system has no learner model. The ceiling is that the learner model is still **composed out of independent heuristic layers**.

The main limitations are:

- no explicit probabilistic latent mastery estimate per KC
- no per-KC learn/slip/guess parameters
- no principled uncertainty propagation
- no formal transition model across attempts
- no sequence model that learns from large histories
- threshold interactions are hand-tuned and can become hard to reason about in combination
- calibration is evaluated indirectly through downstream outcomes, not through held-out prediction quality

In practice, that means the system may behave well locally while still being hard to tune globally.

## What empirical failure should look like

`R4` should not be considered triggered just because the system is heuristic. It should be triggered by observed failure patterns.

The most important failure signals are:

- repeated false-positive mastery:
  outcomes marked `mastered` or learners released to transfer, followed by near-term failure on the same or dependent KCs
- repeated premature advancement:
  transfer or next-outcome progression looks correct in the moment but produces negative progression outcomes soon after
- repeated over-holding:
  hold decisions accumulate negative outcomes, suggesting the system is slowing learners down unnecessarily
- unstable cross-session classification:
  learners oscillate between `fragile`, `emerging_mastery`, and release/hold states without meaningful new evidence
- poor prediction value:
  current KC mastery and ordinary mastery labels stop being good predictors of whether the next independent attempt succeeds
- poor prerequisite honesty:
  learners repeatedly enter downstream outcomes that later show blocked or repair-heavy behavior the model should have anticipated

## What we should measure before replacing the model

Before migrating to BKT-per-KC or another formal KT approach, we should measure the current system on a fixed eval slice.

Recommended metrics:

- hold decision positive rate
- transfer decision positive rate
- prerequisite rebuild positive rate
- false-positive mastery rate:
  share of newly mastered outcomes followed by failure/repair within the next N relevant observations
- release regret rate:
  share of transfer releases followed by a negative progression outcome
- over-hold rate:
  share of hold decisions later judged negative
- outcome mastery stability:
  how often an outcome flips out of a "done" state after being treated as mastered
- next-attempt success prediction:
  correlation between current KC/ordinary mastery state and independent attempt success

If these metrics look healthy and stable, the heuristic model may still be the right tradeoff for this stage. If they do not, we should move to a more formal learner-state model.

## Recommended next step after this note

The next step is not immediately "replace the model." The next step is:

1. treat this document as the baseline description of the current system
2. add a small measurement pass over recent pilot/proof data for the metrics above
3. decide whether the current heuristic stack is:
   - good enough for the next pilot phase
   - good enough with more tuning
   - or ready to be upgraded to BKT-per-KC or another explicit KT path

## Bottom line

Dibble currently has a **real, stateful, inspectable mastery-and-progression engine**.

It is more sophisticated than "advance on percent correct," but it is still fundamentally a **heuristic control system with outcome feedback**, not a formal knowledge-tracing model.

That means `R4` is still a real risk, but it is now a **well-scoped adaptation ceiling**, not an architectural mystery.
