# From Front To Back Needs

Last updated: 2026-03-17

This document is the current frontend-informed marching-order note for backend work.

Use it to answer:

- what the backend still needs to improve for the current frontend product direction
- which previously blocking frontend asks are now resolved and should stay backend-owned
- which future backend investments are conditional rather than urgent

## Current Frontend Reality

- There are three active P1 backend asks: triage section ownership, affective support messages, and display labels on machine-readable keys. All three have working frontend shims, so they are not blockers, but the frontend is currently making pedagogical decisions that should be backend-owned.
- The frontend is already building on backend-owned learner summary, `current_flow`, learner workspace, learner history, generation `workflow_summary`, Socratic session summaries, remediation session summaries, learner progression, teacher intervention, classroom, `continue_action`, and machine-readable error contracts.
- The main frontend work right now is implementation depth, workflow polish, explainability curation, and behavioral test coverage on top of those existing backend contracts.
- The backend should keep owning progression, mastery, intervention, and resume decisions. The frontend should render those decisions, not reconstruct or soften them locally.
- The frontend should not interpret raw signals or machine-readable keys to make pedagogical decisions. Where it currently does, it is documented as a temporary shim awaiting backend ownership.

## What The Frontend Needs From The Backend Right Now

The frontend has identified three areas where it is currently making decisions that should be backend-owned. These are documented as temporary frontend shims that should be replaced once the backend provides the corresponding contracts.

### P1: Backend-owned triage sections on TeacherLearnerCard

**Current state:** The frontend groups learners into triage sections (needs teacher action, needs attention, on track) by interpreting `attention_level` and `intervention.proposal_status` locally in `lib/triage.ts`. This sorting logic is a backend decision about which learners a teacher should focus on.

**Ask:** Add a `triage_section` field (or equivalent) to `TeacherLearnerCard` so the backend owns the categorization. Values like `teacher_action`, `needs_attention`, `on_track` would let the frontend group without interpreting signals. The backend already computes `attention_level` — this is a small step further to also own the grouping decision.

**Frontend shim location:** `frontend/src/lib/triage.ts:buildTriageSections()`

### P1: Backend-owned affective support messages

**Current state:** The frontend interprets raw `frustration` and `engagement` signal levels to decide when to show support messages ("It's okay to take a break", "You're on a roll!") in `components/content/AffectiveSupport.tsx`. The thresholds, priority order, and message content are all hardcoded pedagogical decisions.

**Ask:** Add an optional `affective_support` field to the learner workspace or profile summary:
```
affective_support?: {
  kind: 'break_suggestion' | 'nudge' | 'encouragement'
  title: string
  detail: string
} | null
```
When null, the frontend shows nothing. When present, the frontend renders the message. This lets the backend own the pedagogical rules for when and what to show, and makes them configurable, versionable, and A/B testable.

**Frontend shim location:** `frontend/src/components/content/AffectiveSupport.tsx:resolveAffectiveMessage()`

### P1: Backend-owned display labels alongside machine-readable keys

**Current state:** The frontend maintains hardcoded lookup tables in `lib/copy.ts` that map backend keys to role-appropriate display strings (e.g. `repair` → `"Building foundations"` for learners, `repair` → `"Repair"` for teachers). These are pedagogical framing decisions — the choice to call the repair stage "Building foundations" for a learner is a product/pedagogy decision, not a presentation concern.

**Ask:** Add optional `display_label` fields alongside machine-readable keys on learner-facing and teacher-facing contracts. For example:
- `continue_action.kind` → also provide `continue_action.display_label`
- `curriculum_progression.current_stage` → also provide `curriculum_progression.stage_display_label`
- `remediation_step.phase` → also provide `remediation_step.phase_display_label`

The frontend `copy.ts` functions already accept an optional `backendLabel` parameter and will prefer the backend-provided label when available, falling back to the local table only for backwards compatibility.

**Frontend shim location:** `frontend/src/lib/copy.ts` (all lookup tables)

### Backend marching order

1. preserve the existing frontend-facing contract set
2. add `triage_section` to `TeacherLearnerCard`
3. add `affective_support` to learner workspace/profile
4. add `display_label` fields alongside machine-readable keys on learner and teacher contracts
5. keep cross-surface parity and vocabulary stability strong
6. continue improving backend decision quality without pushing policy back into the UI

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
