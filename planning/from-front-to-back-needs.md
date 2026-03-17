# From Front To Back Needs

Last updated: 2026-03-17

This document is the current frontend-informed marching-order note for backend work.

Use it to answer:

- what the backend still needs to improve for the current frontend product direction
- which previously blocking frontend asks are now resolved and should stay backend-owned
- which future backend investments are conditional rather than urgent

## Current Frontend Reality

- There are no active `P0` backend blockers for the current frontend scope.
- The frontend is already wired to backend-owned `current_flow`, `curriculum_progression`, `workflow_summary`, `continue_action`, learner workspace, learner history, teacher intervention, classroom, and machine-readable error contracts.
- The backend should keep owning progression, mastery, intervention, and resume decisions. The frontend should render those decisions, not reconstruct or soften them locally.

## Active Marching Orders

These are the highest-value backend improvements for the current frontend stream.

| Priority | Area | Marching order for backend | Why the frontend cares | Done looks like |
|---|---|---|---|---|
| P1 | `ORCH-001` learner progression orchestration | Keep strengthening backend ownership of “what should this learner do next?” across ordinary generation, remediation, Socratic follow-up, workspace resume, and classroom drill-in. | The frontend now has multiple learner and teacher entry points; they all need the same backend-owned next-step authority without screen-specific policy. | `current_flow`, `workflow_summary`, session summaries, workspace, history, and classroom cards continue to agree on stage, action, rationale, and next-step semantics. |
| P1 | `ADAPT-006` mastery-loop enforcement | Keep tightening hold / advance / return / transfer gates so repair, bridge, target, and transfer states are stable and inspectable across workflows. | The teacher triage flow and learner handoff UX are only trustworthy when backend stage transitions are honest and durable. | Backend holds and returns survive across workflow summaries and read models without the frontend needing “special-case” interpretation. |
| P1 | `DATA-004` ordinary-work evidence handling | Improve how ordinary practice and remediation evidence influence progression, intervention rationale, and durable confidence. | The frontend is already surfacing explainability and intervention rationale; better evidence quality improves those surfaces without new UI logic. | Backend rationale, confidence, and progression decisions rely less on brittle heuristics and more on stronger target-scoped evidence. |
| P1 | `ADAPT-003` misconception detection / classification | Keep improving misconception precision, recurrence handling, and remediation targeting so the backend packages cleaner explanations and options. | Teacher intervention and remediation surfaces get better when misconception targeting is more precise and less debug-shaped. | Backend returns more specific misconception-informed rationale and alternative packaging without asking the frontend to classify learner errors. |

## Conditional Next-Wave Backend Work

These are valid backend directions, but they are not current frontend blockers and should not displace the active marching orders above without product pressure.

| Priority | Area | When it becomes worth doing | Frontend stance until then |
|---|---|---|---|
| P2 | `ORCH-002` course-level planner | Only if product scope outgrows the current learner `curriculum_progression` contract and the product genuinely needs backend-owned cross-unit / course sequencing authority. | Keep trusting learner `curriculum_progression`; do not invent cross-unit sequencing in the UI. |
| P2 | `GEN-005` richer multimodal artifacts | Only when actual non-text artifacts are ready to ship as product, not just as a speculative schema exercise. | Keep the UI extensible, but route future artifacts through `response.artifacts` rather than stretching text-only block payloads. |
| P2 | teacher-safe analytics expansion | Only if teacher workflows need more than classroom counts, learner cards, intervention summaries, and current rationale fields. | Keep teacher surfaces summary-first; do not pull admin-style telemetry into the frontend. |
| P2 | `LLM-003` stronger curriculum-to-generation fidelity | Only if grounding quality becomes a visible product problem beyond the current partial RAG stack. | Treat this as backend quality improvement, not a reason for frontend-owned curriculum interpretation. |

## Resolved Or No Longer Current Backend Asks

These were once frontend-facing needs and are now sufficiently shipped that they should stay in the “preserve and harden” bucket rather than the “invent new work” bucket.

- learner workspace resume/read model
- learner-scoped generation, Socratic-session, and remediation-session history
- backend-owned cross-surface `continue_action` contract
- teacher intervention read/write contract
- learner curriculum progression read model and parity across summary/classroom surfaces
- teacher classroom read models
- machine-readable error code parity between response body and header
- hardened backend vocabularies for `continue_action` and teacher intervention states

## Backend Review Notes

- Backend commit `93954f9` ("Tighten repair-stage ordinary mastery progression") is aligned with the frontend plan.
- It strengthens target-scoped durable ordinary mastery lookup and makes `hold_repair_target` more trustworthy.
- It does not create a new frontend contract gap and does not justify any frontend-owned progression workaround.
- The latest frontend explainability and label-curation pass also did not surface a new backend blocker; existing backend contracts were sufficient once the UI stopped rendering them so literally.
- The latest shell-level fallback and handoff continuity pass also did not surface a new backend blocker; current learner workspace, classroom, history, and intervention contracts were sufficient once the frontend made source posture and handoff state more explicit.

## Frontend Guardrails While These Needs Remain

- Prefer backend-owned learner `curriculum_progression` over frontend sequencing logic.
- Prefer backend-owned classroom read models over client-side dashboard aggregation.
- Prefer backend-owned workspace, history, and intervention contracts over frontend-only resume or override logic.
- Trust backend-owned workflow vocabularies and machine-readable error `code` values rather than display strings.
- Treat remaining `ORCH-*`, `ADAPT-*`, `DATA-*`, and `LLM-*` work as backend decision-quality improvements, not invitations for the frontend to reclaim authority.

## What The Backend Agent Should Avoid Doing “For The Frontend”

- Do not add frontend-only sequencing policy to compensate for incomplete progression authority.
- Do not add teacher telemetry or dashboard-grade analytics unless classroom summaries and learner cards are truly insufficient.
- Do not extend multimodal payloads by overloading existing text-only fields when `response.artifacts` is the intended extension seam.
- Do not reopen already-resolved contract seams unless there is a concrete bug, parity issue, or vocabulary drift.
