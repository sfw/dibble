# From Front To Back Needs

Last updated: 2026-03-17

This document is the current frontend-informed marching-order note for backend work.

Use it to answer:

- what the backend still needs to improve for the current frontend product direction
- which previously blocking frontend asks are now resolved and should stay backend-owned
- which future backend investments are conditional rather than urgent

## Current Frontend Reality

- There are no active `P0` or `P1` backend blockers for the current frontend scope.
- The frontend is already building on backend-owned learner summary, `current_flow`, learner workspace, learner history, generation `workflow_summary`, Socratic session summaries, remediation session summaries, learner progression, teacher intervention, classroom, `continue_action`, and machine-readable error contracts.
- The main frontend work right now is implementation depth, workflow polish, explainability curation, and behavioral test coverage on top of those existing backend contracts.
- The backend should keep owning progression, mastery, intervention, and resume decisions. The frontend should render those decisions, not reconstruct or soften them locally.

## What The Frontend Needs From The Backend Right Now

Nothing new is required for the current frontend implementation stream.

The backend marching order for the current frontend scope is:

1. preserve the existing frontend-facing contract set
2. keep cross-surface parity and vocabulary stability strong
3. continue improving backend decision quality without pushing policy back into the UI

That means the frontend is not currently asking for a new endpoint family, new contract shape, or frontend-specific policy workaround.

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
| P1 | `ORCH-001` learner progression orchestration | Keep strengthening backend ownership of “what should this learner do next?” across ordinary generation, remediation, Socratic follow-up, workspace resume, and classroom drill-in, but do not treat this as a request for new frontend-owned logic or a new contract family right now. |
| P1 | `ADAPT-006` mastery-loop enforcement | Keep tightening hold / advance / return / transfer gates so repair, bridge, target, and transfer states remain stable and inspectable across workflows. This improves frontend trust, but does not currently require a frontend contract change. |
| P1 | `DATA-004` ordinary-work evidence handling | Keep improving how ordinary practice and remediation evidence influence progression, rationale, and durable confidence so existing teacher and learner surfaces become more trustworthy without UI workarounds. |
| P1 | `ADAPT-003` misconception detection / classification | Keep improving misconception precision, recurrence handling, and remediation targeting so backend-owned rationale and intervention packaging read more cleanly in existing surfaces. |

## Conditional Next-Wave Backend Work

These are valid backend directions, but they are not current frontend blockers and should not displace the preserve-and-harden posture above without product pressure.

| Priority | Area | When it becomes worth doing | Frontend stance until then |
|---|---|---|---|
| P2 | `ORCH-002` course-level planner | Only if product scope outgrows the current learner `curriculum_progression` contract and the product genuinely needs backend-owned cross-unit / course sequencing authority. | Keep trusting learner `curriculum_progression`; do not invent cross-unit sequencing in the UI. |
| P2 | `GEN-005` richer multimodal artifacts | Only when actual non-text artifacts are ready to ship as product, not just as a speculative schema exercise. | Keep the UI extensible, but route future artifacts through `response.artifacts` rather than stretching text-only block payloads. |
| P2 | teacher-safe analytics expansion | Only if teacher workflows need more than classroom counts, learner cards, intervention summaries, and current rationale fields. | Keep teacher surfaces summary-first; do not pull admin-style telemetry into the frontend. |

## Backend Review Notes

- `planning/current-backend-gap-analysis.md` now says the backend is effectively ready for the current frontend scope and that remaining frontend-originated asks are narrow and conditional.
- `planning/front-end-work-plan.md` now shows the frontend stream is focused on workflow polish, explainability curation, CSS cleanup, and test depth rather than waiting on new backend contracts.
- Backend commit `93954f9` ("Tighten repair-stage ordinary mastery progression") is aligned with the frontend plan.
- It strengthens target-scoped durable ordinary mastery lookup and makes `hold_repair_target` more trustworthy.
- It does not create a new frontend contract gap and does not justify any frontend-owned progression workaround.
- Recent frontend explainability, shell/fallback, and CSS cleanup passes also did not surface a new backend blocker.
- The latest teacher-decision continuity and routing-coverage pass also did not surface a new backend blocker; the current intervention, workspace, history, and classroom contracts were sufficient once the frontend honored backend latest-decision state more faithfully.
- The latest app-level fallback aggregation and failure-path coverage pass also did not surface a new backend blocker; the main issue was frontend shell honesty when one surface fell back while others stayed live.

## Frontend Guardrails While This Stance Holds

- Prefer backend-owned learner `curriculum_progression` over frontend sequencing logic.
- Prefer backend-owned classroom read models over client-side dashboard aggregation.
- Prefer backend-owned workspace, history, and intervention contracts over frontend-only resume or override logic.
- Trust backend-owned workflow vocabularies and machine-readable error `code` values rather than display strings.
- Treat backend progression, mastery, misconception, and rationale work as backend decision-quality improvements, not invitations for the frontend to reclaim authority.

## What The Backend Agent Should Avoid Doing “For The Frontend”

- Do not add frontend-only sequencing policy to compensate for incomplete progression authority.
- Do not add teacher telemetry or dashboard-grade analytics unless classroom summaries and learner cards are truly insufficient.
- Do not extend multimodal payloads by overloading existing text-only fields when `response.artifacts` is the intended extension seam.
- Do not reopen already-resolved contract seams unless there is a concrete bug, parity issue, or vocabulary drift.
- Do not interpret backend quality work as a reason to churn stable frontend-facing contracts that are already serving the current product stream.
