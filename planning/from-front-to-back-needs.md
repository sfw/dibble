# From Front To Back Needs

Last updated: 2026-03-17

This document tracks backend-facing needs discovered while implementing the frontend.

It should contain:

- missing read models the frontend cannot responsibly invent
- missing write contracts for teacher or workflow actions
- contract clarifications that reduce fragile UI assumptions

## Current Backend Needs

### P0

- Teacher override / approval write endpoints for intervention decisions.
- A teacher-safe learner intervention action contract so the UI can move beyond advisory-only controls.
- A cohort or classroom-level teacher read model if teacher workflows are expected to extend beyond single-learner drill-in.

### P1

- History/list endpoints for generated runs by learner.
- History/list endpoints for Socratic sessions by learner.
- History/list endpoints for remediation sessions by learner.
- Clearer curriculum/course progression ownership so the frontend does not need to infer anything beyond `current_flow`.

### P2

- Richer artifact payload contracts for multimodal or interactive content.
- More compact explainability-oriented teacher analytics if the product needs more than learner-detail summaries.

## Frontend Stance Until These Exist

- Keep teacher actions advisory and clearly labeled as non-authoritative.
- Use learner-detail views rather than inventing classroom dashboards from partial data.
- Prefer known session IDs and current active context over speculative history UIs.
- Render workflow summaries and `current_flow` directly instead of reconstructing progression.
