# Dibble POC Roadmap

**From current state → instrumented homeschool pilot generating efficacy evidence**

Status: pre-alpha, proof-of-concept development
Target: 5–10 homeschool families, one subject band (Grades 4–6 math), 6–8 week instrumented pilot
Governing principle: **freeze the decision layer, build the experience layer, let the pilot validate the brain.**

---

## 0. Where we are

The codebase has an inverted maturity profile:

| Layer | Maturity | POC verdict |
|---|---|---|
| Adaptive decision stack (routing, calibration profiles, progression holds, mastery gates, outcome trackers) | Over-built | **Freeze** |
| Backend contracts (`workflow_summary`, `continue_action`, rationale spine, intervention contracts) | Strong | Reuse as-is |
| Provider pipeline (failover, circuit breaker, mock fallback, prompt experiments, streaming) | Strong | Reuse as-is |
| Audit/observability (audit events, outcome trackers, run summaries) | Strong | **Leverage** — this is pilot instrumentation |
| Curriculum content | Empty/toy | **Blocking gap** |
| Math rendering | Absent (text-only) | **Blocking gap** |
| Answer correctness guarantees | Weak ("simple math errors" heuristic) | **Blocking gap** |
| Learner cold start / placement | Absent | **Blocking gap** |
| Guardian/parent account model | Absent (teacher role exists) | Gap — mostly remapping |
| Learner session UX (end-to-end loop) | Unknown/unpolished | Gap — audit required |
| Deployment (hosted instance) | Local dev only | Gap — single-instance only |
| Pilot metrics/analysis tooling | Raw audit events only | Gap — dashboard layer |

**Explicitly deferred (post-POC):** license decision, multi-tenancy, Postgres migration, i18n, WCAG conformance, non-math modalities, mobile apps, formal COPPA/FERPA/PIPEDA program, open-source community infrastructure.

---

## 1. Engineering ground rules for the POC push

1. **Adaptive-stack feature freeze.** No new calibration layers, profiles, or feedback loops in `src/dibble` services until the pilot produces evidence. Bug fixes only. Enforce via `SPEC.md`-style allowlist in `CLAUDE.md` / `AGENTS.md`: any change touching routing, calibration, progression, or mastery services requires explicit human approval.
2. **Every new feature ships with tests.** Backend: pytest against the FastAPI app. Frontend: existing `npm test` harness. No exceptions — pilot stability depends on it.
3. **Contracts stay backend-owned.** All new surfaces (placement, family view, dashboards) follow the existing pattern: backend computes, frontend renders. No pedagogy or scoring logic client-side.
4. **SQLite stays.** Single hosted instance for ≤10 families is well within SQLite's envelope. Add WAL mode + nightly backup; do not migrate.
5. **Definition of done for the POC build:** a parent can be invited, consent, create learner accounts, have each learner placed, run daily 20-minute sessions for 6+ weeks without developer intervention, and you can answer "did mastery improve, and did the adaptive stack beat a naive baseline?" from dashboards alone.

---

## Phase 0 — Freeze, instrument, baseline (Week 1)

Goal: lock the decision layer and make the pilot capable of answering the validation question before anything else is built.

### 0.1 Shadow baseline policy (counterfactual logging)

**The single most important piece of new code in this roadmap.** Without it, the pilot proves only that the system *ran*, not that the calibration machinery *helps*.

- **What:** A `BaselinePolicyService` implementing naive decisions at every point where the production stack makes a judgment call:
  - Mastery gate: fixed threshold (e.g., 0.8), no trend/quality/signal adjustments.
  - Progression: simple prerequisite-met check, no holds beyond threshold.
  - Routing: static mapping (wrong → reteach; wrong twice → step back; right at low support → advance). No Thompson sampling, no calibration profiles.
  - Content mode: fixed sequence (explanation → worked example → practice → assess).
- **How:** Wrap the existing router/progression call sites. At each decision, invoke the baseline policy with the same inputs and emit a `learning.baseline.decision` audit event recording `{decision_point, production_decision, baseline_decision, agreed: bool, inputs_digest}`. Zero behavioral impact — log-only.
- **Where:** New service in `src/dibble`, wired in `bootstrap.py`; hook points are the calibration-wrapped router and `ProgressionOwnershipService`.
- **Acceptance:** For any learner session, you can query agreement rate and enumerate every divergence with full context. Post-pilot analysis joins divergences against subsequent mastery outcomes (the existing `progression.outcome` tracker already produces verdicts — reuse it to score baseline decisions retroactively).
- **Estimate:** 3–5 days. Do this first; everything after generates data through it.

### 0.2 Pilot metrics read model

- **What:** A `GET /api/admin/pilot-metrics` endpoint (admin role) aggregating, per learner and cohort:
  - Sessions started/completed, return rate (day-over-day, week-over-week)
  - Mastery deltas per KC/LO (the `mastery-history` endpoint already exists — aggregate it)
  - Content defect reports (see 1.3 / 2.3)
  - Intervention/override counts from the intervention contract
  - Production-vs-baseline agreement rate from 0.1
  - Generation cost + latency per learner-hour (provider telemetry already records latency; add token counts to `generation_metadata` if absent)
- **Frontend:** One admin dashboard page. Charts can be minimal; tables are fine. This is for you, not parents.
- **Acceptance:** Weekly pilot review requires zero ad-hoc SQL.
- **Estimate:** 3–4 days.

### 0.3 Freeze enforcement

- Add the adaptive-stack allowlist rule to `CLAUDE.md`/`AGENTS.md`. Tag the freeze commit. 1 hour.

---

## Phase 1 — Content & correctness (Weeks 1–4, critical path)

Goal: a real curriculum corpus, rendered math, and a near-zero content defect rate. **Pilot recruitment cannot start until this phase is demonstrably solid** — nothing recovers from a parent seeing a wrong answer key in week one.

### 1.1 Curriculum corpus: Grades 4–6 mathematics

- **Source:** One openly-licensed corpus, ingested completely. Candidates: CK-12 FlexBooks (CC BY-NC — verify license fit for the pilot), OpenUp/Illustrative Mathematics OER (CC BY 4.0 — cleanest), or Alberta Program of Studies alignment built over an OER body if the local angle matters. Pick one; do not blend in v1.
- **Scope per grade band:** every Learning Objective, decomposed into Knowledge Components with:
  - Prerequisite edges (the KC graph service consumes these)
  - `concept_family`, `taxonomy_cluster_id`, `nearby_kc_ids` (fields already exist — populate them; bridge detection is inert without them)
  - Curriculum body text with clean excerpts (the grounding pipeline pulls deterministic excerpts — garbage in, garbage grounded)
  - **Misconception catalogs per KC.** This is the highest-pedagogy-value authoring work. The misconception detector, distractor generation, and remediation blueprints all key off catalogued patterns. For Grades 4–6 math the literature is rich (place value, fraction magnitude, equality-as-operator, multiplication-makes-bigger, etc.). Target: every major KC carries 2–5 catalogued misconceptions with alias terms and repair-target mappings.
- **Tooling:** An ingestion pipeline under `scripts/` — source documents → structured KC/LO/resource records → validation pass (orphan KCs, cycle detection in prerequisite graph, KCs with no resources, resources with no excerpts) → load into SQLite. Make it idempotent and re-runnable; corpus authoring will iterate throughout the pilot.
- **Authoring workflow:** Use Claude to draft KC decompositions and misconception catalogs from the source material; **human-review every prerequisite edge and misconception entry**. The graph is the spine of every routing decision — errors here masquerade as adaptive-stack bugs.
- **Acceptance:** Graph validation passes; spot-check 20 random KCs for prerequisite sanity; retriever returns the correct resource for 25 hand-written free-text queries spanning the band.
- **Estimate:** 2–3 weeks calendar (parallelizable with 1.2/1.3), with ongoing refinement during the pilot.

### 1.2 Math notation rendering

- **What:** LaTeX in, KaTeX out. Three touch points:
  1. **Prompt templates:** instruct all math-bearing generation families (explanation, worked example, practice, Socratic probes) to emit inline `$...$` / display `$$...$$` LaTeX. Prompt templates are versioned — ship as a new variant so the experiment machinery can compare adoption cleanly, then promote.
  2. **Artifact contract:** the discriminated `response.artifacts` union was built as the multimodal seam. Either extend the `text` artifact with a `format: "markdown+latex"` marker or add a sibling artifact type. Keep `blocks` untouched for back-compat.
  3. **Frontend:** KaTeX (auto-render extension) over generated content in learner, Socratic, remediation, and teacher drill-in surfaces. KaTeX over MathJax: smaller, faster, sufficient for the band's notation.
- **Validator hook:** add a LaTeX well-formedness check to the default validator chain (unbalanced delimiters, undefined commands) so malformed markup is caught server-side, not as a render error in front of a 10-year-old.
- **Acceptance:** Generate 50 fraction/decimal/geometry items; 100% render without raw LaTeX leakage or KaTeX errors on every surface including SSE streaming (verify delta-rendering doesn't split delimiters — buffer to block boundaries if it does).
- **Estimate:** 4–6 days.

### 1.3 Symbolic answer verification (trust-critical)

- **What:** A `MathVerificationValidator` in the pluggable validator chain that programmatically verifies every generated practice/assessment item before delivery.
- **Mechanism:**
  1. Extend the practice-generation contract: alongside the rendered problem, the provider must emit a structured `verification` block — machine-checkable answer expression, distractor expressions, and where feasible a solution-path expression. The practice pipeline already carries named distractor slots and answer-check focus; this extends that structure, it doesn't replace it.
  2. Verify with `sympy`: parse and evaluate the answer expression against the problem parameters; confirm each distractor is *not* equal to the answer (a distractor that accidentally equals the key is as damaging as a wrong key); sanity-check numeric ranges for the grade band.
  3. **On failure: regenerate, never repair.** Bounded retry (2 attempts) → fall back to the deterministic fallback content path that already exists → emit a `generation.verification.failed` audit event either way.
- **Coverage honesty:** symbolic verification covers arithmetic, fractions, decimals, basic algebra, ratio, area/perimeter — i.e., most of the band. Word problems with interpretive answers can't be fully verified; for those, verify the embedded computation and flag the item `verification: partial` in `generation_metadata` so defect analysis can segment.
- **Metrics:** verification pass rate becomes a first-class dashboard number (0.2). Target before pilot launch: ≥99% of delivered numeric items verified-correct; every unverified delivery is enumerable.
- **Estimate:** 1–1.5 weeks. Highest trust-per-effort item in the roadmap.

### 1.4 Moderation posture check (small, bounded)

- The keyword/category moderation layer is acceptable for a supervised invited pilot, but add one cheap layer: route generated learner-facing drafts through an LLM-based safety check using the existing secondary-provider plumbing when configured, falling back to the local category matcher. Log both verdicts. 2–3 days; do not gold-plate this pre-pilot.

---

## Phase 2 — Learner lifecycle (Weeks 3–6, overlaps Phase 1)

Goal: a new family can go from invite to productive daily sessions with zero developer involvement.

### 2.1 Cold-start diagnostic placement

The adaptive stack is blind for a new learner; without placement, the first two weeks of a six-week pilot are wasted calibrating from zero.

- **What:** A `PlacementService` plus endpoints:
  - `POST /api/learners/{student_id}/placement` — start a placement session for a grade band
  - `POST /api/learners/{student_id}/placement/{session_id}/respond` — submit an answer, receive next item
  - Placement state persisted like Socratic/remediation sessions (same session-backed pattern)
- **Mechanism:** Adaptive binary-search over the KC prerequisite graph, not a fixed quiz:
  1. Start at grade-level anchor KCs (flag 6–10 per band during corpus authoring, 1.1).
  2. Correct at low support → probe dependents; incorrect → probe prerequisites.
  3. Use **verified items only** (1.3), drawn from the generation cache or pre-warmed via the existing `POST /api/content/warm` path so placement is fast.
  4. Terminate at a question budget (12–18 items, ~15 minutes) or graph-frontier convergence.
  5. Seed the mastery profile: direct evidence on probed KCs, graph-propagated estimates elsewhere (the KC graph service's LO-to-KC backfill and weighted mastery recomputation already exist — reuse, don't reinvent). Stamp seeded values with low confidence so live observations dominate quickly.
- **Output:** a placement summary on the learner profile and a parent-readable placement report ("strong on X, gaps at Y, starting at Z") rendered from a backend-owned contract, consistent with the rationale-spine pattern.
- **Acceptance:** 5 synthetic learner personas (advanced, at-level, one-gap, multi-gap, below-band) placed via simulated responses land at hand-verified correct graph frontiers.
- **Estimate:** 1.5–2 weeks.

### 2.2 Guardian accounts (teacher remapped, not tenancy)

- **What:** Map the existing auth model to the homeschool shape:
  - `guardian` as a role alias of `teacher`; entity bindings already carry `teacher_id`, `display_name`, `classroom_ids` — a "classroom" becomes a family unit binding 1–3 learners.
  - **Invite flow:** admin-created invite codes → guardian signup (`POST /api/auth/register-guardian` consuming a code) → guardian creates learner profiles (name/grade only — minimize PII by design) → each learner gets a simple login (PIN or magic link; pilot-grade, not production IAM).
  - Bearer token mint/refresh/revoke already exists; build signup and learner-creation around it.
- **Frontend:** relabel and prune the teacher surfaces into a **Family view**: triage buckets (`needs action` / `needs attention` / `on track`) work unchanged at family scale; classroom mastery trends become family trends; the intervention contract (approve / pick alternative / defer / escalate) is the parent's control surface — escalate routes to you during the pilot.
- **Copy pass:** parent-facing language audit. "Hold on repair target" is backend vocabulary; the backend-owned `display_label` fields exist precisely so the frontend can present "We're spending more time on the basics of X before moving on." Extend labels where parent-legibility gaps remain rather than adding frontend copy tables.
- **Acceptance:** Full path — invite → guardian signup → two learners created → both place (2.1) → guardian sees both in Family view and can act on an intervention — executed by a non-developer tester without instructions beyond a one-page guide.
- **Estimate:** 1.5–2 weeks.

### 2.3 Learner session loop audit & polish

- **What:** A structured UX audit of the end-to-end learner loop, then fix what it finds. Walk it as a 10-year-old: login → "what's next" → do the work → see progress → clean stop.
- **Known plumbing to verify under load:** `continue_action` resume across refresh/restart; `workflow_summary` consistency between SSE and non-stream paths; remediation/Socratic handoffs back to ordinary lessons; the `X-Dibble-Error-Code` contract actually producing child-safe error states (no raw 4xx/5xx text on learner surfaces).
- **Add (small, high-value):**
  - **Session bookends:** explicit session start/end with a per-session goal ("today: 3 practice sets on equivalent fractions") and an end-of-session recap rendered from `workflow_summary` — daily-use rhythm for unsupervised homeschool use.
  - **Progress visibility:** a learner-legible progress strip (mastered / working-on / up-next) derived from the existing `curriculum_progression` read model.
  - **In-context defect report:** a "something's wrong with this question" button on every content surface, writing a `content.defect.report` audit event with `generation_id`. Feeds the defect-rate metric (0.2) and is your fastest verification-gap detector during the pilot.
  - **Affective support surfacing:** the backend-owned `affective_support` message exists on workspace payloads — confirm it renders and reads naturally; tune copy.
- **Acceptance:** 3 scripted personas complete 5 consecutive simulated daily sessions each with zero dead ends, zero developer-language leakage, zero unrecoverable states.
- **Estimate:** 1–1.5 weeks after 2.1/2.2 land.

---

## Phase 3 — Pilot operations (Weeks 5–7)

Goal: boringly reliable single-instance hosting plus the paperwork to run an invited pilot responsibly.

### 3.1 Hosted deployment (single instance, no heroics)

- Dockerfile (multi-stage: frontend build → static assets served behind the FastAPI app or a thin Caddy/nginx front) + `docker-compose.yml` with volume-mounted SQLite.
- SQLite in WAL mode; nightly `sqlite3 .backup` snapshot shipped off-host (litestream if you want continuous, but nightly + WAL is sufficient at pilot scale).
- TLS via Caddy/Let's Encrypt on a small VPS or your existing infra. `DIBBLE_AUTH_ENABLED=true`, real `DIBBLE_AUTH_TOKEN_SECRET`, mock-fallback **disabled** in production config (`DIBBLE_LLM_ALLOW_MOCK_FALLBACK=false`) — a silent mock fallback mid-pilot would corrupt your data while looking like uptime.
- Uptime monitoring on `GET /health`; provider-health telemetry already exists — alert on circuit-open events.
- A `staging` instance with mock provider for testing changes before they touch pilot families.
- **Estimate:** 3–5 days.

### 3.2 Pilot governance (lightweight, real)

- **Consent document** (plain language): what's collected (interaction data, mastery estimates, generated-content history), what's sent to the LLM provider, retention, withdrawal. As an Alberta-based invited pilot, PIPEDA-grade informed consent is the bar — get it reviewed, don't improvise.
- **Data rights tooling:** `GET /api/admin/learners/{id}/export` (full JSON dump of profile, history, audits) and a hard-delete script. An hour of API work that makes the consent document honest.
- **Provider hygiene:** confirm the configured LLM endpoint's data-retention/training terms are compatible with the consent language; prefer a zero-retention API configuration.
- **Estimate:** 2–3 days plus external review of the consent doc.

### 3.3 Pilot runbook

- Family onboarding script (the one-page guide from 2.2 acceptance), weekly check-in template, escalation path (intervention `escalate` → you, with SLA), defect triage flow (`content.defect.report` → verification-gap fix → corpus or prompt patch), and a weekly metrics review ritual against the dashboard (0.2).
- **Estimate:** 1–2 days.

---

## Phase 4 — Pilot execution & analysis (Weeks 7–15)

### 4.1 Design

- **Cohort:** 5–10 families, 8–15 learners, Grades 4–6, recruited from known networks. Over-recruit by ~30%; attrition is certain.
- **Duration:** 6–8 weeks of intended ≥4 sessions/week, ~20 min/session.
- **Pre/post assessment:** a fixed, human-authored assessment over the band's anchor KCs administered before placement and after week 6 — **not system-generated**, so the measuring stick is independent of the thing being measured.

### 4.2 Success criteria (define before recruiting; write them down)

| # | Metric | Source | Target |
|---|---|---|---|
| 1 | Pre/post mastery gain on anchor KCs | Fixed external assessment | Positive, learner-level effect visible; honest n-is-tiny framing |
| 2 | Content defect rate | Defect reports + verification telemetry | <1% of delivered items; zero wrong answer keys |
| 3 | Engagement | Session telemetry | ≥60% of intended sessions completed in weeks 3–6 (the Khanmigo ~15% regular-usage figure is the cautionary benchmark) |
| 4 | Adaptive-stack value | Baseline divergence analysis (0.1) joined to `progression.outcome` verdicts | Production decisions outperform baseline at divergence points — or you learn which layers to delete |
| 5 | Parent trust | Override/escalate rates + exit interviews | Overrides decline over time; parents would continue post-pilot |
| 6 | Unit economics | Cost/latency telemetry | Known $/learner-hour with a defensible path under target price |

### 4.3 Operating cadence

Weekly: dashboard review, defect triage, family check-ins. Mid-pilot (week 3–4): one corpus/prompt patch window — batched, staged, then promoted; no continuous deployment onto live families. Post-pilot: exit interviews, full divergence analysis, written findings.

### 4.4 The decision the pilot exists to inform

Post-pilot, answer three questions in writing:
1. **Did learning happen?** (Criterion 1, honestly framed for sample size.)
2. **Did the machinery matter?** (Criterion 4 — which calibration layers earned their complexity; delete the rest.)
3. **Would families pay/stay?** (Criteria 3 & 5.)

Those answers — not feature ambition — determine whether the next phase is scale-out (license decision, Postgres, multi-tenancy, second subject) or consolidation.

---

## Timeline summary

| Week | Workstream |
|---|---|
| 1 | Phase 0 complete (freeze, shadow baseline, metrics endpoint); corpus ingestion begins |
| 2–3 | Corpus authoring + ingestion tooling; KaTeX rendering; sympy verification |
| 3–4 | Verification hardening to ≥99%; placement service; guardian accounts begin |
| 5 | Session-loop audit & polish; family-view copy pass |
| 5–6 | Hosting, governance, runbook; staging rehearsal with synthetic personas |
| 6–7 | Recruit + onboard families; pre-assessment; placement |
| 7–15 | Pilot (6–8 weeks), weekly cadence, one mid-pilot patch window |
| 15–16 | Post-assessment, exit interviews, divergence analysis, written findings |

**Critical path:** 1.1 → 1.3 → (2.1, 2.2) → 3.1 → recruit. Rendering (1.2), Phase 0, and 2.3 parallelize. Recruitment gates on Phase 1 acceptance criteria, hard.

## Explicit non-goals (resist these)

- Any new adaptive/calibration capability before pilot data exists
- Postgres, multi-tenancy, horizontal scale
- Second subject, second grade band, second language
- Open-source/community infrastructure (the license decision is post-pilot, informed by 4.4)
- Mobile apps, offline mode, voice
- Production-grade IAM, formal compliance certification

Each is real. None blocks the only question that matters right now: **does Dibble demonstrably teach, and does its complexity earn its keep?**
