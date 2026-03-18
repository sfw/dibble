# Frontend Work Plan

Last updated: 2026-03-18

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

## Leadership-Aligned Frontend Rubric

Frontend planning should follow the backend leadership lens rather than drifting into feature accumulation.

For every meaningful frontend item, answer:

| Field | What it must say |
|---|---|
| Type | `protect_differentiator`, `surface_world_class_gap`, `contract_hardening`, or `activation_readiness` |
| Leadership anchor | Which backend differentiator this preserves or which named world-class gap it helps expose honestly |
| Backend owner | Which backend contract, field, or decision remains the source of truth |
| UI value | What learner, teacher, or operator outcome improves if this lands |
| Stop rule | When the frontend has done enough around the current backend capability |
| Frontend boundary | What the UI must not infer, score, or sequence locally |

Planning discipline:

1. protect backend-owned adaptation, inspectable progression, and teacher-aligned control rather than recreating them in UI code
2. surface uncertainty and limitation honestly when the backend is still heuristic or locally scoped
3. only add course maps, richer analytics, multimodal views, messaging, or notifications when the backend owns the semantics those surfaces imply
4. treat cross-surface drift in stage, rationale, continue-action, or mastery framing as a bug, not as an invitation for frontend reconciliation logic

## Current Architecture

The frontend is a React 19 + Vite + TypeScript app with:

- **Role-based routing** via React Router with three shell layouts (`/learn`, `/teacher`, `/staff`)
- **Tailwind CSS** + shadcn-style repo-owned primitives for all styling
- **Typed API adapters** mirroring backend contracts
- **Custom hooks** for data fetching and workflow state (`useLearnerWorkspace`, `useLearnerContracts`, `useGenerationWorkspace`, `useSocraticWorkspace`, `useRemediationWorkspace`, `useTeacherClassroom`)
- **Copy/vocabulary translation layer** (`lib/copy.ts`) preferring backend-provided `display_label` fields with local fallbacks
- **Demo fallback** for offline development (staff mode only by default)
- **30 test files** with 218 tests via Vitest + React Testing Library

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
| P1 | Cross-surface rationale and stage parity can still drift in presentation | Treat parity drift as a product bug; prefer one backend rationale path over frontend synthesis |
| P1 | Mastery-loop evidence still needs clearer learner and teacher rendering | Surface backend evidence snapshots, blockers, mastery history, and next-step framing without inventing trust scores locally |
| P2 | Course-level progression planning is lighter than a true course planner | Do not imply stronger sequencing authority with course maps or unit navigation before backend ownership exists |
| P2 | Multimodal support is envelope-first, not capability-complete | Keep `response.artifacts` rendering extensible without assuming diagrams, simulations, or interactives already exist |
| P2 | Teacher analytics are workflow-first rather than instructional-intelligence-first | Expand reporting only when backend-owned analytics deepen beyond current classroom and mastery-trend surfaces |
| P2 | Messaging and notifications remain product-expansion seams | No inbox, comments, or push surfaces until backend ownership is explicit |

### Residual frontend code gaps

- ~~`lib/copy.ts` still has "TEMPORARY SHIM" comments for `display_rationale` on `TeacherLearnerCard`~~ — **RESOLVED**: shim comment updated; callers now pass backend `display_label` and `stage_display_label` where available
- ~~`TeacherView` imports `teacherContractGaps` from sample-data and shows a hardcoded gap list instead of real gap detection~~ — **RESOLVED**: gaps updated to reflect current P2-only status; section renamed to "Future expansion seams"
- ~~`lib/triage.ts` `describeLearnerRationale` still selects among multiple rationale sources; a backend `display_rationale` field on `TeacherLearnerCard` would simplify this~~ — **RESOLVED**: backend now provides `display_rationale` on `TeacherLearnerCard`; frontend prefers it with backwards-compatible fallback
- Affective support component exists but only renders when `workspace.affective_support` is populated
- ~~Some forms expose orchestration inputs (target KCs, LOs, session IDs) that should be hidden in learner mode~~ — **RESOLVED**: learner views already keep all orchestration inputs (target KCs, LOs, intent selectors, session IDs) in internal form state; none are rendered in the learner shell UI

## Execution Priorities

### P1: protect backend-owned differentiation

- keep learner, teacher, and staff surfaces aligned to the same backend-owned next-step, stage, and rationale semantics
- reduce remaining frontend rationale composition where a canonical backend field can replace it
- keep learner interactions polished enough that backend-owned adaptation feels coherent rather than fragile
- regression-test parity across summary, flow, workspace, history, intervention, and classroom drill-in surfaces

### P1: surface world-class gaps honestly

- present mastery-loop evidence, blocker rationale, mastery trends, and affective support in ways that make current backend confidence and limits legible
- avoid course or unit navigation patterns that imply stronger sequencing authority than `curriculum_progression` actually owns
- keep teacher reports useful for workflow and evidence review without overstating instructional-intelligence depth
- keep `response.artifacts` rendering extensible so richer capabilities can land without frontend churn

### P2: activation-based expansion

- add course maps and broader navigation only when backend course-planning authority exists
- add richer multimodal views only when backend artifact variants exist beyond `text`
- add richer teacher intelligence, messaging, notifications, or family-facing surfaces only when backend ownership and product need are explicit
- continue offline / connectivity resilience and test coverage as enabling work

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

(none)

### Next up

1. keep this work plan and `from-front-to-back-needs.md` updated together with explicit leadership anchors
2. reduce remaining frontend-owned rationale selection where the backend can supply a canonical display field
3. keep parity and artifact-extensibility regression coverage strong as backend quality work continues

### Recently completed

- learner Progress: mastery quality badges — `ResourceCard` now renders "Needs independent practice" (amber) and "Unstable mastery" (orange) badges when the backend `mastery_quality` field is `support_dependent` or `fragile`, with rationale text shown alongside the badge; 2 new tests cover both badge variants
- teacher classroom detail density: collapsible triage sections with learner count badges (on-track collapsed by default), compact card mode toggle (grid/list), and filter bar with student ID search, attention level dropdown, and intervention toggle — all three features with tests
- `CollapsibleTriageSection` component with chevron disclosure, smooth CSS grid-rows animation, and `aria-expanded` accessibility
- `CompactLearnerCard` component with dense single-row layout, expandable detail on click, and reduced padding
- `ClassroomFilterBar` component with text search, Radix Select for attention level, intervention toggle, layout mode switch, and "N of M learners" count
- ClassroomView tests expanded to cover collapsible sections, filter bar, and compact layout
- learner SocraticCheck: added accessibility (aria radiogroup on confidence picker, aria-checked/aria-label on each option), form validation (submit disabled when empty), error retry button
- learner RemediationSession: added form validation (continue disabled when response empty), empty state for sessions with no steps, error retry button, accessibility (aria-current on active step, aria-label on step indicators)
- learner ContinueLearning: added error retry button
- `SocraticCheck.test.tsx` test suite (12 tests) covering heading, conversation history, confidence picker radiogroup, submit validation, loading state, error retry, affective support, hints disclosure
- `RemediationSession.test.tsx` test suite (14 tests) covering heading, step progress, phase label, content blocks, response validation, loading, error retry, empty state, affective support, rationale disclosure
- `ContinueLearning.test.tsx` test suite (11 tests) covering heading, content type, content blocks, progress rail, continue CTA, empty state, loading, error retry, streaming disabled state
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
- teacher Reports: mastery trend line chart (SVG line, no external chart library) showing classroom average mastery over 30 days with date labels and percentage gridlines, per-learner mastery change strip with improving/stable/declining color coding and delta percentages, per-learner mastery deltas in drill-down table rows — all fetched from `GET /api/teachers/classrooms/{classroom_id}/mastery-trends`
- Reports tests expanded to cover trend chart SVG, not-enough-data fallback, loading state, per-learner trend strip with delta values, trend legend, and drill-down table deltas (30 tests total)
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
- ~~polish transitions and loading states~~ — **DONE**: staggered animations, streaming indicators, progress bars
- ~~learner-safe error recovery~~ — **DONE**: retry buttons on SocraticCheck, RemediationSession, ContinueLearning; form validation preventing empty submissions; empty state handling

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
- ~~trend lines~~ — **DONE**: integrated backend mastery-trends endpoint into Reports with SVG trend line, per-learner delta strip, and drill-down table deltas

### Phase 3: assignments, reporting, and operational completeness — DONE / maintenance

- ~~assignment framing layer~~ — **DONE**: learner and teacher assignment views with create, start, cancel, and pagination
- ~~teacher reporting placeholder~~ — **DONE**: `/teacher/reports` now shows class-level progress, learner distribution, engagement/frustration, activity totals, and attention levels across classrooms
- ~~hide orchestration inputs from learner shell~~ — **DONE**: confirmed all orchestration inputs are already internal-only; no UI exposure
- ~~teacher reporting: per-learner mastery heatmap~~ — **DONE**: color-coded mastery strip with hover tooltips and click-through
- ~~learner progress: resource breakdown~~ — **DONE**: all resources grouped by state with mastery bars and blocker rationale
- ~~learner history: type filtering~~ — **DONE**: All/Lessons/Checks/Practice tabs with counts
- ~~teacher reporting depth: trend lines~~ — **DONE**: SVG trend line chart, per-learner mastery change strip, and drill-down table deltas
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
