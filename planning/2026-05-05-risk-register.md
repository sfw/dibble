# Dibble — Risk Register

**Reference:** [DeepWiki — sfw/dibble](https://deepwiki.com/sfw/dibble) (commit `ef5c7960`)
**Scoring:** Severity × Likelihood, both on a 1–5 scale. **Risk score** = S × L. Anything ≥ 16 is treated as a tier-1 risk.

Severity is "if it happens, how bad is it for the product." Likelihood is "in the next 12 months under current trajectory."

The register groups risks into product/strategy, AI quality, learning-science, scalability/cost, security/compliance, and operations. Each risk has a recommended mitigation owner role (Product, Eng, Pedagogy, Ops, Security) and a primary mitigation.

---

## Tier 1 (score ≥ 16) — fix before scaling

### R1 — Modality story does not match the product thesis
- **Lens:** Multimodal generation
- **Severity:** 5 — the central product claim is *"many different modalities."* Three modalities (text, narrative, SVG diagram) is not many.
- **Likelihood:** 5 — this is the present state of the code.
- **Score:** 25
- **Evidence:** [4.5 Modality Plugins](https://deepwiki.com/sfw/dibble/4.5-modality-plugins). Only `text`, `narrative`, `diagram` plugins exist.
- **Why it matters:** product positioning will not survive a serious demo.
- **Mitigation (Product + Eng):** prioritize `audio` (TTS) and one interactive (Desmos/JSXGraph or sandboxed widget) modality plugin in the next quarter; map a 12-month modality roadmap to the strategic narrative.
- **Watch-for trigger:** marketing/sales/demo conversations begin to feel constrained.

### R2 — Cross-learner content reuse is absent; cost will run away with multimodal expansion
- **Lens:** Scalability & cost
- **Severity:** 4 — directly affects unit economics and subsidy of pilots.
- **Likelihood:** 4 — adding video / audio / simulation will multiply per-interaction cost 3–10×.
- **Score:** 16
- **Evidence:** `generated_content` cache is keyed per-generation. No semantic dedup across learners.
- **Mitigation (Eng):** introduce a content-addressable semantic cache (hash of `kc_id + difficulty_band + modality + grounding_hash + prompt_template_version`) separate from per-learner adaptive variants.
- **Watch-for trigger:** weekly LLM spend / household > forecast.

### R3 — Math correctness has no symbolic verification
- **Lens:** AI quality
- **Severity:** 5 — incorrect math in a K-12-shaped product is brand-defining damage.
- **Likelihood:** 4 — frontier LLMs still produce wrong arithmetic at non-trivial rate, especially on multi-step.
- **Score:** 20
- **Evidence:** `ContentValidator` rules cover grounding, alignment, readability, instruction-block, accessibility. None evaluate arithmetic or algebra.
- **Mitigation (Eng + Pedagogy):** implement `MathCorrectnessRule` using sympy. Reject blocks where computed answer ≠ stated answer. Flag unverifiable steps for review.
- **Watch-for trigger:** any pilot reports incorrect math from the system.

### R4 — Knowledge-tracing model is unspecified; adaptation ceiling is unknown
- **Lens:** Adaptive learning loop
- **Severity:** 4 — caps how good the product can ever become at adaptation.
- **Likelihood:** 4 — the wiki only says "trend-aware logic and mastery decay," which suggests heuristics.
- **Score:** 16
- **Evidence:** [3.2 Mastery Gates](https://deepwiki.com/sfw/dibble/3.2-learner-progression-and-mastery-gates).
- **Mitigation (Eng + Pedagogy):** confirm what's actually in `progression_ownership.py`. If heuristic, plan migration to BKT-per-KC for state and IRT for item selection inside Socratic assessments. Validate against held-out outcome data.
- **Watch-for trigger:** false-positive mastery (learners advancing then failing later) above an internal threshold.

### R5 — Modality preference is system-wide, not per-learner
- **Lens:** Personalization
- **Severity:** 4 — direct gap against the *"adapted for the learner"* clause of the goal.
- **Likelihood:** 4 — substrate exists but no learner-scoped term in routing.
- **Score:** 16
- **Evidence:** [7.3 — Modality Routing Inspection](https://deepwiki.com/sfw/dibble/7.3-operational-observability-and-telemetry) shows scoring components are heuristic + prior + repetition penalty; no per-learner term documented.
- **Mitigation (Eng):** add `ModalityPreferenceState` to `LearnerProfileV2`; have the existing outcome scorer update it; bias the routing prior with a learner-scoped term.
- **Watch-for trigger:** learner research or pilot feedback that "the system picks the same kind of content even when I struggle with it."

### R6 — `LocalHashEmbedder` will silently degrade RAG in misconfigured deployments
- **Lens:** AI orchestration
- **Severity:** 5 — RAG drives all grounding; if it fails silently, content quality collapses.
- **Likelihood:** 4 — easy to misconfigure; nothing in the wiki suggests boot-time enforcement.
- **Score:** 20
- **Evidence:** [4.4](https://deepwiki.com/sfw/dibble/4.4-content-moderation-validation-and-rag-retrieval) — embedder is `LocalHashEmbedder` or `OpenAICompatibleEmbedder`; the former is for tests.
- **Mitigation (Eng + Ops):** make `bootstrap` refuse to enter `production` mode without a real embedder. Surface embedder identity in `/ready`. Emit a warning into telemetry when hash-embedder is active.
- **Watch-for trigger:** retrieval-relevance metrics drop without an upstream change.

---

## Tier 2 (score 9–15) — fix before broad release

### R7 — No course-scale narrative coherence layer
- **Lens:** Multimodal generation, Pedagogy
- **Severity:** 4
- **Likelihood:** 3
- **Score:** 12
- **Mitigation:** introduce a `Course` first-class entity and a course-architect planning step that emits cross-KC narrative grounding (running examples, metaphors, characters) consumed by per-KC generation.

### R8 — Single SQLite for everything will hit write contention as modalities multiply
- **Lens:** Scalability & cost
- **Severity:** 3 — recoverable with a swap; the protocol abstraction makes this clean.
- **Likelihood:** 4 — predictive warming + audio + video generation in parallel = many concurrent writers.
- **Score:** 12
- **Mitigation (Eng):** Postgres + pgvector adapter behind the existing `protocols.py` interfaces for the multi-tenant path. Keep SQLite for households.

### R9 — No generation-budget primitive
- **Lens:** Scalability & cost
- **Severity:** 3
- **Likelihood:** 4
- **Score:** 12
- **Mitigation:** `GenerationBudgetController(learner, modality, KC) → token_budget`; hard-stop at threshold and fall back to a cheaper modality.

### R10 — No symbolic / domain-specific verification beyond text rules
- **Lens:** AI quality
- **Severity:** 4
- **Likelihood:** 3
- **Score:** 12
- **Mitigation (Eng + Pedagogy):** in addition to math, add code-correctness (sandboxed run), unit/dimension checks for physics, ChemicalEquationBalanceRule for chemistry.

### R11 — Misconception detector relies on term-normalization; misses paraphrase
- **Lens:** Adaptive learning loop
- **Severity:** 3
- **Likelihood:** 4
- **Score:** 12
- **Evidence:** [5 Assessment & Remediation](https://deepwiki.com/sfw/dibble/5-assessment-and-remediation) — `_normalize_terms` term match.
- **Mitigation:** layer in embedding-based misconception clustering with the existing embedder; learn a misconception lexicon over time.

### R12 — No spaced-repetition primitive; long-term retention is left to "mastery decay"
- **Lens:** Pedagogy
- **Severity:** 3
- **Likelihood:** 4
- **Score:** 12
- **Mitigation:** `RetentionScheduler` (FSRS / SM-2) emits review candidates into the predictive warm queue.

### R13 — Telemetry is local-file; no central observability for managed deployments
- **Lens:** Operations
- **Severity:** 3
- **Likelihood:** 3
- **Score:** 9
- **Mitigation (Ops):** pluggable telemetry export (OTLP). Default to local files for sovereign households.

### R14 — Mock LLM fallback could silently serve mock content in production
- **Lens:** AI orchestration / Operations
- **Severity:** 4
- **Likelihood:** 2 (dependent on misconfiguration)
- **Score:** 8 (just below Tier 2; flagged anyway)
- **Mitigation (Eng + Ops):** config-gate `MockLLMProvider` use behind a `production_allow_mock=false` setting. Emit prominent telemetry when mock is active. Surface in `/ready`.

### R15 — No content-quality offline eval harness
- **Lens:** AI orchestration / quality
- **Severity:** 4
- **Likelihood:** 3
- **Score:** 12
- **Mitigation:** golden corpus of (KC, grade, intervention_type, modality) → expected-properties; runs on every prompt-template / model change.

### R16 — Inline-SVG diagram path will produce poor visuals at scale
- **Lens:** Multimodal generation / AI quality
- **Severity:** 3
- **Likelihood:** 4
- **Score:** 12
- **Mitigation:** replace LLM-generated raw SVG with structured DSLs the LLM is good at producing — KaTeX/MathJax for equations, Desmos JSON for graphs, JSXGraph for geometry, Vega-Lite for data viz. Renderer in the frontend.

---

## Tier 3 (score 4–8) — track and fix as you can

### R17 — `AffectiveState` and `CognitiveLoadState` measurement model not documented
- **Severity:** 3 — affect-driven adaptations may be miscalibrated
- **Likelihood:** 2
- **Score:** 6
- **Mitigation:** document the proxy inputs or learned classifier; bring it into outcome-scoring loop.

### R18 — No multimodal *input* (image, audio, handwriting)
- **Severity:** 3
- **Likelihood:** 3
- **Score:** 9
- **Mitigation:** Whisper STT for voice; vision-LLM grading for handwritten work; canvas input primitive on the frontend.

### R19 — No interest / locale / cultural personalization
- **Severity:** 2 — engagement effect is real but not blocking
- **Likelihood:** 4
- **Score:** 8
- **Mitigation:** add `interests` vector and `locale` to profile; pass into prompt context; build per-locale example libraries.

### R20 — Compliance posture (FERPA / COPPA / GDPR) not fully documented
- **Severity:** 4
- **Likelihood:** 2 — household-first model with local data limits exposure
- **Score:** 8
- **Mitigation:** publish a compliance one-pager; expand `CurriculumLibraryPrivacyAudit` to cover learner-record audit; document data residency and deletion.

### R21 — No PWA / offline learner experience
- **Severity:** 2
- **Likelihood:** 3
- **Score:** 6
- **Mitigation:** PWA shell with pre-warmed content for the next N steps; tolerated-offline session that syncs on reconnect.

### R22 — Frontend is a thin renderer with no client-side bias / parallelization
- **Severity:** 2
- **Likelihood:** 3
- **Score:** 6
- **Mitigation:** keep the backend-owns-logic principle but allow thin client-side optimistic interactions (e.g., MCQ check) so the loop feels instantaneous. Backend remains source of truth.

### R23 — `prior_score` source unverified; could be over-weighted at small N
- **Severity:** 3
- **Likelihood:** 2
- **Score:** 6
- **Mitigation:** verify Bayesian smoothing in `ModalityRoutingHarness`; ensure modalities don't get penalized into oblivion at low traffic.

### R24 — No bias / fairness audit on generated content
- **Severity:** 4 — child-facing content
- **Likelihood:** 2
- **Score:** 8
- **Mitigation:** bias-pattern rule (gender, race, ability stereotypes in word problems and narratives); periodic audit corpus.

### R25 — `Autonomous Teacher Harness` purpose / runtime use unclear from wiki
- **Severity:** 2
- **Likelihood:** 2
- **Score:** 4
- **Mitigation:** clarify if this is a runtime system or a test/eval harness. Treat as internal QA tool unless documented otherwise.

---

## Risk heatmap

Rows are likelihood (L), columns are severity (S). Risk score = S × L. Tier-1 cells (score ≥ 16) are **bolded**.

| L \ S | S=1 | S=2 | S=3 | S=4 | S=5 |
|---|---|---|---|---|---|
| **L=5** | — | — | — | — | **R1** (25) |
| **L=4** | — | R19 | R8, R9, R11, R12, R16 | **R2, R4, R5** (16) | **R3, R6** (20) |
| **L=3** | — | R21, R22 | R13, R18 | R7, R10, R15 | — |
| **L=2** | — | R25 | R17, R23 | R14, R20, R24 | — |
| **L=1** | — | — | — | — | — |

**Tier-1 (≥16):** R1 (25), R3 (20), R6 (20), R2 (16), R4 (16), R5 (16) — six risks.

---

## Top 5 to act on this quarter

1. **R1 + R5 together:** ship audio (TTS) + interactive (Desmos/JSXGraph) modalities, *and* per-learner modality preference.
2. **R3:** `MathCorrectnessRule` (sympy).
3. **R6:** boot-time enforcement of a real embedder for production mode.
4. **R2:** semantic cross-learner content cache.
5. **R4:** confirm and document the knowledge-tracing model; plan BKT migration if heuristic.

These five address the most visible gaps against the stated product goal and the most damaging quality risks.
