# From Front To Back Needs

Last updated: 2026-03-17

This document is the current frontend-informed marching-order note for backend work.

Use it to answer:

- what the backend still needs to build or improve for the current frontend product direction
- which previously blocking frontend asks are now resolved and should stay backend-owned
- which future backend investments are conditional rather than urgent

## Current Frontend Reality

The frontend has moved from a contract integration workbench to a three-layer LMS interface (learner / teacher / staff) per `planning/lms-interface-plan.md`. PR #3 merged the LMS shell onto `main`.

What's built:
- Learner shell: home, continue-learning, Socratic check, remediation session, progress, history
- Teacher shell: dashboard, classroom detail, learner detail, intervention workspace
- Staff shell: the original workbench, repositioned as internal tooling
- Role-based routing, content rendering components, vocabulary translation layer, 16 test files

What the frontend is building against:
- backend-owned learner summary, `current_flow`, workspace, history, progression, generation `workflow_summary`, Socratic summaries, remediation summaries, intervention-action, classroom, `continue_action`, and machine-readable error contracts
- backend-owned `triage_section`, `affective_support`, `display_label` / `stage_display_label` fields
- the frontend does not interpret raw signals or make pedagogical decisions

## Recently Resolved P1 Backend Asks

### Resolved: Assignment model and lifecycle (was P1)

**Backend now provides:** A first-class `Assignment` entity with teacher attribution (`teacher_id`), learner targeting (`student_id`, `target_resource_id`, `target_kc_ids`, `target_lo_ids`), lifecycle status (`assigned` → `in_progress` → `completed` → `canceled`), optional scheduling (`due_at`), and timestamps. API surface: `POST /api/assignments` (teacher creates), `GET /api/assignments/{id}`, `PATCH /api/assignments/{id}` (status update), `GET /api/learners/{id}/assignments` (paginated), `GET /api/teachers/assignments` (paginated).
**Frontend now provides:** TypeScript types (`Assignment`, `AssignmentCreate`, `AssignmentPage`) and API functions (`createAssignment`, `getAssignment`, `updateAssignmentStatus`, `getLearnerAssignments`, `getTeacherAssignments`). Frontend still needs assignment views in learner and teacher shells.

## Recently Resolved Backend Asks

### Resolved: Product-level authentication flow (was P0)

**Backend now provides:** `learner` and `teacher` RBAC roles with entity bindings (`learner_id`, `teacher_id`, `display_name`, `classroom_ids`) that persist through API keys, bearer tokens, token refresh, and `/api/auth/me`. Principal config format: `api_key:principal_id:learner:student-uuid:Display Name` and `api_key:principal_id:teacher:teacher-uuid:Name:classroom-1,classroom-2`.
**Frontend now provides:** login screen (`/login`), role-aware redirect on login, bearer token session persistence via `useAuth` hook, `AuthGuard` component gating `/learn` and `/teacher` routes, logout from shell headers, and `AuthContext` for app-wide auth state. The `RoleSwitcher` auto-redirects authenticated users to their role-appropriate shell.

### Resolved: History pagination (was P1)

**Backend now provides:** all three history endpoints return `{ items, offset, limit, has_more }` paginated responses with offset-based pagination, limit clamped to 1–100.
**Frontend now provides:** `useLearnerContracts` hook tracks `hasMoreHistory` state across all three history types and exposes a `loadMoreHistory` function. The History view shows a "Load more" button when more entries are available.

## Resolved P1 Backend Asks

All three prior P1 frontend-to-backend asks are complete:

### Resolved: Backend-owned triage sections on TeacherLearnerCard

**Backend provides:** `triage_section` field with values `teacher_action`, `needs_attention`, `on_track`.
**Frontend integration:** `lib/triage.ts:buildTriageSections()` groups by `triage_section` directly.

### Resolved: Backend-owned affective support messages

**Backend provides:** `affective_support` field on `LearnerWorkspace` with `{ kind, title, detail }` or `null`.
**Frontend integration:** `components/content/AffectiveSupport.tsx` renders the backend-provided message directly.

### Resolved: Backend-owned display labels alongside machine-readable keys

**Backend provides:** `display_label` on `LearnerContinueAction`, `stage_display_label` on `LearnerCurriculumProgressionSummary`.
**Frontend integration:** `lib/copy.ts` functions accept and prefer `backendLabel` parameter.

## Preserve And Harden

These backend-owned seams are already good enough for the active frontend roadmap and should stay stable:

- learner workspace resume/read model
- learner-scoped generation, Socratic-session, and remediation-session history
- backend-owned cross-surface `continue_action` contract
- teacher intervention read/write contract
- learner curriculum progression read model and parity across summary/classroom surfaces
- teacher classroom read models with `triage_section`
- machine-readable error code parity between response body and header
- hardened backend vocabularies for `continue_action` and teacher intervention states
- explicit `workflow_summary` and session-summary contracts
- `affective_support` on learner workspace
- `display_label` / `stage_display_label` on learner-facing and teacher-facing contracts
- `display_rationale` on `TeacherLearnerCard` for canonical teacher-facing rationale

## Backend Quality Work That Still Matters

These are valuable backend directions. From the frontend perspective they improve the product without requiring new contracts.

| Priority | Area | Frontend stance |
|---|---|---|
| P1 | `ORCH-001` learner progression orchestration | Keep strengthening "what should this learner do next?" across ordinary generation, remediation, Socratic, workspace resume, and classroom drill-in. The same decision should read like one judgment across all surfaces. |
| P1 | `ADAPT-006` mastery-loop enforcement | Keep tightening hold / advance / return / transfer gates. The frontend needs rationale strong enough to explain why the backend held this stage instead of the adjacent one. |
| P1 | `DATA-004` ordinary-work evidence handling | Keep improving how ordinary practice and remediation evidence influence progression, rationale, and durable confidence. The payoff is clearer evidence-weighted rationale in existing contracts. |
| P1 | `ADAPT-003` misconception detection / classification | Keep improving misconception precision and remediation targeting. The signal to optimize for is a more trustworthy explanation of which misconception path won and why. |

## Conditional Next-Wave Backend Work

These are valid backend directions but not current frontend blockers. They should not displace the preserve-and-harden posture without product pressure.

| Priority | Area | When it becomes worth doing | Frontend stance until then |
|---|---|---|---|
| ~~P1~~ | ~~Assignment model / lifecycle~~ | **RESOLVED** — first-class `Assignment` entity with teacher attribution, lifecycle, and paginated endpoints | Frontend needs assignment views in learner and teacher shells |
| P2 | `ORCH-002` course-level planner | Only if product scope outgrows the current learner `curriculum_progression` contract | Keep trusting `curriculum_progression`; do not invent cross-unit sequencing in the UI |
| P2 | `GEN-005` richer multimodal artifacts | When actual non-text artifacts are ready to ship as product | Route future artifacts through `response.artifacts` |
| P2 | Teacher-safe analytics expansion | Only if teacher workflows need more than classroom counts, learner cards, intervention summaries, and current rationale fields | Keep teacher surfaces summary-first |
| P2 | Generation quality metadata on history entries | When teacher quality-inspection workflows become a priority | Not blocking; teacher view works without it |
| P2 | Teacher-to-learner messaging / comments | When the product needs an in-app communication channel | Do not build a frontend-only messaging system |
| P2 | Notifications / inbox | When push or pull notification surfaces are product-justified | Do not invent notification polling in the frontend |

## Frontend Guardrails While This Stance Holds

- Prefer backend-owned learner `curriculum_progression` over frontend sequencing logic.
- Prefer backend-owned classroom read models over client-side dashboard aggregation.
- Prefer backend-owned workspace, history, and intervention contracts over frontend-only resume or override logic.
- Trust backend-owned workflow vocabularies and machine-readable error `code` values rather than display strings.
- Treat backend progression, mastery, misconception, and rationale work as backend decision-quality improvements, not invitations for the frontend to reclaim authority.
- Do not invent assignment, messaging, or notification logic without backend ownership.

## Frontend Feedback To Keep Sending Back

The most valuable frontend feedback to shape backend work:

- places where two surfaces use the same backend-owned label but appear to mean different things in actual product UI
- places where rationale is technically present but still too weak or hedged to present confidently to teachers or learners
- places where repair, bridge, target, and transfer decisions feel under-justified or inconsistent across overview, teacher, classroom, history, and resume flows
- contract gaps surfaced by building real learner and teacher UX (not just contract inspection)

## What The Backend Agent Should Avoid Doing "For The Frontend"

- Do not add frontend-only sequencing policy to compensate for incomplete progression authority.
- Do not add teacher telemetry or dashboard-grade analytics unless classroom summaries and learner cards are truly insufficient.
- Do not extend multimodal payloads by overloading existing text-only fields when `response.artifacts` is the intended extension seam.
- Do not reopen already-resolved contract seams unless there is a concrete bug, parity issue, or vocabulary drift.
- Do not interpret backend quality work as a reason to churn stable frontend-facing contracts that are already serving the current product stream.
- Do not build assignment, messaging, or notification contracts speculatively; wait for this document to promote them to active asks.
