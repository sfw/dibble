# Dibble

This repository now includes a working MVP backend slice for the revised adaptive learning platform.

## Repository Layout

- `src/dibble/`: FastAPI backend and adaptive-learning services
- `frontend/`: React + Vite + TypeScript frontend workspace for learner, teacher, classroom, and integration-shell product surfaces
- `planning/`: revised spec, backend gap analysis, and frontend/back-to-front planning notes

## What Exists

- FastAPI application in `src/dibble/`
- React + Vite frontend in `frontend/` with learner overview, generation, Socratic, remediation, teacher intervention, classroom triage, and contract-smoke surfaces
- SQLite-backed persistence for learner profiles and curriculum resources
- Learner profile model aligned to the revised spec's richer profile design
- Observation-driven affective, cognitive-load, and metacognitive state inference folded into the learner profile and adaptive routing decisions
- Adaptive routing service with curriculum/safety guardrails plus Thompson-style action selection for step-back, reteach, targeted practice, and stretch decisions
- Retrieval-grounded generation pipeline split into retriever, router, provider, and validator services
- Default retriever now uses a persistent SQLite-backed embedding index plus lexical/metadata scoring for better free-text curriculum matching
- Default provider now supports an OpenAI-compatible chat completion endpoint with configurable ordered, round-robin, or latency-aware provider selection, secondary-provider failover, circuit-breaker protection, persistent provider-health warm starts, and automatic mock fallback when no model credentials are configured
- Prompt template selection is now versioned and variant-aware, with deterministic experiment bucketing for generation and Socratic assessment probes, and prompt metadata persisted on generated responses
- Socratic assessment probes can now optionally use recent audit outcomes to adaptively prefer the stronger-performing prompt variant instead of only fixed bucketing
- Experimented generation families such as explanations, worked examples, and practice problems can now also use recent content-generation outcomes to adaptively prefer the stronger prompt variant
- The generation-side adaptive selector now weights nearby `learner.observe` outcomes when available, so prompt variants can be nudged by downstream learner response signals instead of only immediate generation quality
- Observations can now optionally carry `generation_id`, content type, and target KC/LO context so downstream calibration can prefer exact or context-compatible matches over loose time proximity
- Generation requests and observations can now also carry `learning_session_id` so prompt calibration can prefer same-session matches without fragmenting the generation cache
- Socratic assessment now uses modular continuous evidence scoring plus an outcome-aware turn policy instead of a last-turn threshold check
- Socratic assessment outcomes now fold back into learner mastery and metacognitive signals so later routing can react to conversational evidence
- Generation prompt calibration can now also learn from same-session Socratic assessment evidence, not just follow-up observation events
- Generation prompt calibration now aggregates the strongest linked observation and Socratic follow-ups into small session traces instead of relying on only one downstream event
- Generation prompt calibration can now also look across later generated steps in the same learning session and fold those downstream outcomes back into the earlier prompt variant
- Generation prompt calibration now turns those linked traces into explicit run-level summaries with outcome scores, confidence, and positive/mixed/negative calibration signals so selector decisions rely less on raw event-window counts alone
- The production router is now wrapped with a calibration layer that reads recent same-target run summaries, exposes a route-level calibration summary, and conservatively raises or relaxes support when durable evidence is clearly negative or positive
- The learner observation pipeline now reuses those run summaries to conservatively nudge metacognitive state updates, so stored confidence calibration, help-seeking, and self-monitoring rely a little less on single-observation heuristics alone
- Those run summaries are now also persisted as `learning.run.summary` audit events when new observation or Socratic evidence arrives, and downstream calibration services, prompt selection, and prompt telemetry prefer those durable summaries before falling back to raw event-window reconstruction
- The backend now also compacts recent matching run summaries into cross-session `learning.calibration.profile` audit events, and the router prefers those profile snapshots before falling back to per-run summaries or raw trace reconstruction
- The backend now also compacts recent matching run summaries into cross-session `learning.progress.profile` audit events so recent-vs-prior run outcome trends become durable learner-history artifacts instead of only request-time calculations
- Router calibration and generation-mode calibration now prefer those persisted progress profiles when available, so live support decisions can react to cross-session `improving` or `declining` trends instead of only current run snapshots
- The backend now also compacts recent matching run summaries into cross-session `learning.strategy.profile` audit events, producing honest heuristic recovery, plateau, relapse, and volatility signals that routing, generation-mode calibration, remediation workflows, learner summaries, and predictive follow-up warming can reuse directly
- The misconception pipeline now also compacts repeated remediation signals into richer `learning.misconception.profile` events with recurrence counts, session counts, and recurrence labels such as `recurring` or `relapsing`, and those durable signals now feed later misconception detection, alias-aware catalog matching, graph-weighted prerequisite-gap scoring, per-KC misconception disambiguation, and remediation blueprint selection
- Misconception detection can now also reuse recent target-scoped learner observations as bounded behavioral evidence, so support-heavy struggle or low-support stability can reinforce or temper prerequisite-gap, target-confusion, and repair-target catalog signals with explicit rationale instead of relying only on text overlap and durable profiles
- Learner-strategy signals now also produce explicit per-KC sequencing decisions such as rebuilding a prerequisite first, holding on the repair target, holding on the target KC, or attempting transfer, and those decisions now shape remediation workflow steps plus predictive follow-up targeting
- Same-session observations and Socratic assessments now feed a persisted within-session controller keyed by `learning_session_id`, so active sessions can carry explicit arc phases such as `stabilize`, `repair`, `consolidate`, `bridge`, and `transfer_check` plus recovery intent, streaks, generated-step counts, support-step budgets, loop-risk signals, and a concrete `arc_action` across requests while the next generation step raises or relaxes support, avoids shallow support loops, and updates sequencing before the slower cross-session profiles catch up
- The backend now also compacts recent run summaries, progress profiles, and learner-strategy profiles into durable `learning.state.profile` events, including outcome-backed recovery-stability, overload-risk, and metacognitive-reliability signals, and the learner observation pipeline can use those signals to decide how strongly cross-session state targets should influence the next live affective, load, and metacognitive update instead of relying only on the latest observation window
- The KC graph layer now has a reusable graph service for broader prerequisite/dependent traversal, same-LO sibling and bridge detection, distance-aware weighting, LO-to-KC backfill estimates, and weighted LO mastery recomputation, so Socratic mastery migration and remediation sequencing no longer treat every prerequisite hop or sibling KC as equally strong
- Knowledge Components can now also carry light taxonomy and locality metadata such as `concept_family`, `taxonomy_cluster_id`, and curated `nearby_kc_ids`, and the KC graph uses those relations to surface practical local bridge candidates beyond same-LO siblings during remediation sequencing
- Recent Socratic assessment turns now also feed an explicit conversational steering layer, so the next generated step can react to recent `step_back`, `clarification`, or `transfer_check` outcomes by changing prompt family, guidance, and even the selected next content mode more directly, while the Socratic turn policy can now re-probe from a new angle when clarification or step-back turns start to stall
- Socratic steering is now also explicit on assessment turns and responses, with policy-level actions such as `open_probe`, `probe_from_new_angle`, `repair_then_model`, `clarify_then_check`, `restate_then_apply`, and `verify_transfer`, so downstream generation no longer has to infer all conversational intent only from prompt style
- Cross-session Socratic assessment history now also condenses into a lightweight conversational signal that can recognize durable tendencies such as needing model-then-release, clarify-then-check, vary-representation, or independent-check follow-through, and generation-mode calibration plus prompt steering can use that history when the current session is sparse
- Practice generation now hydrates lightweight target-KC misconception hints from the live KC catalog, upgrades generic distractors into misconception-aware contrast when a live target misconception is known, and carries named distractor slots plus answer-check focus so prompt guidance and fallback content can build more purposeful wrong-answer structure
- Practice generation now also names a distractor family, distractor support intensity, and distractor rationale, so misconception-aware problem construction can stay explicit when support is still needed and lighten more honestly when durable recovery signals support freer discrimination
- Micro-explanation generation now also reuses those target-KC hints, so explanation prompts can center the exact concept, correct the likely misconception, anchor the corrective move, and optionally pull in one nearby comparison instead of falling back to a generic explanation frame
- Worked-example generation now carries named visible step roles, a hidden learner-owned step role, a transfer move, a step outline, and a learner-release plan, so fading can be expressed as a role-based release sequence rather than only a visible-step count
- Worked-example generation now also names a release stage, release intensity, release transition, and release rationale, so prompts and deterministic fallback content can fade support by role and transfer move while honoring reliable learner-state and challenge-tolerance evidence instead of only counting visible steps
- Curriculum grounding now carries short deterministic excerpts from the retrieved curriculum body, and those excerpts now flow through generation prompts, Socratic assessment probes, validation, and deterministic fallback generation instead of grounding the provider mostly by titles and tags
- Predictive warming now behaves more like a lightweight scheduler, with urgency classes, bounded batch selection so routine work is not starved forever, retry/backoff for transient failures, stale-processing sweep/requeue recovery, urgency-aware retry caps, and richer queue/process telemetry
- Predictive warm execution now also records explicit claim ownership and execution intent, so inline versus background queue work surfaces which worker claimed each task, why it ran, whether it was a targeted or autonomous backlog pickup, whether it came from stale-processing recovery, and what eligible versus blocked backlog remained afterward
- Predictive warm processing can now also use spare inline budget to catch up other eligible backlog tasks instead of only the just-enqueued task ids, and the scheduler/process API now surfaces claimed, supplemental, and expired-task counts so those bounded autonomous decisions are inspectable
- The ordinary generation path now also applies a broader local mastery gate, so premature assessment-style requests can be rewritten into target practice, prerequisite rebuild, or bridge practice with explicit target stage, requested-versus-applied content-type, and redirect metadata instead of silently attempting transfer too early
- Ordinary progression evidence now follows the backend-applied stage target rather than only the originally requested KC, so repair and bridge work can actually earn or fail the backend’s hold/return decision on the concept the learner just practiced, and the within-session controller now blocks transfer promotion when live evidence still looks overloaded, disengaged, or support-dependent even if later assessment evidence is positive
- Same-session progression holds and transfer resumes now also append compact evidence snapshots to their rationale, so backend-owned lesson and teacher surfaces can show observation, assessment, confidence, and mastery context without introducing parallel explainability fields
- Remediation sessions now also enforce stronger repair-versus-bridge return gates and carry progression evidence metadata such as observation counts, confidence, average observed mastery, and low-support success counts directly on the session/read-model contract
- Held remediation follow-ups now also keep `workflow_summary`, workspace resume, and generation history aligned to the actual held stage target and latest held generation, so repair or bridge holds no longer drift back toward stale return-stage semantics on adjacent frontend surfaces
- Ordinary lesson progression now also reuses durable ordinary mastery profiles directly, so support-dependent or fragile cross-session practice can hold the learner on target practice and even rewrite an assessment request back into target-aligned practice when same-session evidence is sparse
- Durable ordinary mastery lookup is now target-scoped instead of falling back to unrelated KC history, and strong support-dependent or fragile ordinary evidence on a backend-applied repair target can now sharpen a prerequisite redirect into an explicit `hold_repair_target` state with inspectable rationale
- Ordinary-mastery-driven progression holds now also append compact confidence and observed-mastery snapshots to their rationale, so `workflow_summary`, learner-flow, workspace, history, and teacher-intervention surfaces can reuse one more inspectable explanation without new frontend logic
- Workflow-facing lesson and remediation surfaces now also prefer one canonical next-step rationale path, so `workflow_summary`, learner flow, workspace resume, history, intervention, and classroom drill-in can present the same backend-owned decision rather than neighboring surfaces drifting toward different rationale fragments
- Same-session and ordinary-work progression rationales now more explicitly explain why the backend is holding repair, bridge, target, or transfer instead of the adjacent stage, and ordinary-work rationale snapshots now also surface low-support success versus high-support dependency rates directly in the existing rationale text
- Within-session bridge phases now also surface an explicit `hold_bridge_target` posture instead of leaking repair-hold vocabulary, and predictive follow-up planning plus predictive warming now treat that bridge hold like a first-class guided re-entry decision instead of falling back to generic repair semantics
- Ordinary lesson progression now also preserves that active `hold_bridge_target` posture in front of same-session transfer evidence while the within-session controller is still in guided re-entry, so delivered `workflow_summary`, `continue_action`, and predictive follow-up behavior stay aligned with the backend's bridge-stage judgment
- Active remediation summaries and delivered remediation workflow payloads now also carry remediation-path rationale plus current-step framing instead of falling back to bare execution guidance, so frontend surfaces can explain why the learner is in that remediation step now instead of only what the step asks them to do
- Socratic summaries now also reuse the same decision-grade next-step rationale spine as learner flow, workspace, history, and intervention surfaces, so a Socratic repair, assessment, or transfer decision reads like the same backend judgment everywhere it appears
- Delivered lesson and remediation `workflow_summary` payloads now also treat their canonical next-step rationale as the source of truth instead of layering extra fallback prose on top, so generated-content summaries stay byte-aligned with session summaries and other read models
- Curriculum progression now also behaves more like a dependency-aware frontier planner instead of a thin unlocked-resource list, so deferred return targets can stay visible while prerequisite repair or bridge work is in flight and unrelated ready resources do not outrank the backend's current repair path just because they sort earlier
- Blocked curriculum resources now also name prerequisite mastery snapshots plus the blocking resource titles in their rationale, so learner summary and classroom drill-in can explain exactly why a resource is still blocked without inventing extra frontend heuristics
- Lesson `current_flow` now preserves deferred and transfer target KC ids even when a persisted `workflow_summary` is present, so learner flow, curriculum progression, summary, and classroom cards can all reason from the same backend-owned return target during repair or bridge holds
- Generated lesson content now also persists its `workflow_summary`, and learner-flow responses now prefer that stored lesson contract with explicit provenance fields so backend-owned next-step answers survive reloads and restarts without re-deriving lesson state from audits alone
- Lesson, remediation, Socratic, learner-flow, and learner-workspace payloads now also expose a small shared `continue_action` contract, so the frontend can ask the backend what request to make next instead of inferring resume/advance behavior from raw status fields alone
- Frontend-facing error paths now also expose a consistent `X-Dibble-Error-Code` header, so the UI can distinguish auth, not-found, stale-session, and completed-workflow failures without parsing human-facing error messages
- The generation engine now runs an explicit moderation pass before and after provider generation, covers a broader normalized local category set such as abusive tone, academic-integrity prompts, privacy risk, sexual content, violence, self-harm, stereotype/bias, and substance-use wording, and can replace unsafe learner prompts or generated drafts with a teacher-safe fallback while surfacing explicit moderation metadata and matched terms instead of treating them as ordinary validation issues
- The moderation layer now also groups matched terms into category-level moderation matches, marks whether the request was blocked or the response was rewritten, records fallback kind, stream action, provider-invocation, buffered-stream, and original-versus-replacement block-count metadata, emits dedicated moderation audit events, and exposes moderation category rollups plus fallback-path telemetry so safety handling is easier to inspect end to end
- Live learner-state and cognitive-trait inference now score the strength of current evidence more explicitly, so strong current low-support observations can push back on overly optimistic durable profiles while sparse evidence can still benefit from stable cross-session state/trait backfill
- Durable learner-state profiles now also carry per-dimension reliability signals for affective versus load versus metacognitive targets, and both live state inference and observation-time state calibration now blend those dimensions selectively instead of moving the whole durable profile as one block
- The backend now also compacts recent learner observations plus durable state-profile context into `learning.cognitive_trait.profile` events, including trait-stability, challenge-tolerance, per-trait reliability, and challenge-evidence-strength signals, and live cognitive-trait inference can use those signals to trust strong durable working-memory or processing-speed evidence without over-trusting weaker durable trait dimensions
- `GET /api/learners/{student_id}/summary` now exposes a frontend-ready learner overview with engagement, metacognitive snapshot, latest calibration summary, latest progress trend summary, latest learner-strategy summary, recent activity counts, and a backend-owned `current_flow` summary so the UI does not need to read audit logs directly
- `GET /api/learners/{student_id}/flow` exposes the same learner-flow contract directly, including current phase, progression action, active targets, and next-step metadata for ordinary generation, remediation, and Socratic workflows
- `GET /api/learners/{student_id}/progression` now exposes a backend-owned curriculum progression read model with current resource focus, next ready resource, prerequisite blockers, and compact resource-state counts, and learner summary now embeds that same `curriculum_progression` contract so the frontend can render broader progression without inventing course logic
- Curriculum progression and teacher classroom learner cards now also reuse the canonical learner-flow rationale whenever they are describing the same active curriculum focus, so overview, classroom drill-in, and workspace/flow surfaces do not hedge differently about the same backend-owned stage decision
- `GET /api/learners/{student_id}/workspace` now also includes a top-level backend-owned `continue_action`, so reload and continue buttons can reuse one server contract across lesson, remediation, and Socratic states
- Learner workspace payloads now also include an optional backend-owned `affective_support` message, so learner encouragement, nudges, and break suggestions no longer depend on frontend interpretation of raw frustration and engagement signals
- Learner-scoped history endpoints now expose compact backend-owned lists for prior generated content, Socratic sessions, and remediation sessions, so the frontend can build history views without replaying audit events or guessing which payloads matter
- `GET` and `POST /api/learners/{student_id}/intervention-action` now expose a teacher-safe intervention contract derived from `current_flow`, including backend-generated alternative options plus `select_option`, so a teacher can approve the current move, choose a safer backend-owned alternative, defer, or escalate without the frontend inventing its own workflow authority
- Teacher intervention option labels now also reflect the backend-owned stage (`repair`, `bridge`, `target`, `transfer`) for lesson follow-ups, so teacher surfaces can tell at a glance whether an option is repair practice, bridge explanation, or a transfer check instead of reading every rationale line first
- Teacher intervention alternative rationales now also name the relevant stage target directly, so repair and bridge options no longer read like generic “same target” follow-ups when the backend is actually holding a different stage
- `GET /api/teachers/classrooms` and `GET /api/teachers/classrooms/{classroom_id}` now expose a compact teacher classroom read model with learner cards, current flow, curriculum progression, intervention availability, attention flags, and classroom-level counts, so the frontend can build classroom views without aggregating learner detail client-side
- Teacher classroom learner cards now also include a backend-owned `triage_section`, so classroom grouping into teacher action, needs attention, and on-track buckets no longer depends on frontend interpretation of intervention availability plus attention level
- The backend now treats `summary.curriculum_progression` and `GET /api/learners/{student_id}/progression` as one regression-protected contract, and teacher classroom learner cards reuse that same compact progression shape instead of introducing a classroom-specific variant
- The backend now also treats `continue_action` and teacher intervention vocabulary as explicit backend-owned contract sets: `continue_action.kind` is finite across lesson, remediation, and Socratic flows, `continue_action.method` is normalized, and intervention `proposal_status`, `allowed_decisions`, `latest_decision.status`, and classroom intervention summaries now serialize from stable backend vocabularies instead of loosely coordinated strings
- Backend-owned display labels now also ride alongside key machine-readable contract fields such as `continue_action.kind`, `curriculum_progression.current_stage`, and remediation workflow `phase`, so the frontend can retire more of its local pedagogy-copy tables without losing backward-compatible keys
- Frontend-facing error responses now also keep the same machine-readable code in both `X-Dibble-Error-Code` and the JSON body `code` field while preserving the existing human-readable `detail`, so the UI can branch on one stable error vocabulary without scraping headers or message text alone
- Predictive warming now also has a durable SQLite-backed queue plus an explicit processor path, so anticipated follow-up requests can be scheduled, canceled when new evidence arrives, prioritized by likely next-step urgency, expired when they go stale, and processed outside the original generation request when needed
- The predictive follow-up planner is now calibration-aware, so declining practice can warm a worked example instead of a transfer check, stronger remediation progress can warm a transfer probe sooner, long-horizon learner-strategy signals can now escalate relapse toward prerequisite repair or break a plateau with varied modeled support, and newer within-session controller phases can now keep a session in consolidate or bridge before warming transfer
- Knowledge Components can now carry catalogued misconception patterns, and the remedial trigger uses those patterns to produce richer misconception signals plus a structured remediation blueprint instead of only a generic step-back wrapper
- Remediation planning rationale now also names the primary misconception path, evidence terms, recurrence posture, and selected repair target directly in the existing remediation rationale field, so product surfaces can explain why that remediation path was chosen without a new contract
- Remediation planning rationale now also carries the winning misconception disambiguation plus KC-sequencing context when available, so existing remediation and intervention surfaces can explain why this path beat adjacent misconception or prerequisite-only alternatives without a schema change
- Remediation planning rationale now also explicitly names the strongest alternative path it beat when that comparison matters, so prerequisite-gap step-backs do not read like arbitrary defaults when the backend has a more specific misconception diagnosis
- Teacher intervention alternative options now also inherit the current backend posture in their rationale, so option lists read like explicit deviations from the same backend judgment instead of unrelated generic suggestions
- Remediation is now session-backed, so `POST /api/remedial/trigger` starts a persisted multi-step workflow and later steps can be reloaded or advanced through dedicated remediation-session endpoints, those sessions now carry learner-strategy context so repeated struggle can keep prerequisite rebuild guidance explicit across steps, and recurring misconception profiles can now pull remediation back toward repeated repair targets instead of treating each attempt as isolated
- Remediation and Socratic session payloads now also carry compact summary contracts with canonical status, current phase, latest decision, and next-step metadata so the frontend can render workflow state without interpreting raw step arrays or turn history on its own
- Completed remediation follow-ups now also reuse the same backend-owned `continue_action` payload across the session summary, delivered `workflow_summary`, and workspace resume path, so lesson handoff keeps the same `learning_session_id`, source generation, and target KC semantics everywhere
- The learner observation pipeline now also refreshes cognitive trait estimates such as processing speed, working memory, and spatial reasoning from recent observation patterns, so trait fields are no longer purely static seed data
- Strong target-scoped practice or remediation observations can now still write mastery back even without an explicit generation or session link when the evidence is specific enough, and the ordinary generation path can now redirect a request toward a prerequisite or bridge KC when strategy or same-session sequencing evidence says the caller’s requested target is premature while also letting stronger same-session transfer evidence override a slower prerequisite hold when that newer evidence is clearly better
- Default validation now checks for missing grounding, missing instructional content, weak curriculum alignment, instruction-level grounding coverage, grade-band readability risk, accessibility density, unsafe language, and simple math errors
- Adaptive decision and generation endpoints now write audit events and expose simple local observability metrics
- Observability metrics now include durable provider-health telemetry for upstream failures and circuit-open state
- Streaming generation is available over server-sent events for incremental `start`, `delta`, and `complete` delivery, and can consume real upstream OpenAI-compatible chat streams when configured
- Generated content is now persisted with quality/provenance metadata and reused through a lightweight SQLite-backed generation cache
- Generated content responses now also include a compact `workflow_summary` contract so clients can read delivered phase, progression action, active targets, and next-step metadata without unpacking the raw `request_context` tree
- Generated content responses now also expose a discriminated `response.artifacts` contract alongside the legacy `blocks` list, with a stable `text` artifact shape that keeps current consumers working while giving future multimodal artifacts an explicit extension seam
- Stream `complete` events now carry that same compact `workflow_summary` contract and run through the same progression-ownership and session-finalization path as non-stream generation, so frontend state does not diverge between SSE and normal response modes
- Generated content can now be reloaded by `generation_id`, and learner workspace responses can now bundle learner summary/flow with the active generation or active remediation/Socratic session for resume-after-refresh frontend work
- Optional principal-based API key auth with `learner`/`viewer`/`teacher`/`editor`/`admin` roles can protect every endpoint except `GET /health`
- `learner` and `teacher` principals now carry entity bindings (`learner_id`, `teacher_id`, `display_name`, `classroom_ids`) that persist through bearer tokens, refresh, and `/api/auth/me` so the frontend can identify who a user is in product terms
- Signed bearer tokens can be minted, refreshed, and revoked for request-scoped sessions, and entity bindings survive token refresh
- RBAC failures now keep the same `403` machine-readable contract for API-key and bearer-token callers, and forbidden-request audit events preserve the authenticated principal instead of falling back to API-key-only handling
- History endpoints (`/history/generations`, `/history/socratic-sessions`, `/history/remediation-sessions`) now return paginated responses with `items`, `offset`, `limit`, and `has_more` fields, supporting offset-based pagination with limit clamped to 1–100
- Mastery writeback now applies diminishing returns when prior KC mastery is above 0.85 and the observation is upward, so high mastery stabilises near the ceiling instead of oscillating
- Ordinary mastery hold thresholds now adapt to the learner's actual independence signals: high low-support success rate relaxes the hold, very high support-dependency rate tightens it
- Ordinary mastery hold rationale now surfaces session count context and an explicit "extended hold — consider teacher review" signal when a learner has been held across many observations and sessions without improving
- Ordinary mastery profiles now detect mastery trend direction (improving, stable, declining) by comparing recent versus older recency-weighted observation scores, and the signal classification can rescue an improving borderline-fragile learner to emerging or downgrade a declining borderline-durable to emerging
- Misconception behavioral evidence now applies recency weighting so recent struggles and low-support successes contribute more than stale observations at the tail of the evidence window
- Mastery history snapshots are now recorded on every observation-driven profile update, and `GET /api/learners/{student_id}/mastery-history` returns a time-series of overall KC/LO mastery, mastered/struggling KC counts, and affective signals so the frontend can render trend lines
- `GET /api/teachers/classrooms/{classroom_id}/mastery-trends` returns per-learner mastery trajectories plus daily classroom average points, unblocking teacher report trend lines
- Ordinary mastery hold thresholds now integrate mastery trend direction: an improving trend relaxes the hold so the learner has room to keep improving, while a declining trend tightens the hold so the learner does not fall further before teacher review
- Stuck-repair detection now triggers earlier for declining learners (4 observations / 2 sessions instead of 6 / 3) with a distinct "declining hold" label
- Ordinary mastery hold threshold adjustments are now scaled by evidence depth so sparse observation windows don't earn the same threshold shift as learners with many observations
- Misconception prerequisite gap detection now adapts its mastery threshold to recent behavioral evidence: recent struggles on a prerequisite raise the threshold while recent low-support successes lower it
- KC mastery now decays over time when a learner has not practiced a KC recently (DATA-004): decay is applied at read time during curriculum progression decisions so stale mastery does not artificially inflate resource classification, with a smooth four-band schedule from no decay within 14 days to a 0.6 floor beyond 90 days
- Observation writeback now stamps per-KC `kc_last_practiced` timestamps so the mastery decay system knows when each KC was last actively practiced
- Curriculum progression is now trend-aware (ORCH-001): ordinary mastery trend signals (improving/stable/declining) from the durable mastery profile layer now adjust both the mastery and prerequisite-ready thresholds per resource, so improving learners can advance sooner while declining learners are held more conservatively at the resource-classification level, not only at the progression-ownership hold level
- Dynamic plugin loading for router, retriever, provider, and validator factories
- API tests covering routing, persistence, retrieval, generation, and fallback behavior

## Run It

Install dependencies:

```bash
env UV_CACHE_DIR=.uv-cache uv sync --group dev
```

Start the API:

```bash
env UV_CACHE_DIR=.uv-cache uv run uvicorn dibble.main:app --reload
```

Run tests:

```bash
env UV_CACHE_DIR=.uv-cache uv run pytest
```

Run the frontend locally:

```bash
cd frontend
npm ci
npm run dev
```

Run the frontend verification suite:

```bash
cd frontend
npm run test:run
npm run lint
npm run build
```

Install the local git hooks:

```bash
pre-commit install
```

The repository includes a `pre-commit` hook that scans staged diffs with `trufflehog` before each commit.

## Current Endpoints

- `GET /health`
- `GET /api/learners`
- `PUT /api/learners/{student_id}/profile`
- `GET /api/learners/{student_id}/profile`
- `POST /api/learners/{student_id}/observations`
- `GET /api/learners/{student_id}/state`
- `GET /api/learners/{student_id}/summary`
- `GET /api/learners/{student_id}/flow`
- `GET /api/learners/{student_id}/progression`
- `GET /api/learners/{student_id}/workspace`
- `GET /api/learners/{student_id}/history/generations`
- `GET /api/learners/{student_id}/history/socratic-sessions`
- `GET /api/learners/{student_id}/history/remediation-sessions`
- `GET /api/learners/{student_id}/mastery-history`
- `GET /api/learners/{student_id}/intervention-action`
- `POST /api/learners/{student_id}/intervention-action`
- `PUT /api/teachers/classrooms/{classroom_id}`
- `GET /api/teachers/classrooms`
- `GET /api/teachers/classrooms/{classroom_id}`
- `GET /api/teachers/classrooms/{classroom_id}/mastery-trends`
- `PUT /api/curriculum/resources/{resource_id}`
- `GET /api/curriculum/resources`
- `PUT /api/knowledge-components/{kc_id}`
- `GET /api/knowledge-components`
- `GET /api/knowledge-components/{kc_id}/prerequisites`
- `POST /api/router/decide`
- `POST /api/content/generate`
- `GET /api/content/{generation_id}`
- `POST /api/content/warm`
- `POST /api/content/warm/process`
- `POST /api/explanations/generate`
- `POST /api/problems/generate`
- `POST /api/worked-examples/generate`
- `POST /api/assessments/socratic`
- `GET /api/assessments/socratic/{session_id}`
- `POST /api/remedial/trigger`
- `GET /api/remedial/sessions/{session_id}`
- `POST /api/remedial/sessions/{session_id}/advance`
- `POST /api/llm/stream`
- `POST /api/assignments`
- `GET /api/assignments/{assignment_id}`
- `PATCH /api/assignments/{assignment_id}`
- `GET /api/learners/{student_id}/assignments`
- `GET /api/teachers/assignments`
- `GET /api/auth/me`
- `POST /api/auth/token`
- `POST /api/auth/token/refresh`
- `POST /api/auth/token/revoke`
- `GET /api/audit/events`
- `GET /api/observability/metrics`

## Persistence

The app uses SQLite by default and stores data in `dibble.db`.

You can override the database path with:

```bash
export DIBBLE_DATABASE_PATH=/path/to/dibble.db
```

Plugin factories can also be overridden:

```bash
export DIBBLE_ROUTER_PLUGIN=dibble.plugins.defaults.router:build
export DIBBLE_RETRIEVER_PLUGIN=dibble.plugins.defaults.retriever:build
export DIBBLE_PROVIDER_PLUGIN=dibble.plugins.defaults.provider:build
export DIBBLE_VALIDATOR_PLUGIN=dibble.plugins.defaults.validator:build
```

LLM orchestration settings for the default provider:

```bash
export DIBBLE_LLM_API_BASE=https://api.openai.com/v1
export DIBBLE_LLM_API_KEY=...
export DIBBLE_LLM_MODEL=...
export DIBBLE_LLM_TIMEOUT_SECONDS=20
export DIBBLE_LLM_SECONDARY_API_BASE=https://api.openai.com/v1
export DIBBLE_LLM_SECONDARY_API_KEY=...
export DIBBLE_LLM_SECONDARY_MODEL=...
export DIBBLE_LLM_SECONDARY_TIMEOUT_SECONDS=20
export DIBBLE_LLM_CIRCUIT_BREAKER_THRESHOLD=2
export DIBBLE_LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS=30
export DIBBLE_LLM_SELECTION_STRATEGY=ordered
export DIBBLE_LLM_ALLOW_MOCK_FALLBACK=true
export DIBBLE_PROMPT_LIBRARY_VERSION=1.0
export DIBBLE_PROMPT_EXPERIMENT_ENABLED=false
export DIBBLE_PROMPT_ADAPTIVE_SELECTION_ENABLED=false
export DIBBLE_PROMPT_VARIANT=
```

If the primary LLM provider fails, the default provider can fail over to the configured secondary provider before falling back to the deterministic mock provider for local development. Repeated failures can temporarily open a circuit for the failing provider so the system stops retrying it until the cooldown window passes. `DIBBLE_LLM_SELECTION_STRATEGY=ordered` preserves explicit primary failback, `round_robin` balances across currently healthy upstream providers, and `latency_aware` gives each healthy provider an initial sample before favoring the strongest recent success-rate and latency profile. Provider-health telemetry is persisted in SQLite and now warms those routing decisions back into memory when the app restarts. The prompt layer now selects named templates like `micro_explanation.baseline` or `worked_example.guided_reflection`, tracks their version, and can deterministically bucket supported content types into a simple experiment when `DIBBLE_PROMPT_EXPERIMENT_ENABLED=true`. If `DIBBLE_PROMPT_ADAPTIVE_SELECTION_ENABLED=true`, Socratic assessment probes and the main experimented generation families can also use recent audit outcomes to prefer the better-performing prompt variant once enough evidence exists, with generation-side calibration now summarized into explicit run outcomes plus confidence-weighted positive/mixed/negative signals before selector ranking and router-side calibration now consuming those same summaries before final support selection. When configured, the stream endpoint can consume upstream OpenAI-compatible chat SSE deltas and translate NDJSON chunk output into Dibble block-stream events. The stream endpoint emits server-sent events named `start`, `delta`, `moderation`, and `complete`.

Embedding settings for the default retriever:

```bash
export DIBBLE_EMBEDDING_API_BASE=https://api.openai.com/v1
export DIBBLE_EMBEDDING_API_KEY=...
export DIBBLE_EMBEDDING_MODEL=...
export DIBBLE_EMBEDDING_DIMENSIONS=256
export DIBBLE_EMBEDDING_TIMEOUT_SECONDS=15
export DIBBLE_EMBEDDING_ALLOW_LOCAL_FALLBACK=true
```

If `DIBBLE_EMBEDDING_API_KEY` or `DIBBLE_EMBEDDING_MODEL` is unset, the default retriever uses a deterministic local embedder and stores resource vectors in SQLite for offline development.

Authentication settings:

```bash
export DIBBLE_AUTH_ENABLED=true
export DIBBLE_AUTH_API_KEYS=secret-one,secret-two
export DIBBLE_AUTH_PRINCIPALS=viewer-key:viewer-user:viewer,editor-key:editor-user:editor,admin-key:admin-user:admin
export DIBBLE_AUTH_HEADER_NAME=X-API-Key
export DIBBLE_AUTH_TOKEN_SECRET=replace-me
export DIBBLE_AUTH_TOKEN_ISSUER=dibble
export DIBBLE_AUTH_TOKEN_TTL_SECONDS=3600
export DIBBLE_AUTH_REFRESH_TTL_SECONDS=604800
export DIBBLE_GENERATION_CACHE_TTL_SECONDS=3600
```

When auth is enabled, all API routes except `GET /health` require a valid key in the configured header. If `DIBBLE_AUTH_PRINCIPALS` is set, keys resolve to named principals and roles. Route access is split so viewers can read, editors can mutate/generate, and admins can access audit and observability endpoints. If `DIBBLE_AUTH_TOKEN_SECRET` is set, authenticated principals can exchange API-key access for signed bearer tokens via `POST /api/auth/token`, rotate them with `POST /api/auth/token/refresh`, and revoke sessions with `POST /api/auth/token/revoke`. Forbidden requests now also preserve the same authenticated principal in audit logs regardless of whether the caller authenticated with an API key or a bearer token.

Generated responses now include `generation_id` plus `generation_metadata` with validation status, quality score, provider provenance, prompt-template provenance, latency, cache-hit state, and explicit moderation metadata. The current revised-spec generation routes wrap that response in a `GeneratedContent` record so the API contract aligns with the authoritative planning package. `POST /api/content/warm` can proactively pre-generate the same content shape and prime the SQLite-backed cache for expected remedial or practice requests, and the live generation path now also performs conservative predictive warming for likely follow-up content such as practice after a worked example or a quick assessment probe after practice. Predictive warmed entries carry durable request-context metadata, reuse the same cache key as later real requests, and are expired when new learner observations or Socratic assessment outcomes change the same learner/session target context. That predictive path now also writes follow-up requests into a durable SQLite queue, uses live route/mode calibration to adapt which follow-up content types are warmed, exposes `POST /api/content/warm/process` so queued warm tasks can be drained explicitly outside the original generation request when needed, can now use spare inline processing budget to catch up other eligible queued work even when the newest enqueue call did not fill the whole local budget, and now records explicit claim owner, claim mode, claim rationale, stale-recovery pickup, and post-run eligible-versus-blocked backlog health for each processing pass so lightweight scheduler autonomy stays inspectable without introducing a full job system. The same persisted cross-session calibration profiles that already influence router support selection now also feed generation-mode calibration, and that calibration now also carries durable learner-state plus cognitive-trait reliability summaries so practice and worked-example planning can react to reliable overload, recovery-stability, or challenge-tolerance evidence instead of treating every durable signal as equally trustworthy. The live observation pipeline now also tags current evidence as `productive_struggle`, `overload`, `disengagement`, or `support_dependence` when the recent pattern is strong enough, surfaces that through inferred learner state plus audit telemetry, uses it to keep durable learner-state blending honest, and lets same-session adaptation plus generation-mode calibration treat healthy low-support struggle differently from overload or support-heavy success before fading support. When the broader cross-session trend is available, router calibration and generation-mode calibration now prefer persisted `learning.progress.profile` events and can react to `improving` or `declining` trajectory, not just static positive/negative snapshots. Practice generation now also carries trajectory-aware progression metadata such as distractor style, distractor family, distractor support intensity, distractor rationale, progression action, and a structured distractor blueprint with named roles, temptation basis, repair cues, and surface-shift guidance, while worked examples now carry fade-focus, progression-action, release-stage, release-intensity, release-transition, visible-step-role, hidden-step-role, transfer-move, release-rationale, and a structured transfer plan that says what to preserve, what changes, and which move the learner owns next. Retrieved grounding now also carries short deterministic curriculum excerpts, and the prompt builder, adaptive prompt selector, validation path, Socratic assessment probes, and deterministic fallback provider all consume that richer grounding package directly, so the backend uses more curriculum substance immediately instead of grounding the provider mostly by titles and thin metadata. The moderation layer is now explicit too: unsafe learner prompts can be short-circuited before provider generation, unsafe generated drafts can be replaced before delivery, category-level moderation matches now surface severity plus matched terms, blocked versus rewritten fallback state is explicit through `decision`, `request_blocked`, `response_rewritten`, `fallback_kind`, and `stream_action`, stream responses buffer provider output until moderation finishes so no unsafe deltas are leaked before a rewrite, blocked-request streams now start in `static_fallback` mode immediately, dedicated `content.moderation` audit events capture the same safety decision, and observability snapshots now summarize moderation category counts plus provider-bypass and buffered-stream rewrite telemetry in addition to request versus response flags. Socratic assessment responses and audit events now also expose explicit steering actions, so an initial `diagnostic` probe can stay an `open_probe` while loop-breaking diagnostics become `probe_from_new_angle`, and recovery after step-back can ask the generation layer to `restate_then_apply` instead of treating every clarification as the same conversational move. Observability snapshots now summarize prompt-template usage counts, Socratic assessment aggregates such as evidence-score averages and profile-update counts, per-template/style Socratic prompt performance summaries, predictive warm activity, predictive warm queue processing and backlog counts, predictive warm ownership/autonomy metrics, predictive cache invalidation totals, expired queued-task totals, supplemental inline catch-up totals, progress-profile trend counts, moderation category totals, and generation prompt-performance summaries that combine immediate quality with explicit run-level outcome summaries, confidence-weighted calibration signals, persisted-summary coverage, aggregated learner-observation traces, same-session Socratic traces, and later cross-generation session outcomes, including average trace depth, so prompt experiments and conversational assessment behavior are inspectable without digging through raw audit events. Those same durable run summaries are now also written into the audit log as first-class `learning.run.summary` events, compacted into cross-session `learning.calibration.profile` and `learning.progress.profile` events, and reused by prompt calibration, route calibration, generation-mode selection, and learner-summary packaging before the system falls back to raw window reconstruction.

Knowledge Components are now first-class persisted entities with prerequisite links, optional catalogued misconception patterns, optional taxonomy fields such as `concept_family` and `taxonomy_cluster_id`, curated `nearby_kc_ids`, and remediation-planner integration. The remedial trigger uses that graph plus misconception signals to step back through weaker prerequisite KCs before returning to the requested target, and it now also emits a structured remediation blueprint with phases such as `step_back`, `repair`, `bridge`, and `return` so the generated remedial module is grounded in a more explicit plan. Remediation responses now include the detected misconception signals, misconception ids, remediation hints, per-KC primary flags, disambiguation scores, sequencing metadata, blueprint, and remediation-session metadata in `request_context`, and `POST /api/remedial/trigger` now starts a persisted workflow session whose later steps can be reloaded with `GET /api/remedial/sessions/{session_id}` and advanced with `POST /api/remedial/sessions/{session_id}/advance`. Repeated remediation classifications are now compacted into durable `learning.misconception.profile` audit events, later similar remedial requests can reuse those profile signals so persistent misconception patterns are not inferred only from the latest free-text description, and overlapping misconception matches on the same KC are now disambiguated down to a single primary repair path before blueprint selection. Learner-strategy signals now also choose a concrete KC sequence, so the remediation workflow can deliberately rebuild a prerequisite first, stay on the repair target, or bridge through a nearby KC from the same LO, concept family, or curated taxonomy neighborhood before the final target return instead of always inserting the same step-back path, and predictive warm follow-ups can now target that same sequenced KC before warming broader transfer checks. The learner API also now accepts observed interaction signals and infers affective state, cognitive load, metacognitive state, and lightweight cognitive trait updates back into the stored profile, including processing speed, working memory, and spatial reasoning estimates derived from recent observation patterns. Observations can now carry task context such as `task_type`, `support_level`, `expected_duration_ms`, and optional linkage fields such as `generation_id`, `learning_session_id`, `observed_content_type`, and target KC/LO ids, so an assessment attempt is interpreted differently from a scaffolded worked example and downstream prompt calibration can prefer exact, same-session, or context-compatible observation matches. Those same linkage fields now also let learner-state updates reuse recent same-target run summaries before persisting metacognitive state, and they now also support a stronger ordinary-work mastery loop: linked practice or remediation observations can blend target KC/LO mastery back through the same KC graph migration layer used by Socratic assessment, repeated same-session target evidence now strengthens that writeback instead of treating each observation alone, and a newer durable `learning.ordinary_mastery.profile` layer now compacts prior ordinary practice and remediation outcomes into explicit `durable_mastery`, `emerging_mastery`, `support_dependent`, or `fragile` signals that the next ordinary writeback can use to slightly trust or discount similar evidence while keeping confidence, rates, and rationale inspectable in audits. The ordinary generation path can now surface an explicit `hold_target` versus `attempt_transfer` posture for the current target while predictive warming follows that decision. That same progression layer can now also rewrite premature assessment probes back into target-aligned practice when recent same-session evidence still says to hold on the concept, and it surfaces `requested_content_type`, `applied_content_type`, `mastery_gate_applied`, and `mastery_gate_reason` through generation metadata and audits so the gate remains inspectable. A newer durable `learning.state.profile` layer can now blend cross-session affective/load/metacognitive targets back into the next live state update when recent outcome history is strong enough, and that same state profile now carries recovery-stability, overload-risk, metacognitive-reliability, plus newer affective/load reliability signals so a sharply strained current observation can block an overconfident cross-session independence pull while still letting stable durable load or affect evidence influence only the dimensions that still match. A newer durable `learning.cognitive_trait.profile` layer can now blend cross-session trait targets back into the next cognitive-trait update when enough observation history exists, and that layer now also carries trait-stability, challenge-tolerance, per-trait reliability, and challenge-evidence-strength signals so the live trait update path can trust strong durable working-memory or processing-speed evidence without over-trusting weaker durable trait dimensions. The router now uses those metacognitive signals to hold back stretch when the learner still appears to need modeled support, and it now also returns a calibration summary on route decisions so recent same-target run outcomes can conservatively increase or relax scaffolding before delivery. There is now also a persisted within-session controller layered on top of that: recent `learner.observe` and `assessment.socratic` events for the same `learning_session_id` can update phase, recovery intent, positive or negative streaks, generated-step counts, the latest Socratic prompt style, the latest Socratic next action, and a compact `socratic_steering_action` so the next generated step can hold on the current target, stay in repair, consolidate recovery, move toward transfer, or switch prompt family with more direct conversational continuity instead of recomputing every request from scratch. `GET /api/learners/{student_id}/summary` now rolls the current learner state together with recent generation, observation, assessment, calibration activity, the latest durable cross-session progress trend, the newest durable state-profile snapshot, and the newest durable cognitive-trait profile snapshot so a frontend can render a learner overview card without replaying audit events client-side. The generation path also supports first-class worked-example fading and practice difficulty bands through the same unified engine, and those mode choices can now be nudged by persisted run-summary calibration rather than only current profile heuristics. Socratic mastery updates now also propagate through a richer KC graph service, with distance-aware weighting across prerequisite and dependent hops, LO-to-KC backfill when historical LO mastery is stronger than KC coverage, local neighborhood detection across same-LO, concept-family, taxonomy-cluster, and curated-neighbor relations, and weighted LO recomputation after propagation instead of treating every KC in an LO as equally strong. The generic `/api/content/generate` path can now auto-select a worked example when learner-state signals favor modeled support before freer explanation, can step from explanation into practice when a recent Socratic transfer check already demonstrated understanding, and can steer prompt-template variants directly from recent conversational step-back or clarification evidence instead of waiting only for longer-horizon summary aggregation. Curriculum grounding is now also more passage-aware: the retriever still ranks whole resources, but each returned grounding item now selects the best local sentence window with semantic plus lexical passage scoring, so prompts, validation, and deterministic fallbacks see a tighter curriculum span instead of whatever broad leading sentence happened to be returned first. The predictive warm queue behind that path is now also more autonomous: tasks carry urgency classes, long-waiting routine tasks earn an aging boost so they can break back into claim rotation, transient provider failures back off differently by urgency class, stale urgent work can recover into the same processing pass instead of waiting for a later sweep, stale tasks are canceled before claim, and observability now exposes eligible-now backlog, blocked deferred work, stale processing counts, urgent active work, and the next-eligible queue delay in addition to deferred, retried, dropped, failed, and canceled warm work. There is also now a persisted conversational assessment flow at `POST /api/assessments/socratic` that scores the current learner response before choosing the next prompt, exposes continuous evidence dimensions such as lexical alignment, reasoning signal, confidence alignment, progression, and misconception risk, and uses an outcome-aware prompt-style policy such as `diagnostic`, `clarification`, `scaffolded_step_back`, or `transfer_check` across multi-turn sessions. Strong Socratic turns now also update target KC/LO mastery plus metacognitive readiness in the stored profile so later router decisions can respond to conversational evidence rather than treating assessment as an isolated side channel, and those same-session assessment outcomes can now feed generation prompt calibration as part of an aggregated downstream trace that can continue across later generated steps in the same learning session. Sessions can be reloaded with `GET /api/assessments/socratic/{session_id}`. Observability snapshots now include cache-hit counts, warm-request totals, predictive warm and invalidation totals, queue backlog, deferred counts, eligible-versus-blocked queue health, next-eligible delay, prompt-template usage, and generation prompt-performance summaries so pre-generation and prompt experiments are visible without extra instrumentation.

## Suggested Next Build Steps

1. Replace or augment SQLite with production persistence such as Redis/PostgreSQL or Redis/Cassandra.
2. Replace the SQLite embedding cache with a production vector store and background indexing pipeline while keeping the retriever plugin contract stable.
3. Deepen predictive scheduler quality only where real backlog and outcome traces justify it.
4. Revisit broader progression orchestration only if the current local mastery and sequencing layers expose a clear gap.
5. Keep Socratic adaptation local and inspectable unless longer-run traces justify richer discourse planning.
