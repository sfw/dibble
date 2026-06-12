# Dibble — CLAUDE.md

## What this is

Dibble is an AI-powered adaptive LMS. The backend (FastAPI + Pydantic + SQLite) owns all pedagogical logic. The frontend (React + Vite + TypeScript) renders backend decisions — it never interprets raw signals or makes learning-path choices.

## Commands

```bash
# Backend
uv run pytest                        # run all backend tests
uv run pytest tests/test_foo.py      # run one test file
uv run ruff check src/ tests/        # lint
uv run ruff format src/ tests/       # format

# Frontend
cd frontend && npm test              # run all frontend tests
cd frontend && npm run build         # type-check + production build (MUST pass before committing)
cd frontend && npm run lint          # eslint
```

## POC adaptive-stack feature freeze (in effect)

The adaptive decision stack is **frozen** until the pilot produces evidence. Any change touching the following services requires **explicit human approval** — bug fixes only, no new calibration layers, profiles, or feedback loops:

- Routing: `calibrated_router.py`, `adaptive_router.py`, `plugins/defaults/router.py`, `router_calibration_signals.py`
- Calibration / signals: `learner_state_signal.py`, `learner_strategy_signal.py`, `learner_state_prediction_signals.py`, `learner_state_prediction_outcomes.py`
- Progression: `progression_ownership.py`, `kc_sequence_planner.py`, `progression_outcome_tracker.py`, `progression_outcome_signals.py`, `outcome_driven_adaptation.py`, `within_session_adaptation.py`
- Mastery: `mastery_quality_gate_signals.py`, `mastery_quality_gate_outcomes.py`, `mastery_snapshot_service.py`, `ordinary_mastery_profiles.py`

Shadow/observability wrappers that **only log** (e.g. baseline counterfactual logging) are allowed, provided they have zero behavioral impact on production decisions.

## Architecture rules

### Backend owns logic, frontend owns presentation

- All mastery gates, progression decisions, intervention policy, remediation arcs, and Socratic assessment logic live in `src/dibble/services/`.
- API responses include `display_label` and other presentation-ready fields. The frontend uses these directly.
- Frontend hooks (`src/hooks/`) fetch and cache backend state. They do not compute derived pedagogical state.
- If a feature requires a new decision or calculation, add it to a backend service and expose it through the API — do not put it in the frontend.

### Modularity is mandatory

- Each service file has a single responsibility. Do not merge unrelated concerns into one file.
- New domain logic gets its own service file in `src/dibble/services/`. Prefer a new file over growing an existing one past ~300 lines.
- Services communicate through typed Pydantic models, not raw dicts.
- **No god files.** If a file is accumulating too many responsibilities, split it. Use the plugin architecture (`src/dibble/plugins/`) and dependency injection (`bootstrap.py`) to keep components loosely coupled and independently testable.
- When adding new integrations or strategies, implement them as plugins with a shared interface — do not hardcode variants into existing services.

### Pydantic models are the contract layer

- All API request/response shapes and inter-service data are Pydantic models in `src/dibble/models/`.
- Frontend TypeScript types in `frontend/src/types.ts` mirror these models. Keep them in sync when changing API contracts.
- Use enums for finite vocabularies.

### Frontend conventions

- **shadcn + Tailwind CSS**: UI primitives live in `frontend/src/components/ui/`. Use existing primitives before creating new ones.
- **Tailwind only**: No CSS modules, no styled-components, no inline style objects. All styling through Tailwind utility classes.
- **Component hierarchy**: `ui/` (primitives) → `app/` and `content/` (domain components) → `views/` (pages) → `shells/` (layouts).
- **One component per file**. Co-locate small helper components only if they are not used elsewhere.

### Testing

- Backend: pytest with SQLite fixtures. Every new service or endpoint needs tests.
- Frontend: Vitest + React Testing Library. Test user-visible behavior, not implementation details.
- **Tests are not an afterthought.** Write tests alongside the code they cover — every new service, endpoint, or component must include tests in the same piece of work, not as a follow-up.
- **Before committing**: always run lint, tests, **and the production build** for any code you changed. Do not commit code that has not passed all three. For the frontend this means running `cd frontend && npm run build` (which runs `tsc -b && vite build`) in addition to tests and lint — CI will fail on type errors or build failures that tests alone do not catch.

### Dependencies and wiring

- Backend services are wired through `src/dibble/bootstrap.py` using dependency injection. Do not import services directly in route handlers — receive them via `ApiContext`.
- Plugins (`src/dibble/plugins/`) provide extensibility for router, retriever, provider, and validator. Use the plugin interface for new integrations rather than hardcoding.

## Style

- Python: follow ruff defaults (configured in `pyproject.toml`).
- TypeScript: follow the project eslint config. Strict mode is on.
- Type hints on all Python function signatures. TypeScript strict — no `any` unless unavoidable.
- Async/await throughout the backend. No sync blocking calls in route handlers or services.
