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
- `POST /api/content/generate` with `workflow_summary`
- `POST /api/llm/stream`
- `POST /api/assessments/socratic` with canonical session `summary`
- `GET /api/assessments/socratic/{session_id}`
- `POST /api/remedial/trigger`
- `GET /api/remedial/sessions/{session_id}`
- `POST /api/remedial/sessions/{session_id}/advance`

## Missing Or Incomplete Items

These are the highest-signal frontend gaps discovered so far:

| Priority | Gap | Impact on frontend |
|---|---|---|
| P0 | No teacher override / approval write contract | Teacher intervention UI must stay advisory for now |
| P0 | No cohort / classroom dashboard read model | First teacher UI should be learner-detail focused |
| P1 | No history/list endpoints for sessions or generated runs per learner | Session review must rely on known IDs or current active context |
| P1 | Progression orchestration is still local rather than full course-owned | UI must trust `current_flow` and workflow summaries, not invent lesson progression |
| P2 | No multimodal artifact payload contract | UI should keep content cards extensible without assuming diagrams or interactives yet |
| P2 | Teacher-safe analytics are summary-based, not dashboard-grade | Explainability should come from compact read models rather than admin telemetry |

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
- Record missing teacher intervention, history, and dashboard contracts there rather than letting them drift across chat and code comments.

### P2: polish higher-level product surfaces

- Improve teacher-facing intervention language so advisory states are clear even without write contracts.
- Replace raw JSON-first payload inspection with more curated explainability summaries where possible.
- Continue making the UI resilient to richer artifact types without assuming they already exist.

## Key Decisions

### Product / Contract

- Treat `current_flow` and workflow/session summaries as the source of truth for UI state.
- Do not reconstruct learner state from audit logs or internal request context unless there is no alternative.
- Keep teacher-facing decisions explainable with explicit rationale, confidence, and next-step metadata.

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

- reduce reliance on legacy app-shell CSS without destabilizing current screens
- keep frontend-originated backend needs captured in a dedicated planning document
- continue tightening shared screen-level primitives so new views do not reintroduce raw control patterns

### Next up

1. continue reducing legacy CSS by migrating repeated screen containers and layout helpers onto shared primitives where it improves clarity
2. add deeper behavioral tests around live/demo fallback transitions and streamed generation behavior
3. consider whether overview and teacher surfaces need curated explainability components in place of raw JSON panels
4. track backend changes for teacher intervention, learner history, and classroom-level read models
5. keep this work plan and `from-front-to-back-needs.md` updated together

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
