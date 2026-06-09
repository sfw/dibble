# Dibble — Risk Register

**Original audit source:** [DeepWiki — sfw/dibble](https://deepwiki.com/sfw/dibble) at commit `ef5c7960`  
**Current-state update:** June 8, 2026  
**Scoring:** Severity × Likelihood, both on a 1–5 scale. **Risk score** = S × L. Scores are directional; the tier groupings below reflect both score and current implementation priority, so some reduced items remain in higher-attention buckets when their residual risk still deserves near-term work.

This document is now a **current-state register**, not a verbatim copy of the original audit. A few of the original findings were accurate at the time but are now partially or fully addressed in code. Those are marked explicitly below.

Status meanings:

- **Active:** still materially true and should drive near-term work.
- **Reduced:** the underlying concern is still worth tracking, but the original audit overstated it relative to the current codebase.
- **Closed / stale:** the original audit claim no longer matches how the system works today.

---

## What changed since the original audit

The following items from the original audit no longer describe the system accurately:

- **Cross-learner reuse is not absent anymore.** Dibble now has a curriculum-safe shared library path, exact-key cross-learner reuse, remote/local library abstraction, and outcome-aware ranking.
- **Modality preference is no longer purely system-wide.** Routing now uses learner-scoped modality affinity plus learner-scoped durable routing priors.
- **Math verification is no longer absent.** Dibble now has both `MathSanityRule` checks and a bounded symbolic linear-equation verifier, though broader subject coverage is still incomplete.
- **Mock/provider posture is more visible.** `/ready` now surfaces provider readiness, mock fallback state, and embedder posture.
- **Autonomous teacher is clearly a runtime subsystem.** It is no longer fair to describe it as an ambiguous internal harness.
- **A retention scheduler now exists in stage-1 form.** Dibble can persist, nominate, and inspect retention-review candidates even though due review is not yet a first-class runtime action.

The original audit is still strategically useful, but it should not be treated as a literal description of the current implementation.

---

## Tier 1 — highest-attention risks to address before scaling

### R1 — Modality breadth still undershoots the product thesis
- **Status:** Active
- **Lens:** Multimodal generation
- **Severity:** 5
- **Likelihood:** 5
- **Score:** 25
- **Current evidence:** The modality plugin system is real, but the practical set is still `text`, `narrative`, and `diagram`.
- **Why it matters:** The architecture supports modality growth, but the product thesis still sounds broader than the delivered experience.
- **Mitigation (Product + Eng):** add one audio path and one genuinely interactive path, or deliberately narrow the product narrative.
- **Watch-for trigger:** demos start feeling like “text plus formatting” rather than “many modalities.”

### R3 — Math correctness verification is stronger, but still not broad enough for a math-heavy product
- **Status:** Reduced
- **Lens:** AI quality
- **Severity:** 5
- **Likelihood:** 3
- **Score:** 15
- **Current evidence:** Dibble now has `MathSanityRule` plus bounded symbolic checks for linear equations and arithmetic equalities. This is materially better than the earlier posture, but it is still not a full subject-aware verifier for richer math content.
- **Why it matters:** For K-12 math, “mostly right” is not enough.
- **Mitigation (Eng + Pedagogy):** extend the current verifier toward richer equation families, answer validation, and step-level checks where possible.
- **Watch-for trigger:** any live pilot reports incorrect math or contradictory worked examples.

### R4 — The knowledge-tracing ceiling is still heuristic
- **Status:** Active
- **Lens:** Adaptive learning loop
- **Severity:** 4
- **Likelihood:** 4
- **Score:** 16
- **Current evidence:** The system now has much richer state, outcome tracking, and progression evidence than the original audit assumed. But the mastery and progression loop is still fundamentally heuristic / threshold / weighted-history driven rather than a formal KT model.
- **Why it matters:** This likely caps adaptation quality and makes long-run tuning harder.
- **Mitigation (Eng + Pedagogy):** document the current model clearly, define target failure metrics, and evaluate migration options such as BKT-per-KC or another explicit learner-state model.
- **Watch-for trigger:** repeated false-positive mastery or repeated “advance then fail later” patterns.

### R6 — Embedding fallback is safer now, but retrieval quality can still degrade if embedder posture is weak
- **Status:** Reduced
- **Lens:** AI orchestration
- **Severity:** 5
- **Likelihood:** 2
- **Score:** 10
- **Current evidence:** Dibble now surfaces embedder identity in `/ready`, treats local-hash embeddings as not-ready for real-provider household/managed runtimes, and provides stronger setup guidance. The remaining risk is degraded retrieval quality in fallback or misconfigured environments, not silent invisibility.
- **Why it matters:** Retrieval quality is a hidden dependency for most of the content pipeline.
- **Mitigation (Eng + Ops):** keep failing closed for strict runtime modes, and add stronger degraded telemetry and trend visibility when fallback embedding is used in non-strict environments.
- **Watch-for trigger:** retrieval or grounding quality drops without visible provider or prompt changes.

### R15 — Offline content-quality evaluation exists now, but coverage is still narrow
- **Status:** Reduced
- **Lens:** AI quality / release process
- **Severity:** 4
- **Likelihood:** 3
- **Score:** 12
- **Current evidence:** Dibble now has an offline content-quality eval harness plus a real golden corpus and regression command. The remaining gap is breadth and depth of corpus coverage, not absence of a harness.
- **Why it matters:** Prompt/model changes can still regress content quality without a fast automated gate.
- **Mitigation (Eng + Pedagogy):** grow the corpus across more grades, intervention types, and failure patterns, and make it part of every provider / prompt / template change path.
- **Watch-for trigger:** content quality regressions are detected only through manual review or pilot usage.

---

## Tier 2 — important follow-on work before broad release

### R2 — Cross-learner reuse exists, but semantic dedup is still missing
- **Status:** Reduced
- **Lens:** Scalability & cost
- **Severity:** 4
- **Likelihood:** 3
- **Score:** 12
- **Current evidence:** Dibble now supports curriculum-safe shared library reuse, exact-key cache reuse across learners, and ranked candidate selection. What it does not yet have is broader semantic dedup across near-equivalent requests.
- **Mitigation (Eng):** introduce a second-layer semantic reuse mechanism above exact curriculum-safe selection keys.
- **Watch-for trigger:** LLM spend rises materially even though many requests are near-identical in curricular shape.

### R5 — Learner-specific modality state exists, but the preference model is still shallow
- **Status:** Reduced
- **Lens:** Personalization
- **Severity:** 3
- **Likelihood:** 4
- **Score:** 12
- **Current evidence:** Modality routing already uses learner-scoped affinities, priors, and recent outcomes. The remaining gap is that this preference model is still relatively lightweight and may not capture durable learner-specific modality strategy well.
- **Mitigation (Eng):** deepen learner-scoped modality preference state and calibrate it against repeated outcome evidence.
- **Watch-for trigger:** pilots show the system rotating modalities, but not in ways that feel meaningfully individualized.

### R7 — No strong course-scale narrative coherence layer
- **Status:** Active
- **Lens:** Pedagogy / generation
- **Severity:** 4
- **Likelihood:** 3
- **Score:** 12
- **Mitigation:** add a course-architect planning layer or other durable narrative scaffolding above per-KC generation.

### R8 — Single SQLite architecture may still become a concurrency bottleneck in managed deployments
- **Status:** Active
- **Lens:** Scalability & cost
- **Severity:** 3
- **Likelihood:** 4
- **Score:** 12
- **Mitigation (Eng):** keep SQLite for households, but add a Postgres/pgvector-backed managed path behind existing protocol seams.

### R9 — No explicit generation-budget controller
- **Status:** Active
- **Lens:** Scalability & cost
- **Severity:** 3
- **Likelihood:** 4
- **Score:** 12
- **Mitigation:** add `GenerationBudgetController` with modality-aware and household-aware hard limits and cheaper fallbacks.

### R10 — Domain-specific verification remains thin outside basic text and arithmetic checks
- **Status:** Active
- **Lens:** AI quality
- **Severity:** 4
- **Likelihood:** 3
- **Score:** 12
- **Mitigation:** layer in subject-specific validators for math, code, unit checking, chemistry, and richer diagram verification where relevant.

### R11 — Misconception detection likely misses paraphrase and deeper semantic variants
- **Status:** Active
- **Lens:** Adaptive learning loop
- **Severity:** 3
- **Likelihood:** 4
- **Score:** 12
- **Mitigation:** add embedding-assisted misconception clustering and a learned misconception lexicon.

### R12 — Retention scheduling exists in stage 1, but due review is not yet a first-class runtime behavior
- **Status:** Reduced
- **Lens:** Pedagogy
- **Severity:** 3
- **Likelihood:** 3
- **Score:** 9
- **Current evidence:** Dibble now has durable retention-review candidates, nomination from observation/progression/planning evidence, suppression rules, and admin inspectability. The remaining gap is stage-2 runtime integration into planning, warming, and household-facing suggestion flows.
- **Mitigation:** complete retention scheduler stage 2 so due reviews can shape runtime planning and pre-generation in a bounded, explainable way.

### R13 — Central observability is still thin for managed deployments
- **Status:** Reduced
- **Lens:** Operations
- **Severity:** 3
- **Likelihood:** 3
- **Score:** 9
- **Current evidence:** Dibble now has much stronger trace, readiness, audit, and rollout observability than the original audit assumed. The remaining gap is export / centralization, not absence.
- **Mitigation (Ops):** add pluggable OTLP or another managed export path while keeping local-first defaults.

### R14 — Mock fallback production risk is reduced but still configuration-sensitive
- **Status:** Reduced
- **Lens:** AI orchestration / operations
- **Severity:** 3
- **Likelihood:** 2
- **Score:** 6
- **Current evidence:** Mock fallback is now surfaced in readiness and deployment docs, and live proof explicitly disables it. The remaining risk is misconfiguration, not silent invisibility.
- **Mitigation (Eng + Ops):** make managed/production modes fail closed unless mock fallback is explicitly and deliberately allowed.

### R16 — Narrow SVG hardening reduced the immediate diagram risk, but raw SVG remains a ceiling
- **Status:** Reduced
- **Lens:** Multimodal generation / AI quality
- **Severity:** 3
- **Likelihood:** 3
- **Score:** 9
- **Current evidence:** Dibble now constrains supported diagram shapes, validates SVG structure and accessibility more aggressively, and uses a stronger fallback. The remaining risk is semantic fidelity and long-run expressiveness, not totally unconstrained SVG output.
- **Mitigation:** keep the narrowed SVG path for now, and only move to structured renderers if proof or pilot evidence shows the hardened path is still insufficient.

---

## Tier 3 (track, but not the highest-leverage next work)

### R17 — Measurement model for affective and cognitive-load state still needs clearer documentation
- **Status:** Active
- **Severity:** 3
- **Likelihood:** 2
- **Score:** 6
- **Mitigation:** document proxies, confidence, and update mechanics, then tie calibration back to outcome data.

### R18 — No multimodal input path yet
- **Status:** Active
- **Severity:** 3
- **Likelihood:** 3
- **Score:** 9
- **Mitigation:** add voice, image, handwriting, or canvas input only when it strengthens a concrete learner workflow.

### R19 — Interest / locale / cultural personalization remains shallow
- **Status:** Active
- **Severity:** 2
- **Likelihood:** 4
- **Score:** 8
- **Mitigation:** extend learner profile and example libraries with locale and interest-aware variation.

### R20 — Compliance posture is still not fully documented
- **Status:** Active
- **Severity:** 4
- **Likelihood:** 2
- **Score:** 8
- **Mitigation:** publish a clear FERPA / COPPA / GDPR posture memo and data-handling summary.

### R21 — No offline/PWA learner experience
- **Status:** Active
- **Severity:** 2
- **Likelihood:** 3
- **Score:** 6
- **Mitigation:** only prioritize if household reliability or field conditions make this important.

### R22 — Frontend remains intentionally thin
- **Status:** Active but acceptable
- **Severity:** 2
- **Likelihood:** 3
- **Score:** 6
- **Mitigation:** preserve backend-owned logic, but allow narrowly scoped low-risk optimistic UX where it meaningfully improves responsiveness.

### R23 — Modality prior weighting may still be brittle at low evidence counts
- **Status:** Active
- **Severity:** 3
- **Likelihood:** 2
- **Score:** 6
- **Mitigation:** keep tuning weak-evidence fallbacks and verify smoothing behavior with small-sample cohorts.

### R24 — No explicit bias/fairness audit on generated content
- **Status:** Active
- **Severity:** 4
- **Likelihood:** 2
- **Score:** 8
- **Mitigation:** add bias-pattern rules and periodic audit corpora for child-facing content.

### R25 — Autonomous teacher runtime ambiguity is closed
- **Status:** Closed / stale
- **Severity:** 1
- **Likelihood:** 1
- **Score:** 1
- **Current evidence:** The autonomous teacher is now a clear runtime subsystem used through household and learner workspace flows.
- **Mitigation:** none needed beyond documentation hygiene.

---

## Revised heatmap summary

### Tier 1 — act this quarter

1. **R1:** modality breadth vs thesis
2. **R3:** stronger math correctness verification
3. **R6:** production-safe embedder enforcement and visibility
4. **R15:** offline content-quality eval harness
5. **R4:** formalize/document the knowledge-tracing path and decide whether to evolve beyond heuristics

### Tier 2 — important, but no longer emergency

1. **R2:** semantic reuse above exact curriculum-safe reuse
2. **R5:** deepen learner-specific modality preference modeling
3. **R8:** managed-deployment database path
4. **R9:** generation-budget control
5. **R16:** structured diagram rendering

---

## Practical conclusion

The original audit was valuable, but the current codebase is meaningfully stronger than that snapshot implied:

- rollout, observability, readiness, and governance are much better
- curriculum-safe shared library reuse is real
- learner-scoped modality adaptation is real
- live proof and operational hardening have reduced several deployment risks

The highest-leverage remaining risks are now less about missing architecture and more about:

- **quality ceilings** (`R3`, `R15`, `R16`)
- **adaptation ceilings** (`R4`, `R5`, `R11`, `R12`)
- **production safeguards** (`R6`, `R8`, `R9`, `R20`)
- **product-thesis credibility** (`R1`, `R18`)
