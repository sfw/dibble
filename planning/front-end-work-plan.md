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
- **27 test files** with Vitest + React Testing Library

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
| ~~P0~~ | ~~No product-level authentication or user identity~~ | **RESOLVED** — backend supports `learner` and `teacher` roles with entity bindings. Frontend now has login screen (`/login`), `useAuth` hook with bearer token persistence and refresh, `AuthGuard` gating `/learn` and `/teacher` routes, role-aware redirect, logout from shell headers, and `AuthContext` for app-wide auth state. |
| ~~P1~~ | ~~No assignment model or lifecycle~~ | **RESOLVED** — backend has a first-class `Assignment` entity. Frontend now has learner assignment view (`/learn/assignments`) with active/past grouping, start action, and pagination; teacher assignment view (`/teacher/assignments`) with create form, cancel action, and pagination; `useAssignments` hooks for both roles; nav links in both shells; and tests. |
| ~~P1~~ | ~~Teacher reporting is a placeholder~~ | **RESOLVED** — `/teacher/reports` now shows a real reporting surface with cross-classroom summary metrics, per-classroom progress cards with stacked distribution bars, per-classroom deep-dive sections for stage distribution, engagement/frustration overview, activity totals, and attention levels, per-learner drill-down table with sortable columns and attention reasons, expandable attention-level drill-down, and classroom selector for deep-dive switching. Reports nav link added to teacher shell. Tests cover all report sections. |
| ~~P1~~ | ~~No pagination on history endpoints~~ | **RESOLVED** — backend returns `{ items, offset, limit, has_more }` paginated responses. Frontend `useLearnerContracts` hook now tracks pagination state and exposes `loadMoreHistory`. History view shows a "Load more" button when more entries are available. |
| P2 | Course-level progression planning is lighter than a true course planner | UI should trust learner `curriculum_progression` and avoid inventing cross-unit sequencing logic |
| P2 | No multimodal artifact payload contract | Content cards should stay extensible without assuming diagrams or interactives yet |
| P2 | No learner-to-learner or teacher-to-learner messaging | No in-app communication channel |
| P2 | No notification / inbox concept | No push or pull notification surface for learners or teachers |

### Residual frontend code gaps

- ~~`lib/copy.ts` still has "TEMPORARY SHIM" comments for `display_rationale` on `TeacherLearnerCard`~~ — **RESOLVED**: shim comment updated; callers now pass backend `display_label` and `stage_display_label` where available
- ~~`TeacherView` imports `teacherContractGaps` from sample-data and shows a hardcoded gap list instead of real gap detection~~ — **RESOLVED**: gaps updated to reflect current P2-only status; section renamed to "Future expansion seams"
- `lib/triage.ts` `describeLearnerRationale` still selects among multiple rationale sources; a backend `display_rationale` field on `TeacherLearnerCard` would simplify this
- Affective support component exists but only renders when `workspace.affective_support` is populated
- ~~Some forms expose orchestration inputs (target KCs, LOs, session IDs) that should be hidden in learner mode~~ — **RESOLVED**: learner views already keep all orchestration inputs (target KCs, LOs, intent selectors, session IDs) in internal form state; none are rendered in the learner shell UI

## Execution Priorities

### P0: product-level authentication

- Integrate with the existing backend auth contract (`POST /api/auth/token`, bearer tokens, RBAC roles)
- Add a login screen and role-aware redirect
- Persist auth state across browser sessions
- Gate learner/teacher routes behind authenticated identity
- Keep staff mode available for API-key-based access

### P1: learner experience polish

- ~~Hide orchestration inputs from the learner shell~~ — **DONE**: already internal-only
- Make the Continue Learning flow seamless: learner taps resume, sees content, responds, gets next step — no raw workflow vocabulary
- ~~Add real pagination or infinite scroll to history views~~ — **DONE**: load-more pagination
- ~~Add type filtering to history views~~ — **DONE**: All/Lessons/Checks/Practice filter tabs with counts
- ~~Enrich Progress view with resource breakdown~~ — **DONE**: all resources grouped by state with mastery bars and blocker rationale
- Polish the Socratic check and remediation session UX for student safety and clarity
- Add loading states, transitions, and error recovery that feel product-grade

### P1: teacher experience depth

- ~~Build a real teacher reporting surface with class-level progress, mastery trends, and per-learner evidence timelines~~ — **DONE**: `/teacher/reports` with cross-classroom summaries, per-classroom analytics, per-learner mastery heatmap, and learner drill-down table
- Improve classroom detail density so teachers can scan 30 learners efficiently
- ~~Add teacher-to-learner drill-in for artifact review~~ — **DONE**: `LearnerDetail` evidence timeline with expandable entries and artifact review panel
- Add trend lines to reports when backend exposes historical snapshots

### P1: assignment layer (frontend + backend coordination) — DONE

- ~~Design a lightweight assignment model~~ — backend owns a first-class `Assignment` entity
- ~~Learner view~~ — `/learn/assignments` shows assigned work with start action, due dates, and pagination
- ~~Teacher view~~ — `/teacher/assignments` shows all assignments with create form, cancel, and pagination
- ~~Hooks~~ — `useLearnerAssignments` and `useTeacherAssignments` with full CRUD and pagination

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

- learner experience polish: continued micro-interaction refinement
- teacher reporting depth: trend lines (blocked on backend historical snapshots)

### Next up

1. add trend lines to teacher reports when backend exposes historical snapshots
2. continue refining learner flow micro-interactions and transitions
3. keep this work plan and `from-front-to-back-needs.md` updated together

### Recently completed

- learner Progress: "All resources" section grouping curriculum resources by state (mastered count summary, current focus highlighted, ready to start, blocked with lock icon and rationale tooltip), with mastery bars and stage badges per resource
- learner History: type filter tabs (All/Lessons/Checks/Practice) with count badges, type-consistent color coding (blue/violet/amber), and filtered empty states
- teacher Reports: per-learner mastery heatmap strip between mastery banner and analytics grid — color-coded cells sorted low-to-high, hover tooltips with student ID and mastery %, click-through to learner detail, and color legend
- `Progress.test.tsx` test suite (11 tests) covering resource groups, mastered count, blocked rationale, loading, and error states
- `History.test.tsx` test suite (10 tests) covering filter tabs, counts, type filtering, filtered empty states, and load more
- Reports tests expanded to cover mastery heatmap strip (4 new tests, 23 total)
- teacher `LearnerDetail` evidence timeline: unified chronological view interleaving generation, Socratic, and remediation history entries with expandable detail rows showing flow type, status, phase, progression, steering, evidence strength, and rationale; load-more pagination via existing `useLearnerContracts` hook
- teacher `LearnerDetail` artifact review panel: click any generation in the timeline to load and display the actual content blocks via `GET /api/content/{generation_id}`, with quality metadata, safety notes, and all block types rendered through the existing `ContentBlock` component
- `getGeneratedContent` API function for fetching individual generations by ID
- `LearnerDetail.test.tsx` test suite covering header, overview, current activity, evidence timeline, and back navigation
- learner flow transitions: staggered fade-in-up animations on content blocks, streaming indicators, progress bars, home cards, Socratic conversation thread, remediation steps, and confidence picker for a polished product-grade feel
- learner SocraticCheck: submission success feedback ("Answer received" badge), auto-scroll to bottom of conversation thread, hover/scale micro-interactions on confidence picker
- learner RemediationSession: enhanced step progress with numbered circles, check marks on completed steps, connected track lines between steps, animated phase labels
- learner ContinueLearning: animated progress bar fill, smoother loading indicator with descriptive subtext
- learner LearnerHome: staggered entrance animations on greeting, lesson card, focus section, and progress section
- StreamingContent: per-block fade-in animation with stagger delay, richer streaming indicator with "usually takes a few seconds" subtext
- CSS animation utilities: `animate-fade-in-up`, `animate-fade-in`, `animate-scale-in`, `animate-progress-fill`, `animate-pulse-gentle` added to `index.css`
- teacher Reports: class average mastery banner with on-track/at-risk counts, mastery distribution histogram (4-bucket bar chart), resource mastery breakdown showing weakest-first resources with per-resource mastery bars and mastered/total counts
- Reports tests expanded to cover mastery banner, mastery distribution, and resource mastery sections (19 tests total)
- wired backend `display_label` and `stage_display_label` through to `copy.ts` callers in LearnerHome, ContinueLearning, and Progress views
- added animated loading spinner to ContinueLearning initial load state
- added loading indicator to RemediationSession when content is loading between steps
- added "Thinking..." indicator to SocraticCheck while waiting for response
- updated `teacherContractGaps` sample data to reflect current P2-only status (all P0/P1 items resolved)
- renamed TeacherView "Remaining backend gaps" section to "Future expansion seams"
- updated `copy.ts` shim comment to reflect that backend now provides display_label fields
- updated `triage.ts` rationale selection comment to be descriptive rather than labeled as temporary
- fixed pre-existing Unicode curly-quote issue in sample-data.ts
- shared `Skeleton`, `CardSkeleton`, `PageSkeleton` and `ErrorBanner` UI primitives for consistent loading/error states across all views
- learner home: loading skeleton during initial data fetch, error banner for context errors
- learner progress: loading skeleton during initial fetch, error banner
- learner continue-learning: error banner for generation failures
- learner history: loading skeleton during initial history fetch, error banner
- learner remediation: upgraded error display from small red text to visible `ErrorBanner`
- learner Socratic check: upgraded error display to `ErrorBanner`
- teacher reports: loading skeleton, error banner, classroom selector for deep-dive switching, per-learner drill-down table with sortable columns (stage, mastery, engagement, frustration, attention), attention reasons display with human-readable labels, expandable attention-level drill-down showing which learners drive each level with their attention reasons, learner "View" links for direct navigation to learner detail
- tests for `Skeleton`, `ErrorBanner`, and expanded Reports coverage (15 tests including sorting, drill-down, attention reasons, classroom selector)
- teacher reports view (`/teacher/reports`) with cross-classroom summary, per-classroom progress cards, stage distribution, engagement/frustration overview, activity totals, and attention levels — with Reports nav link in teacher shell
- confirmed learner shell already hides all orchestration inputs; no UI changes needed
- learner assignment view (`/learn/assignments`) with active/past grouping, start action, due dates, and load-more pagination
- teacher assignment view (`/teacher/assignments`) with create form, student selection, cancel action, and load-more pagination
- `useLearnerAssignments` and `useTeacherAssignments` hooks with fetch, create, status update, and pagination
- assignment nav links added to both learner and teacher shell headers
- tests for assignment hooks and both assignment views
- login screen at `/login` with API key authentication, bearer token issuance, and role-aware redirect
- `useAuth` hook managing auth state, bearer token persistence in localStorage, token refresh, and logout
- `AuthContext` provider wrapping the app for global auth state access
- `AuthGuard` component gating `/learn` and `/teacher` routes behind authentication with role checks
- `RoleSwitcher` auto-redirects authenticated users to their role-appropriate shell
- learner and teacher shells now use bearer tokens from auth state instead of API key config
- shell headers show display name and logout button for authenticated users
- history view now shows "Load more" button when the backend reports more entries available
- `useLearnerContracts` hook tracks `hasMoreHistory` / `loadingMore` and exposes `loadMoreHistory`

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
- `Progress` with mastery tracking, resource state, and full resource breakdown by state (mastered, current, ready, blocked)
- `History` with generation, Socratic, and remediation timeline plus type filter tabs with counts

Remaining:
- ~~hide orchestration inputs from learner forms~~ — **DONE**: all orchestration inputs already internal-only
- polish transitions and loading states
- learner-safe error recovery

### Phase 2: teacher shell — DONE (core structure)

Built:
- `Dashboard` with classroom overview cards and attention/blocked/intervention counts
- `ClassroomDetail` with learner cards grouped by backend-owned `triage_section`
- `LearnerDetail` with affective state, progression, intervention proposal, unified evidence timeline, and artifact review panel
- `InterventionWorkspace` with approve/defer/escalate/select-option controls
- Classroom-to-learner drill-in and return navigation

Remaining:
- ~~teacher reporting surface~~ — **DONE**: `/teacher/reports` with cross-classroom and per-classroom reporting plus per-learner mastery heatmap
- ~~artifact review~~ — **DONE**: `LearnerDetail` now has a unified evidence timeline with expandable detail and click-to-review generated content via `GET /api/content/{generation_id}`
- ~~assignment management layer~~ — **DONE**: teacher and learner assignment views
- trend lines when backend exposes historical snapshots

### Phase 3: assignments, reporting, and operational completeness — IN PROGRESS

- ~~assignment framing layer~~ — **DONE**: learner and teacher assignment views with create, start, cancel, and pagination
- ~~teacher reporting placeholder~~ — **DONE**: `/teacher/reports` now shows class-level progress, learner distribution, engagement/frustration, activity totals, and attention levels across classrooms
- ~~hide orchestration inputs from learner shell~~ — **DONE**: confirmed all orchestration inputs are already internal-only; no UI exposure
- ~~teacher reporting: per-learner mastery heatmap~~ — **DONE**: color-coded mastery strip with hover tooltips and click-through
- ~~learner progress: resource breakdown~~ — **DONE**: all resources grouped by state with mastery bars and blocker rationale
- ~~learner history: type filtering~~ — **DONE**: All/Lessons/Checks/Practice tabs with counts
- teacher reporting depth: trend lines (blocked on backend historical snapshots)
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

### Authentication and history pagination

- added login screen with API key input, role-aware redirect, and advanced server URL setting
- added `useAuth` hook with bearer token lifecycle: login, logout, token persistence, and token refresh
- added `AuthContext` and `AuthGuard` for app-wide auth state and route protection
- updated `RoleSwitcher` to auto-redirect authenticated users to their role shell
- updated `LearnerShell` and `TeacherShell` to use bearer tokens from auth context with display name and logout
- added load-more pagination to history view via `useLearnerContracts` hook pagination tracking
- added `Root` component wrapping `RouterProvider` with `AuthContext.Provider`
- added tests for `useAuth` hook and `Login` page
- updated `RoleSwitcher` tests for auth context

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
