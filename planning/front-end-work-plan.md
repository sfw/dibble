# Frontend Work Plan

Last updated: 2026-03-16

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

- migrate the current frontend shell from starter CSS patterns toward Tailwind + shadcn primitives
- replace remaining ad hoc form controls with shared UI primitives where it improves consistency
- reduce reliance on legacy app-shell CSS without destabilizing current screens
- expand the new test suite beyond foundational helper/API/view coverage as we add screens and interactions

### Next up

1. continue migrating screen-level controls onto shared Tailwind + shadcn-style primitives
2. polish teacher explainability language and raw payload drill-downs
3. add workflow-focused tests for learner overview, generation, Socratic, and remediation screens
4. watch backend changes for any new teacher intervention or history endpoints
5. keep this work plan updated as backend/frontend seams change

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

## Notes For Future Updates

When work changes, update:

1. `Current Work`
2. `Missing Or Incomplete Items`
3. `Key Decisions`
4. `Completed`

Coding quality bar:
- write code like this backend will be lived in for a long time
- optimize for modularity, maintainability, and elegant composition
- keep functions and modules crisp
- avoid cleverness that obscures intent
- prefer explicit, boring, trustworthy logic over fragile abstraction
- leave touched code better than you found it
