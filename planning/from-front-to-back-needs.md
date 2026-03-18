# From Front To Back Needs

Last updated: 2026-03-17

This document is the current frontend-informed marching-order note for backend work.

Use it to answer:

- what the backend still needs to improve for the current frontend product direction
- which previously blocking frontend asks are now resolved and should stay backend-owned
- which future backend investments are conditional rather than urgent

## Current Frontend Reality

- The three P1 backend asks (triage section ownership, affective support messages, display labels) are now resolved. The backend provides `triage_section` on `TeacherLearnerCard`, `affective_support` on `LearnerWorkspace`, and `display_label`/`stage_display_label` on `LearnerContinueAction`/`LearnerCurriculumProgressionSummary`. The frontend shims have been removed and replaced with direct rendering of backend-provided fields.
- The frontend is already building on backend-owned learner summary, `current_flow`, learner workspace, learner history, generation `workflow_summary`, Socratic session summaries, remediation session summaries, learner progression, teacher intervention, classroom, `continue_action`, and machine-readable error contracts.
- The main frontend work right now is implementation depth, workflow polish, explainability curation, and behavioral test coverage on top of those existing backend contracts.
- The backend should keep owning progression, mastery, intervention, and resume decisions. The frontend should render those decisions, not reconstruct or soften them locally.
- The frontend no longer interprets raw signals or machine-readable keys to make pedagogical decisions. The `copy.ts` lookup tables remain as backwards-compatible fallbacks but prefer backend-provided labels when available.

## Resolved P1 Backend Asks

All three P1 frontend-to-backend asks are now complete:

### Resolved: Backend-owned triage sections on TeacherLearnerCard

**Backend provides:** `triage_section` field on `TeacherLearnerCard` with values `teacher_action`, `needs_attention`, `on_track`.

**Frontend integration:** `lib/triage.ts:buildTriageSections()` now groups by `triage_section` directly — no signal interpretation.

### Resolved: Backend-owned affective support messages

**Backend provides:** `affective_support` field on `LearnerWorkspace` with `{ kind, title, detail }` or `null`.

**Frontend integration:** `components/content/AffectiveSupport.tsx` renders the backend-provided message directly — no frustration/engagement threshold logic.

### Resolved: Backend-owned display labels alongside machine-readable keys

**Backend provides:** `display_label` on `LearnerContinueAction`, `stage_display_label` on `LearnerCurriculumProgressionSummary`.

**Frontend integration:** `lib/copy.ts` functions accept and prefer `backendLabel` parameter. Local lookup tables remain as backwards-compatible fallbacks only.

### Ongoing backend marching order

1. preserve the existing frontend-facing contract set
2. keep cross-surface parity and vocabulary stability strong
3. continue improving backend decision quality without pushing policy back into the UI

## Preserve And Harden

These backend-owned seams are already good enough for the active frontend roadmap and should stay stable:

- learner workspace resume/read model
- learner-scoped generation, Socratic-session, and remediation-session history
- backend-owned cross-surface `continue_action` contract
- teacher intervention read/write contract
- learner curriculum progression read model and parity across summary/classroom surfaces
- teacher classroom read models
- machine-readable error code parity between response body and header
- hardened backend vocabularies for `continue_action` and teacher intervention states
- explicit `workflow_summary` and session-summary contracts across generation, Socratic, remediation, and streaming paths

## Backend Quality Work That Still Matters

These are still valuable backend directions, but from the frontend perspective they are quality/depth improvements rather than active contract asks.

| Priority | Area | Frontend stance |
|---|---|---|
| P1 | `ORCH-001` learner progression orchestration | Keep strengthening backend ownership of “what should this learner do next?” across ordinary generation, remediation, Socratic follow-up, workspace resume, and classroom drill-in, with a bias toward semantic parity: the same learner decision should read like one judgment across `current_flow`, workspace, history, `workflow_summary`, intervention, and classroom cards. |
| P1 | `ADAPT-006` mastery-loop enforcement | Keep tightening hold / advance / return / transfer gates so repair, bridge, target, and transfer states remain stable and inspectable across workflows. The frontend need is not a new field; it is rationale strong enough to explain why the backend held this stage instead of the adjacent one. |
| P1 | `DATA-004` ordinary-work evidence handling | Keep improving how ordinary practice and remediation evidence influence progression, rationale, and durable confidence so existing teacher and learner surfaces become more trustworthy without UI workarounds. The best payoff now is clearer evidence-weighted rationale in existing contracts, especially when ordinary evidence overrides or tempers same-session momentum. |
| P1 | `ADAPT-003` misconception detection / classification | Keep improving misconception precision, recurrence handling, and remediation targeting so backend-owned rationale and intervention packaging read more cleanly in existing surfaces. The frontend signal to optimize for is not more schema; it is a more trustworthy explanation of which misconception path won and why. |

## Marching Orders After The Latest Backend Review

The latest backend stack on `main` is aligned with the frontend stance and should shift the backend marching orders further toward semantic depth over contract expansion.

The five highest-value backend directions from the frontend perspective are now:

1. keep auditing cross-surface next-step parity so `current_flow`, learner workspace, generation `workflow_summary`, session summaries, history entries, intervention options, and classroom learner cards all describe the same backend decision with the same stage semantics.
2. keep making rationale fields decision-grade instead of merely present, especially where the UI needs to explain why the backend held repair, bridge, target, or transfer instead of the adjacent stage.
3. keep making ordinary-work evidence legible inside existing rationale text so the frontend can present backend holds, resumes, and transfer checks confidently without inventing extra interpretation.
4. keep making misconception-path selection more inspectable inside existing remediation and intervention rationale so the chosen repair target feels earned rather than heuristic or arbitrary.
5. keep treating “same label, different meaning” drift as a backend bug even when the contract shape does not change.

## Conditional Next-Wave Backend Work

These are valid backend directions, but they are not current frontend blockers and should not displace the preserve-and-harden posture above without product pressure.

| Priority | Area | When it becomes worth doing | Frontend stance until then |
|---|---|---|---|
| P2 | `ORCH-002` course-level planner | Only if product scope outgrows the current learner `curriculum_progression` contract and the product genuinely needs backend-owned cross-unit / course sequencing authority. | Keep trusting learner `curriculum_progression`; do not invent cross-unit sequencing in the UI. |
| P2 | `GEN-005` richer multimodal artifacts | Only when actual non-text artifacts are ready to ship as product, not just as a speculative schema exercise. | Keep the UI extensible, but route future artifacts through `response.artifacts` rather than stretching text-only block payloads. |
| P2 | teacher-safe analytics expansion | Only if teacher workflows need more than classroom counts, learner cards, intervention summaries, and current rationale fields. | Keep teacher surfaces summary-first; do not pull admin-style telemetry into the frontend. |
| P2 | generation quality metadata on history entries | The teacher learner-detail view would benefit from showing generation quality (quality_score, validation_passed, moderation decision, latency) for recent content. Currently `LearnerGenerationHistoryEntry` doesn't carry `GenerationMetadata`. Adding an optional `metadata` field on history entries would let the teacher view surface quality without a separate API call per generation. | Not blocking; teacher view works without it. Add when teacher quality-inspection workflows become a product priority. |

## Backend Review Notes

- `planning/current-backend-gap-analysis.md` now says the backend is effectively ready for the current frontend scope and that remaining frontend-originated asks are narrow and conditional.
- `planning/front-end-work-plan.md` now shows the frontend stream is focused on workflow polish, explainability curation, CSS cleanup, and test depth rather than waiting on new backend contracts.
- Backend commit `93954f9` ("Tighten repair-stage ordinary mastery progression") is aligned with the frontend plan.
- It strengthens target-scoped durable ordinary mastery lookup and makes `hold_repair_target` more trustworthy.
- It does not create a new frontend contract gap and does not justify any frontend-owned progression workaround.
- Recent frontend explainability, shell/fallback, and CSS cleanup passes also did not surface a new backend blocker.
- The latest teacher-decision continuity and routing-coverage pass also did not surface a new backend blocker; the current intervention, workspace, history, and classroom contracts were sufficient once the frontend honored backend latest-decision state more faithfully.
- The latest app-level fallback aggregation and failure-path coverage pass also did not surface a new backend blocker; the main issue was frontend shell honesty when one surface fell back while others stayed live.
- Backend commits from `329d26c` through `873d2ba` on March 17, 2026 are also aligned with the frontend plan.
- They meaningfully improve misconception-path grounding, ordinary-work and same-session rationale snapshots, stage-aware teacher labels/rationales, held-remediation parity, and cross-surface workflow rationale preference without introducing a new frontend contract seam.
- The frontend-facing result is positive: the contracts now read more like product decisions and less like raw debug state.
- The remaining opportunity is semantic consistency and rationale trustworthiness, not endpoint expansion.
- A local live smoke pass against the rebased backend also succeeded for learner summary/flow, progression, workspace, generation history, intervention, and classroom surfaces after seeding one learner/classroom scenario.
- That smoke pass did not surface a new backend blocker; the latest backend stack looked contract-stable enough for frontend merge readiness.

## Frontend Guardrails While This Stance Holds

- Prefer backend-owned learner `curriculum_progression` over frontend sequencing logic.
- Prefer backend-owned classroom read models over client-side dashboard aggregation.
- Prefer backend-owned workspace, history, and intervention contracts over frontend-only resume or override logic.
- Trust backend-owned workflow vocabularies and machine-readable error `code` values rather than display strings.
- Treat backend progression, mastery, misconception, and rationale work as backend decision-quality improvements, not invitations for the frontend to reclaim authority.

## Frontend Feedback To Keep Sending Back

While the current contracts stay stable, the most valuable frontend feedback to shape backend work is:

- places where two surfaces use the same backend-owned label but appear to mean different things in actual product UI
- places where rationale is technically present but still too weak or hedged to present confidently to teachers or learners
- places where repair, bridge, target, and transfer decisions feel under-justified or inconsistent when a user moves across overview, teacher, classroom, history, and resume flows

## What The Backend Agent Should Avoid Doing “For The Frontend”

- Do not add frontend-only sequencing policy to compensate for incomplete progression authority.
- Do not add teacher telemetry or dashboard-grade analytics unless classroom summaries and learner cards are truly insufficient.
- Do not extend multimodal payloads by overloading existing text-only fields when `response.artifacts` is the intended extension seam.
- Do not reopen already-resolved contract seams unless there is a concrete bug, parity issue, or vocabulary drift.
- Do not interpret backend quality work as a reason to churn stable frontend-facing contracts that are already serving the current product stream.
