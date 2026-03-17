# From Front To Back Needs

Last updated: 2026-03-17

This document tracks backend-facing needs discovered while implementing the frontend.

It should contain:

- missing read models the frontend cannot responsibly invent
- missing write contracts for teacher or workflow actions
- contract clarifications that reduce fragile UI assumptions

## Current Backend Needs

### P0

- No active P0 backend blockers remain for the current frontend scope.

### P1

- A true course-level planner only if product needs exceed the new learner `curriculum_progression` read model and the current classroom/learner views start needing stronger cross-unit sequencing authority.

### P2

- Richer artifact payload contracts for multimodal or interactive content.
- More compact explainability-oriented teacher analytics if the product needs more than the current learner cards, intervention summaries, and classroom-level counts.

## Frontend Stance Until These Exist

- Prefer the backend-owned learner `curriculum_progression` contract over inventing broader sequencing logic in the UI.
- Prefer the backend-owned classroom read models over aggregating single-learner responses into a teacher dashboard in the frontend.
- Keep the new learner workspace, history, and intervention surfaces wired to backend-owned contracts rather than adding frontend-only resume or override logic.
- Trust the backend-owned workflow vocabularies and machine-readable error `code` values rather than inferring semantics from display strings.

## Recently Resolved On The Backend

- learner-scoped generation, Socratic-session, and remediation-session history endpoints now exist
- learner workspace resume/read model now exists
- backend-owned `continue_action` contracts now exist across the main learner workflow surfaces
- teacher intervention action read/write contracts now exist
- learner curriculum progression read models now exist through `GET /api/learners/{student_id}/progression` and `summary.curriculum_progression`
- teacher classroom read models now exist through `GET /api/teachers/classrooms` and `GET /api/teachers/classrooms/{classroom_id}`
- progression parity is now regression-protected across learner progression, learner summary, and teacher classroom learner cards
- `continue_action` and teacher intervention vocabularies are now explicit backend-owned contract sets rather than loose cross-surface strings
- machine-readable error codes now arrive in both the JSON body and the `X-Dibble-Error-Code` header
