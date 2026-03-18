# Frontend Work Plan

Last updated: 2026-03-17

## Purpose

This document tracks the frontend implementation stream against the authoritative planning sources:

- `planning/4 - revised-spec/*`
- `planning/5 - dev-handoff-revised-spec/*`
- `planning/current-backend-gap-analysis.md`

It is a living work log for:

- what we need to build
- what we are actively working on
- key contract discoveries and missing backend items
- implementation decisions
- completed work

## Frontend Scope From Revised Spec

Primary surfaces to implement first:

1. learner summary and `current_flow`
2. generated content workflow summaries
3. Socratic session summaries
4. remediation session summaries
5. teacher-facing explainability and intervention surfaces

Guardrail:

- the frontend should render backend-owned workflow decisions, not invent progression logic locally

## Backend Contract Discoveries

Stable frontend-facing read models already available:

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

Recent contract-hardening additions:

- machine-readable backend error codes are now available in both the response body `code` field and the `X-Dibble-Error-Code` header
- learner progression parity is now protected across `/progression`, `summary.curriculum_progression`, and teacher classroom learner cards
- `continue_action` and teacher intervention vocabularies are now explicit backend-owned sets rather than loose cross-surface strings

## Missing Or Incomplete Items

These are the highest-signal frontend gaps discovered so far:

| Priority | Gap | Impact on frontend |
|---|---|---|
| P1 | Course-level progression planning is still intentionally lighter than a true course planner | UI should trust learner `curriculum_progression` and avoid inventing cross-unit sequencing logic |
| P2 | No multimodal artifact payload contract | UI should keep content cards extensible without assuming diagrams or interactives yet |
| P2 | Teacher-safe analytics are classroom-card oriented, not dashboard-grade | Teacher views should build on classroom summaries and learner cards rather than admin telemetry |

## Execution Priorities

### P0: tighten the frontend foundation

- Replace remaining raw form controls in generation, Socratic, and remediation views with shared UI primitives.
- Reduce dependence on the legacy app-shell CSS where it is still carrying screen-level styling.
- Keep workflow state and side effects in feature-specific hooks rather than letting them drift back into `frontend/src/App.tsx`.

### P1: grow behavioral coverage

- Add tests for learner overview rendering.
- Add tests for generation interactions and stream fallback behavior.
- Add tests for Socratic run/load flows.
- Add tests for remediation trigger/reload/advance flows.

### P1: formalize backend asks from the frontend stream

- Keep a dedicated `planning/from-front-to-back-needs.md` document updated with frontend-discovered contract needs.
- Keep that document opinionated and current enough to serve as backend marching orders, not just as a historical notes dump.
- Record remaining multimodal, analytics, and longer-horizon progression gaps there rather than letting them drift across chat and code comments.

### P1: implement newly available backend-owned contracts

- Add learner workspace resume and continue flows using `GET /api/learners/{student_id}/workspace`.
- Add learner-scoped generation, Socratic-session, and remediation-session history surfaces.
- Replace advisory-only teacher intervention messaging with the real intervention-action contract and write path.
- Add learner curriculum progression surfaces using `GET /api/learners/{student_id}/progression` and `summary.curriculum_progression`.
- Add teacher classroom surfaces using `GET /api/teachers/classrooms` and `GET /api/teachers/classrooms/{classroom_id}`.

### P2: polish higher-level product surfaces

- Improve teacher-facing intervention language now that backend-owned teacher decisions and selectable options exist.
- Replace raw JSON-first payload inspection with more curated explainability summaries where possible.
- Continue making the UI resilient to richer artifact types without assuming they already exist.

## Key Decisions

### Product / Contract

- Treat `current_flow` and workflow/session summaries as the source of truth for UI state.
- Treat `curriculum_progression` as the source of truth for broader learner resource posture.
- Do not reconstruct learner state from audit logs or internal request context unless there is no alternative.
- Keep teacher-facing decisions explainable with explicit rationale, confidence, and next-step metadata.
- Prefer backend-owned `continue_action`, learner workspace, learner history, learner progression, intervention-action, and classroom contracts over frontend-inferred resume, sequencing, or aggregation flows.

### Frontend Architecture

- Use React + Vite + TypeScript as the frontend workspace.
- Standardize future frontend work on Tailwind CSS + shadcn/ui-style repo-owned primitives.
- Treat the frontend workspace as an ES module app and keep new tooling/config compatible with native `import` / `export`.
- Maintain a Vitest + React Testing Library test suite and grow it as frontend behavior expands.
- Favor small modules and explicit props over heavy abstraction.
- Use typed API adapters and typed read models that mirror the backend contracts.
- Avoid additional UI/state libraries unless they clearly reduce complexity.
- Keep a demo fallback path so UI development can continue when the backend is unavailable, while keeping live API integration first-class.

### Component / Styling Standard

- Use Tailwind utilities for layout, spacing, theming, and state styling.
- Use shadcn-style primitives in `frontend/src/components/ui/*` as the shared component foundation.
- Keep domain views and workflow components separate from UI primitives.
- Prefer CSS variables and Tailwind theme tokens over ad hoc colors in component files.
- Avoid introducing parallel styling systems for new work unless there is a strong reason.

### Tooling / Runtime Standard

- Pin the frontend to Node 22 for local development and verification.
- Provide Node version pins in repo files that work across multiple version managers and local environments.
- Record runtime expectations in repo files so module-format failures are easier to diagnose.
- Prefer fixing environment/tooling mismatches before rewriting working ESM code to accommodate an older runtime.

### Code Quality

- Prefer explicit, readable composition over clever indirection.
- Keep view modules focused by screen.
- Keep shared UI primitives small and reusable.
- Keep formatting, payload building, and API access out of top-level view components.

## Current Work

### In progress

- keep frontend-originated backend needs captured in a dedicated planning document
- continue reducing legacy app-shell CSS where layout patterns are still duplicated
- continue tightening workflow view integration now that generation, Socratic, and remediation screens can hydrate from backend-owned workspace context
- keep evolving the new learner progression and classroom surfaces toward more curated teacher workflows, especially around teacher triage and learner handoff continuity
- keep reviewing new backend progression changes against the frontend contract stance so the UI continues trusting backend-owned repair, target, bridge, and transfer decisions
- keep reviewing new backend semantic-hardening changes against the frontend contract stance so frontend feedback stays focused on parity drift and rationale trust rather than new schema asks
- keep replacing enum-shaped or debug-shaped frontend copy with more curated explainability summaries built from existing backend contracts
- keep making live-vs-demo fallback posture explicit in the shell so contract connectivity changes are visible without opening debug panels or being overwritten by unrelated live refreshes
- keep consolidating shell and screen layout CSS onto shared primitives where it clearly removes one-off legacy classes instead of adding another styling layer
- keep `App.css` focused on visual primitives and view-specific card treatment instead of generic page composition helpers
- keep tightening teacher intervention continuity and routing coverage so backend-selected options, resume actions, and classroom drill-in behavior stay trustworthy as the product surface grows

### Next up

1. start a merge-readiness pass for bringing `frontend/` onto `main`, with special focus on repo-level CI coverage, root-level docs, PR scoping, and final verification expectations
2. extend fallback/error-path coverage into no-demo-fallback branches plus generation, Socratic, and remediation action failures after a live-connected boot
3. curate more explainability-first summaries so fewer product surfaces depend on raw debug payload inspection
4. keep extending teacher and classroom flows without inventing frontend-owned sequencing or intervention policy
5. keep this work plan and `from-front-to-back-needs.md` updated together

## Merge Readiness

Current read: the frontend branch is getting close to mergeable as product code, but it still needs a small repo-integration pass before it should land on `main`.

Highest-value merge-prep tasks:

1. add repo-level CI coverage for the frontend so `npm run test:run`, `npm run lint`, and `npm run build` run in automation alongside the existing backend checks
2. add a short top-level README pointer for the `frontend/` workspace so the main branch documents how the frontend fits into the repo and how to run it locally
3. keep the merge PR scoped to the frontend workspace plus intentionally synced planning/docs work; do not drag unrelated planning experiments into the merge
4. do one final rebase onto the latest `main` immediately before merge and rerun backend plus frontend verification from a clean tree
5. do a short live-contract smoke pass against the latest backend-owned learner workspace, history, progression, intervention, and classroom surfaces before merge so the branch lands against the current semantic contract set

## Completed

- reviewed the authoritative planning packages before frontend implementation
- compared revised frontend needs to the current backend implementation
- identified the main contract gaps for teacher and workflow surfaces
- created a new React + Vite frontend workspace under `frontend/`
- installed the initial frontend toolchain dependencies
- aligned the frontend toolchain onto a Tailwind-compatible Vite version
- added Tailwind CSS, shadcn-style config, UI dependencies, theme tokens, aliases, and shared UI primitives
- added typed API models and demo data scaffolding for current contracts
- refactored the app into typed API helpers, domain views, formatters, and shared primitives
- verified the frontend passes lint and production build with Node 22
- documented the frontend runtime and ES module standard in the workspace
- added repo-level Node version pins for testing and local development across `.nvmrc`, `.node-version`, and Volta metadata
- confirmed the current frontend codebase is already ES module-based; remaining module errors are more likely runtime/tooling mismatches than app source format problems
- added a baseline frontend test stack with Vitest, jsdom, and React Testing Library
- added initial coverage for form helpers, API contract helpers, SSE stream parsing, and the teacher explainability surface
- identified that `frontend/src/App.tsx` and the remaining raw form views are the main maintainability hotspots in the current frontend codebase
- identified that the backend-needs planning note referenced by the frontend plan did not yet exist and should be maintained explicitly
- extracted persistent config, learner workspace, generation, Socratic, and remediation logic into dedicated hooks
- reduced `frontend/src/App.tsx` to a smaller composition shell with app-level components for workspace settings and learner selection
- added shared frontend form primitives plus repo-owned `Label` and `Select` UI components for screen-level workflow forms
- migrated generation, Socratic, and remediation views away from raw HTML controls and button-specific CSS classes
- removed unused legacy form/button CSS now that workflow screens rely on shared UI primitives
- expanded the screen test suite to cover overview, generation, Socratic, and remediation views
- verified the frontend still passes tests, lint, and production build after the workflow-form refactor
- gated raw contract payload panels behind an explicit debug setting instead of presenting them as always-on product UI
- replaced the remaining raw workspace toggle with a shared `Switch` primitive
- removed unused frontend assets and dead tab-era styling leftovers
- rebased the frontend branch onto a newer `main` that now includes learner workspace, learner history, continue-action, normalized API error, and teacher intervention contracts
- extended the frontend read models and API adapters to support learner workspace, learner history, normalized intervention contracts, and teacher intervention writes
- refactored learner loading to use the backend-owned workspace payload as the source for summary and current-flow state
- added a dedicated learner-contracts hook for generation history, Socratic history, remediation history, and teacher intervention state
- upgraded the overview screen to show backend-owned workspace resume state plus learner history across generated, Socratic, and remediation workflows
- replaced the advisory-only teacher surface with a real intervention contract view that supports backend decision recording
- expanded tests to cover the new workspace/intervention API adapters and the upgraded overview and teacher screens
- verified the frontend passes tests, lint, and production build after integrating the newer backend contracts
- rebased again onto a newer `main` that now also includes learner curriculum progression and teacher classroom read models
- rebased onto a newer `main` that also hardens machine-readable error bodies, progression parity, and workflow-facing contract vocabularies
- extended the frontend contract layer with typed learner progression and teacher classroom adapters plus demo data coverage
- surfaced learner curriculum progression in the overview and teacher detail screens
- added an initial classroom workspace backed by the teacher classroom overview/detail contracts
- expanded tests to cover learner progression adapters, teacher classroom adapters, and the new classroom screen
- verified the frontend still passes tests, lint, and production build after the progression/classroom integration pass
- aligned frontend types, demo data, error handling, and teacher/continue-action behavior with the hardened backend workflow vocabularies
- added regression coverage for machine-readable backend error codes and idle-workspace resume routing
- fixed classroom-to-learner drill-in so learner contract loading can target the selected learner explicitly
- verified the frontend still passes tests, lint, and production build after the contract-alignment pass
- hydrated generation, Socratic, and remediation workspace forms from the backend-owned learner workspace contract
- reused workspace-owned generated content and session state so the workflow tabs reopen with learner-specific context instead of static defaults
- expanded form-helper tests to cover workspace-driven hydration
- verified the frontend still passes tests, lint, and production build after the workspace-hydration pass
- rebased the frontend worktree onto the latest `origin/main` before starting the next substantial slice
- refined the classroom workspace into a triage-oriented queue that separates teacher-action-ready, blocked, and resume-ready learners using backend-owned classroom signals
- added direct classroom handoff into backend-owned learner continue actions instead of forcing every learner follow-up through the same screen
- added classroom-to-teacher drill-in context so the teacher explainability screen can return cleanly to the originating classroom queue
- expanded classroom and teacher view tests to cover the new triage and handoff behavior
- rebased again onto `origin/main` and reviewed backend commit `93954f9` against the frontend-to-backend plan; it strengthens backend-owned repair-stage progression without creating a new frontend contract gap
- rewrote `planning/from-front-to-back-needs.md` into a sharper backend marching-orders document that separates active asks, conditional future work, resolved seams, and frontend guardrails
- added shared frontend formatting and panel-state helpers so backend-owned statuses, actions, and content types render in more product-facing language across overview, classroom, teacher, generation, Socratic, and remediation views
- expanded view coverage for curated labels plus overview/classroom/teacher loading, error, and empty-history states
- added a shell-level workspace status surface that makes live connectivity and demo fallback posture visible from the main app chrome
- added app-level regression coverage for classroom-to-teacher handoff continuity, return-to-classroom flow, learner continue-action routing, and live contract connectivity state
- changed shell connectivity tracking from a single last-write-wins source flag to per-surface aggregation so one fallbacking contract family cannot be masked by another live refresh
- added app-level regression coverage for teacher-decision fallback notices and classroom refresh fallback after a live-connected boot
- rebased onto the latest `origin/main` again and reviewed the March 17, 2026 backend semantic-hardening stack; it strengthens rationale parity, stage-aware intervention language, misconception-path grounding, and held-remediation consistency without creating a new frontend contract gap
- curated the remaining overview-screen status, progression, strategy, and accommodation labels so fewer learner surfaces leak backend enum shapes directly
- completed a frontend CSS cleanup pass that replaced the last legacy overview pills, route-reason badges, and learner chip styles with shared `Pill` and `Button` primitives
- removed dead app-shell selectors that no longer affected layout after the shared primitive migration
- finished the remaining frontend layout-CSS sweep by migrating shell and view composition helpers onto explicit Tailwind utility classes across the app shell, workspace controls, and learner/teacher views
- reduced `frontend/src/App.css` to a smaller set of visual and card-level selectors instead of using it as a generic layout framework
- aligned the teacher intervention screen with backend-recorded latest decision state so the default selected option reflects the latest backend choice instead of always snapping back to the recommended option
- expanded behavioral coverage around teacher option submission, learner overview resume/history routing, and classroom selection plus teacher-first blocked-learner posture

## Notes For Future Updates

When work changes, update:

1. `Current Work`
2. `Missing Or Incomplete Items`
3. `Key Decisions`
4. `Completed`

# Coding quality bar:
- write code like this backend will be lived in for a long time
- optimize for modularity, maintainability, and elegant composition
- keep functions and modules crisp
- avoid cleverness that obscures intent
- prefer explicit, boring, trustworthy logic over fragile abstraction
- leave touched code better than you found it
- all major logic should be in the backend, save frontend requirements for the backend in from-front-to-back-needs.md
