# Dibble Modality Preference Depth Assessment

**Date:** June 8, 2026  
**Source risks:** `R5` and `R23` in [2026-05-05-risk-register.md](/Users/sfw/Development/dibble/planning/2026-05-05-risk-register.md)  
**Related plan:** [2026-05-07-risk-reduction-execution-plan.md](/Users/sfw/Development/dibble/planning/2026-05-07-risk-reduction-execution-plan.md)

## Purpose

This note answers a narrow question:

Is Dibble's current learner-specific modality system still "shallow" enough that we should deepen it now?

Short answer:

- The old audit language is now outdated.
- Dibble already has a **real learner-scoped modality adaptation loop**.
- The remaining shallowness is **not** "no learner state." The remaining shallowness is that downstream consumers collapse rich routing evidence into coarse global preferences too early.
- Because of that, the next move should be **measurement and selective refinement**, not a large new modality-preference subsystem.

## What Dibble already does well

The current modality path is stronger than the earlier audit assumed.

### 1. Routing is learner-scoped, not system-wide

[modality_routing.py](/Users/sfw/Development/dibble/src/dibble/services/harness/modality_routing.py) starts from learner-specific state:

- `profile.learning_preferences.modality_affinity`
- learner cognitive-load state
- request cues
- pedagogical move / intervention type
- requested content type
- learner-scoped durable routing priors

So the first-order decision is already personalized.

### 2. Durable modality priors exist

[ModalityRoutingPrior](/Users/sfw/Development/dibble/src/dibble/models/generation.py) stores per-learner modality evidence for:

- plugin scope
- composition scope
- context key
- evidence count
- average outcome score
- average engagement score
- average progress score
- recent deltas
- positive outcome rate
- recovery attempts and recovery success

These priors are persisted through [modality_routing_prior_store.py](/Users/sfw/Development/dibble/src/dibble/services/modality_routing_prior_store.py), so the system already learns across sessions.

### 3. Outcome feedback updates modality state automatically

[outcome_driven_adaptation.py](/Users/sfw/Development/dibble/src/dibble/services/outcome_driven_adaptation.py) updates modality priors from `learning.run.summary` events.

That means the learner-specific modality layer is not just configured once. It is adjusted by:

- run summary score
- downstream observation score
- downstream assessment score
- recovery after poor outcomes

This is meaningful adaptation, not static preference storage.

### 4. Routing combines heuristics and priors conservatively

The router uses a bounded mixture of:

- heuristic fit
- plugin prior
- composition prior
- recent outcome delta
- recent engagement delta
- recent progress delta
- repetition penalty
- recovery bonus

It also applies a weak-evidence fallback so a modality with sparse evidence does not displace the heuristic winner too easily.

That is a good current design for a pilot system because it avoids overfitting to thin data.

### 5. Household governance is part of the modality system

[autonomous_teacher_harness.py](/Users/sfw/Development/dibble/src/dibble/services/autonomous_teacher_harness.py) carries modality outcomes into learner relationship state and enforces approval-aware suggestions.

That means modality is already shaped by:

- learner outcomes
- household-approved modalities
- parent approval requirements
- rollout policy

This is more product-real than a pure routing-only design.

## What "shallow" still means today

The current gap is not absence of personalization. The gap is where the personalization gets flattened.

### 1. Heuristic affinities are still coarse

The base learner profile only carries broad affinity buckets in [profile.py](/Users/sfw/Development/dibble/src/dibble/models/profile.py):

- `textual`
- `interactive`
- `visual`
- `video`

But the currently active plugins are essentially:

- `text`
- `narrative`
- `diagram`

So the static profile layer is:

- broad rather than modality-plugin-specific
- not calibrated separately by intervention type
- not explicitly tied to age, subject, or misconception family

That is acceptable for a small modality set, but it will become less expressive as the plugin graph grows.

### 2. Rich contextual priors are collapsed into a single preferred modality

[planning_adaptation.py](/Users/sfw/Development/dibble/src/dibble/services/planning_adaptation.py) computes `preferred_modality` by sorting global plugin priors and returning the single top one.

That loses useful distinctions already available in the routing layer, such as:

- content-type-specific performance
- intervention-type-specific performance
- context-key-specific priors
- composition success vs single-plugin success

In other words:

- routing is contextual
- planning becomes mostly global

That is the clearest remaining shallowness in the current system.

### 3. Autonomous-teacher modality suggestions are intentionally simple

[AutonomousTeacherHarness._suggested_modality](/Users/sfw/Development/dibble/src/dibble/services/autonomous_teacher_harness.py) effectively does this:

- choose a modality default from content type
- fall back to text if the default has poor evidence and text is materially better
- otherwise, if an approved modality has enough samples and average score >= `0.68`, suggest the best one

That is sensible for household safety, but it is a **summary heuristic**, not a nuanced learner model.

It does not yet reason about:

- modality by concept cluster
- modality by recovery pattern
- modality by frustration/load regime
- modality by misconception class

### 4. Priors are learner-scoped, but not richly segmented

The current prior key space is helpful but still narrow:

- plugin
- composition
- context key

The context key includes:

- intent
- requested content type
- target KC ids
- target LO ids
- intervention type
- scaffolding level

That is a good start. But the system does not yet maintain explicit priors for:

- concept-cluster families above literal target overlap
- misconception classes
- overload/recovery regimes
- parent-approved modality transitions
- age/grade-specific modality success patterns

The current contextual scope is therefore stronger than "global only," but not yet semantically rich.

### 5. Evidence aging is weaker than the mastery system

Mastery has explicit read-time decay in [mastery_decay.py](/Users/sfw/Development/dibble/src/dibble/services/mastery_decay.py).

Modality priors currently do **not** have a comparable aging model. They track recency deltas and timestamps, but their averages do not decay directly.

That means old modality wins can stay influential longer than they probably should, especially if the learner changes phase, grade, or support needs.

### 6. There is no explicit exploration strategy

The current router includes:

- weak-evidence fallback
- repetition penalty
- recovery bonus

But it does not run an explicit exploration policy such as:

- optimistic trial budget for under-tested modalities
- structured recovery probes
- deliberate re-sampling after long dormancy

Right now, exploration is incidental rather than designed.

## What is not worth doing yet

Based on the current code, I would **not** recommend immediately adding:

- a new large learner-modality profile model
- heavy ML for modality prediction
- broad cross-learner shared modality preference transfer
- complex Bayesian or bandit machinery for modality alone

Reasons:

- the active modality set is still small
- the current learner-scoped routing loop is already meaningful
- the bigger gap is loss of context downstream, not lack of raw state
- more complexity would be hard to validate without stronger modality evals

## What the best next move is

The best next move is **targeted refinement**, not wholesale expansion.

### Recommendation 1. Keep routing state as the source of truth

Do not build a parallel modality-preference subsystem.

Instead, preserve the current routing stack as the canonical evidence source and improve how planning/household layers consume it.

### Recommendation 2. Stop collapsing everything to one global preferred modality

The highest-value refinement is to replace "single global preferred modality" with a small structured summary such as:

- preferred modality by content family
- preferred modality by concept cluster risk bucket
- preferred modality by recovery pattern

That would let planning stay aligned with what the routing layer already knows, without adding much new state.

### Recommendation 3. Add light recency decay to modality priors

This should be smaller than mastery decay, but some aging is warranted so stale modality wins do not dominate forever.

The goal is not full forgetting. The goal is to:

- prefer recent learner evidence
- make re-evaluation easier after recovery or curriculum shift

### Recommendation 4. Add measurement before deeper modeling

Before deepening the system further, we should add a small eval/inspection pass for modality quality.

Recommended metrics:

- outcome score by modality
- completion rate by modality
- modality decision regret:
  cases where the selected modality underperformed a recently approved alternative with enough evidence
- recovery contribution by modality:
  which modalities are actually associated with rebounds after low-score runs
- concept-cluster modality lift:
  whether some modalities help only in certain cluster/risk contexts
- stale-prior drift:
  whether modalities with old wins keep getting selected despite weaker recent evidence

## Concrete conclusion

The current system is **not too shallow to ship in a pilot**.

It is already:

- learner-scoped
- outcome-updated
- household-governed
- rollout-aware
- inspectable

The remaining shallowness is mainly this:

- the routing layer is contextual
- the downstream planning/suggestion layer is still too global

So the correct next action is:

1. keep the current routing model
2. improve how planning and autonomous-teacher layers summarize modality evidence
3. add light recency decay / modality eval metrics
4. only then decide whether a larger preference model is justified

## Recommended status for `R5`

`R5` should remain **Reduced**, not `Closed`.

Reason:

- the original audit claim that modality state was basically system-wide is no longer accurate
- but the system still compresses rich modality evidence into coarse downstream summaries quickly enough that there is still real room to improve learner-specific modality strategy

## Recommended next implementation slice

If we continue the risk-reduction plan directly from here, the next implementation slice should be:

- add a planning-safe modality summary that preserves at least `content family + risk bucket` distinctions, instead of a single `preferred_modality`

That is the smallest change likely to improve learner-specific modality behavior without reopening architecture.
