# Frontend Work Plan

Last updated: 2026-03-17

## Purpose

This document tracks the frontend implementation stream against the authoritative planning sources:

- `planning/4 - revised-spec/*`
- `planning/5 - dev-handoff-revised-spec/*`
- `planning/back-end-work-plan.md`
- `planning/lms-interface-plan.md`

It is a living work log for:

- what we need to build
- what we are actively working on
- key contract discoveries and missing backend items
- implementation decisions
- completed work

## Product Direction

Dibble is building the world's most adaptable and functional AI-powered educational LMS. The frontend is a three-layer LMS interface around the Dibble backend:

1. **Learner experience** — a focused, student-safe learning environment for daily work, adaptive lessons, Socratic checks, remediation, review, and progress
2. **Teacher experience** — a classroom workflow for monitoring, intervening, reviewing learner reasoning, and handling exceptions
3. **Staff / operator experience** — an internal workspace for QA, contract inspection, fallback debugging, and workflow validation

See `planning/lms-interface-plan.md` for the full product vision and information architecture.

Guardrail: the frontend renders backend-owned workflow decisions. It does not invent progression logic, mastery gating, or intervention policy locally.

## Current Architecture

The frontend is a React 19 + Vite + TypeScript app with:

- **Role-based routing** via React Router with three shell layouts (`/learn`, `/teacher`, `/staff`)
- **Tailwind CSS** + shadcn-style repo-owned primitives for all styling
- **Typed API adapters** mirroring backend contracts
- **Custom hooks** for data fetching and workflow state (`useLearnerWorkspace`, `useLearnerContracts`, `useGenerationWorkspace`, `useSocraticWorkspace`, `useRemediationWorkspace`, `useTeacherClassroom`)
- **Copy/vocabulary translation layer** (`lib/copy.ts`) preferring backend-provided `display_label` fields with local fallbacks
- **Demo fallback** for offline development (staff mode only by default)
- **16 test files** with Vitest + React Testing Library

## Backend Contracts In Use

Stable frontend-facing read models already integrated:

- `GET /api/learners/{student_id}/summary`
- `GET /api/learners/{student_id}/flow`
- `GET /api/learners/{student_id}/profile`
- `GET /api/learners/{student_id}/progression`
- `GET /api/learners/{student_id}/workspace`
- `GET /api/learners/{student_id}/history/generations`
- `GET /api/learners/{student_id}/history/socratic-sessions`
- `GET /api/learners/{student_id}/history/remediation-sessions`
- `GET /api/learners/{student_id}/intervention-action`
- `POST /api/learners/{student_id}/intervention-action`
- `GET /api/teachers/classrooms`
- `GET /api/teachers/classrooms/{classroom_id}`
- `POST /api/content/generate` with `workflow_summary`
- `POST /api/llm/stream`
- `POST /api/assessments/socratic` with canonical session `summary`
- `GET /api/assessments/socratic/{session_id}`
- `POST /api/remedial/trigger`
- `GET /api/remedial/sessions/{session_id}`
- `POST /api/remedial/sessions/{session_id}/advance`

Contract-hardening in use:

- machine-readable backend error codes via response body `code` and `X-Dibble-Error-Code` header
- learner progression parity across `/progression`, `summary.curriculum_progression`, and teacher classroom learner cards
- `continue_action` and teacher intervention vocabularies as explicit backend-owned sets
- `triage_section` on `TeacherLearnerCard` for backend-owned classroom grouping
- `affective_support` on `LearnerWorkspace` for backend-owned pedagogical messaging
- `display_label` / `stage_display_label` on `LearnerContinueAction` / `LearnerCurriculumProgressionSummary`

## Missing Or Incomplete Items

### Product-level gaps

| Priority | Gap | Impact on frontend |
|---|---|---|
| P0 | No product-level authentication or user identity | Learners and teachers cannot log in; role is selected manually; no session persistence across browser reloads |
| P1 | No assignment model or lifecycle | Cannot frame learning work as teacher-assigned tasks; learner and teacher views lack an assignment container |
| P1 | Teacher reporting is a placeholder | `/teacher/reports` shows "Coming soon"; no class-level progress, trend, or standards mastery views |
| P1 | No pagination on history endpoints | History views hardcoded to `limit=20` with no load-more or infinite scroll |
| P2 | Course-level progression planning is lighter than a true course planner | UI should trust learner `curriculum_progression` and avoid inventing cross-unit sequencing logic |
| P2 | No multimodal artifact payload contract | Content cards should stay extensible without assuming diagrams or interactives yet |
| P2 | No learner-to-learner or teacher-to-learner messaging | No in-app communication channel |
| P2 | No notification / inbox concept | No push or pull notification surface for learners or teachers |

### Residual frontend code gaps

- `lib/copy.ts` still has "TEMPORARY SHIM" comments for `display_rationale` on `TeacherLearnerCard`
- `TeacherView` imports `teacherContractGaps` from sample-data and shows a hardcoded gap list instead of real gap detection
- Affective support component exists but only renders when `workspace.affective_support` is populated
- Some forms expose orchestration inputs (target KCs, LOs, session IDs) that should be hidden in learner mode

## Execution Priorities

### P0: product-level authentication

- Integrate with the existing backend auth contract (`POST /api/auth/token`, bearer tokens, RBAC roles)
- Add a login screen and role-aware redirect
- Persist auth state across browser sessions
- Gate learner/teacher routes behind authenticated identity
- Keep staff mode available for API-key-based access

### P1: learner experience polish

- Hide orchestration inputs (target KCs, LOs, intent selectors) from the learner shell
- Make the Continue Learning flow seamless: learner taps resume, sees content, responds, gets next step — no raw workflow vocabulary
- Add real pagination or infinite scroll to history views
- Polish the Socratic check and remediation session UX for student safety and clarity
- Add loading states, transitions, and error recovery that feel product-grade

### P1: teacher experience depth

- Build a real teacher reporting surface with class-level progress, mastery trends, and per-learner evidence timelines
- Improve classroom detail density so teachers can scan 30 learners efficiently
- Add teacher-to-learner drill-in for artifact review (see the actual generated content, Socratic turns, remediation steps a learner worked through)

### P1: assignment layer (frontend + backend coordination)

- Design a lightweight assignment model that can wrap backend-owned learning sessions
- Record what the frontend needs from the backend in `planning/from-front-to-back-needs.md`
- Start with a presentation layer around learner workspace and progression before adding teacher-launched assignment creation

### P2: polish and expansion

- Continue improving explainability summaries so fewer surfaces depend on raw contract inspection
- Continue making the UI resilient to richer artifact types via `response.artifacts`
- Add offline / connectivity resilience for learner sessions
- Extend test coverage as new surfaces land

## Key Decisions

### Product / Contract

- Treat `current_flow` and workflow/session summaries as the source of truth for UI state.
- Treat `curriculum_progression` as the source of truth for broader learner resource posture.
- Do not reconstruct learner state from audit logs or internal request context.
- Keep teacher-facing decisions explainable with explicit rationale, confidence, and next-step metadata.
- Prefer backend-owned `continue_action`, learner workspace, learner history, learner progression, intervention-action, and classroom contracts over frontend-inferred resume, sequencing, or aggregation flows.
- The frontend prefers backend-provided `display_label` fields; local lookup tables are backwards-compatible fallbacks only.

### Frontend Architecture

- React 19 + Vite + TypeScript with ES modules throughout.
- Role-aware React Router shell: `/learn`, `/teacher`, `/staff`.
- Tailwind CSS + shadcn/ui-style repo-owned primitives.
- Vitest + React Testing Library test suite.
- Typed API adapters mirroring backend contracts.
- Custom hooks for data fetching and workflow state.
- Demo fallback available in staff mode; learner and teacher modes are live-first.
- No additional UI/state libraries unless they clearly reduce complexity.

### Component / Styling Standard

- Tailwind utilities for layout, spacing, theming, and state styling.
- shadcn-style primitives in `frontend/src/components/ui/*`.
- Domain views and workflow components separate from UI primitives.
- CSS variables and Tailwind theme tokens over ad hoc colors.
- No parallel styling systems.

### Tooling / Runtime Standard

- Node 22 pinned via `.nvmrc`, `.node-version`, and Volta metadata.
- GitHub Actions CI runs `test:run`, `lint`, and `build`.

### Code Quality

- Prefer explicit, readable composition over clever indirection.
- Keep view modules focused by screen.
- Keep shared UI primitives small and reusable.
- Keep formatting, payload building, and API access out of top-level view components.
- All major logic belongs in the backend; save frontend requirements for the backend in `from-front-to-back-needs.md`.

## Current Work

### In progress

- reviewing all planning documents and updating work plans to reflect current codebase reality
- identifying the next highest-value product work across frontend and backend

### Next up

1. product-level authentication integration so learners and teachers can log in
2. hide orchestration inputs from the learner shell so Continue Learning feels like a real learning flow
3. build real teacher reporting to replace the placeholder
4. design the assignment model with backend coordination
5. add history pagination
6. keep this work plan and `from-front-to-back-needs.md` updated together

## LMS Interface Progress

### Phase 0: reposition current frontend as staff workspace — DONE

- current tabbed workbench lives under `/staff`
- debug panels, demo toggles, and raw contract inspection are staff-only
- role switcher landing page routes to learner, teacher, or staff shells

### Phase 1: learner shell — DONE (core structure)

Built:
- `LearnerHome` with resume CTA, current lesson card, focus areas, progress bar
- `ContinueLearning` dispatching to generation, Socratic, and remediation flows
- `SocraticCheck` with prompt/response/evaluation UI
- `RemediationSession` with step progression
- `Progress` with mastery tracking and resource state
- `History` with generation, Socratic, and remediation tabs

Remaining:
- hide orchestration inputs from learner forms
- pagination on history
- polish transitions and loading states
- learner-safe error recovery

### Phase 2: teacher shell — DONE (core structure)

Built:
- `Dashboard` with classroom overview cards and attention/blocked/intervention counts
- `ClassroomDetail` with learner cards grouped by backend-owned `triage_section`
- `LearnerDetail` with affective state, progression, intervention proposal
- `InterventionWorkspace` with approve/defer/escalate/select-option controls
- Classroom-to-learner drill-in and return navigation

Remaining:
- teacher reporting surface
- artifact review (see actual generated content a learner received)
- assignment management layer
- richer class-level progress and trend views

### Phase 3: assignments, reporting, and operational completeness — NOT STARTED

- assignment framing layer (frontend + backend coordination needed)
- teacher reporting with trends and standards mastery
- class-level progress review
- role-aware navigation polish

### Phase 4: product depth expansion — FUTURE

- richer artifacts when backend ships multimodal support
- course maps and unit navigation
- messaging and notifications
- family portal
- standards mastery views

## Completed

### LMS interface implementation (PR #3, merged to main)

- built role-based React Router skeleton with three shell layouts and role switcher
- built complete learner shell with home, continue-learning, Socratic, remediation, progress, and history views
- built complete teacher shell with dashboard, classroom detail, learner detail, and intervention workspace
- added vocabulary translation layer (`lib/copy.ts`) and shell layout primitives
- added content block registry, affective support, and streaming content components
- integrated shared content components into learner and teacher views
- added component tests for content blocks, affective support, streaming, and role switcher
- added tests for triage logic and vocabulary translation
- replaced frontend pedagogical shims with backend-owned `triage_section`, `affective_support`, and `display_label` fields
- documented backend need for generation quality metadata on history entries

### Contract integration and workbench phase (earlier PRs, merged to main)

- created React + Vite frontend workspace under `frontend/`
- added Tailwind CSS, shadcn-style config, UI dependencies, theme tokens, aliases, and shared UI primitives
- added typed API models and demo data scaffolding for all current contracts
- refactored the app into typed API helpers, domain views, formatters, and shared primitives
- added baseline test stack with Vitest, jsdom, and React Testing Library
- extracted persistent config, learner workspace, generation, Socratic, and remediation logic into dedicated hooks
- reduced `App.tsx` to a composition shell
- migrated all workflow views to shared UI primitives
- gated raw contract payload panels behind an explicit debug setting
- extended frontend to support learner workspace, learner history, intervention contracts, classroom, and progression
- added triage-oriented classroom queue with backend-owned section grouping
- added classroom-to-teacher drill-in and return navigation
- added shared formatting and panel-state helpers for product-facing language
- added shell-level workspace status surface for connectivity posture
- completed CSS cleanup onto Tailwind utilities
- aligned teacher intervention with backend-recorded latest decision state
- added repo-level GitHub Actions CI for frontend workspace
- completed live-contract smoke pass against backend stack

## Notes For Future Updates

When work changes, update:

1. `Current Work`
2. `Missing Or Incomplete Items`
3. `Key Decisions`
4. `Completed`
5. `LMS Interface Progress`

# Coding quality bar:
- write code like this backend will be lived in for a long time
- optimize for modularity, maintainability, and elegant composition
- keep functions and modules crisp
- avoid cleverness that obscures intent
- prefer explicit, boring, trustworthy logic over fragile abstraction
- leave touched code better than you found it
- all major logic should be in the backend, save frontend requirements for the backend in from-front-to-back-needs.md
