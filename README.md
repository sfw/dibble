![dibble hero](docs/images/dibble.png)
# Dibble

Dibble is an adaptive LMS that generates learner-specific instruction on demand.
Instead of selecting from a fixed content bank, it decides what the learner
needs next and generates it inside a backend-owned pedagogical loop.

Today Dibble can:

- generate explanations, worked examples, practice, and Socratic assessments
- ground generation in curriculum and retrieval context
- adapt by mastery, misconception, cognitive load, affect, and recent outcomes
- reuse curriculum-safe shared artifacts across learners without leaking
  learner-private data
- run inside a household-scoped container with persistent local state and
  operator-facing readiness/proof workflows

## What Is Proven Today

Dibble is not just a prototype UI. It now has:

- a real household container deployment path
- a live proof workflow against Dockerized household runtime
- privacy-safe shared-library reuse
- restart, backup, restore, and post-restore verification
- readiness, observability, rollout, and approval-governance surfaces
- an offline content-quality eval harness

The clearest current proof posture is:

- internally proven
- credibly proven for a small operator-managed pilot rehearsal
- not yet claimed as fully proven for unsupervised real-world parent use

See:

- [Final Proof Status](/Users/sfw/Development/dibble/docs/proof/final-proof-status.md)
- [Live Household Proof Procedure](/Users/sfw/Development/dibble/docs/proof/live-household-proof.md)
- [Pilot Readiness Runbook](/Users/sfw/Development/dibble/docs/runbooks/pilot-readiness.md)

## How Dibble Works

The backend owns all pedagogical decisions. The frontend renders backend state
and backend decisions; it does not interpret raw learner signals or compute its
own adaptation logic.

Core loop:

1. Observe learner signals such as correctness, timing, confidence, hints, and
   conversation evidence.
2. Infer learner state including mastery posture, load, affect, and support
   need.
3. Plan the next move: target practice, prerequisite repair, bridge work,
   transfer, remediation, or conversational assessment.
4. Generate curriculum-aligned content through a provider path with grounding,
   moderation, validation, and safe fallbacks.
5. Record outcomes and revise future routing, planning, modality choice, and
   retention candidates based on what actually helped.

## Repository Layout

```text
src/dibble/          FastAPI backend: models, services, plugins, routes
frontend/            React + Vite + TypeScript frontend
docs/                Deployment, proof, runbooks, and technical notes
planning/            Roadmaps, risk plans, design notes, implementation plans
deploy/household/    Household container deployment files
proof/               Proof fixtures and proof support assets
evals/               Offline evaluation corpora
scripts/             Proof, eval, and operational helper scripts
```

## Local Development

### Backend

```bash
uv sync --group dev
uv run python -m uvicorn --app-dir src dibble.main:app --reload --port 8000
```

Common backend checks:

```bash
uv run pytest
uv run ruff check src/dibble tests scripts
uv run ruff format src/dibble tests scripts
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend verification:

```bash
cd frontend
npm test
npm run lint
npm run build
```

### Local Runtime Defaults

By default Dibble uses:

- SQLite for persistence
- a mock LLM fallback if no real LLM credentials are configured
- a local hash embedder unless a real embedding provider is configured

That is fine for local development and dry-run rehearsal. It is not the target
posture for a real pilot-proof run.

## Household Container Deployment

Dibble now has a first-class household container path: one household runtime,
local persistent state, proof-ready readiness checks, and operator-facing setup.

Start here:

- [Household Container Deployment](/Users/sfw/Development/dibble/docs/deployment/household-container.md)

Typical flow:

1. Copy `deploy/household/.env.example` to `deploy/household/.env`
2. Configure real provider settings and auth secret
3. Run `docker compose up --build` from `deploy/household/`
4. Check `http://localhost:8000/health` for liveness
5. Check `http://localhost:8000/ready` for actual deployment readiness
6. Create the initial operator and household
7. Run the live proof workflow before treating the container as pilot-ready

Important distinction:

- `/health` means the process is alive
- `/ready` means the household runtime is actually ready for use

Docker health is wired to `/ready`, not just HTTP 200.

## Live Proof Workflow

The proof path now exercises real runtime behavior, not just static fixtures.

The main operator workflow is:

```bash
uv run python scripts/live_household_proof.py \
  --base-url http://localhost:8000 \
  --compose-dir deploy/household \
  --require-real-provider
```

That proof run exercises:

- canonical proof scenarios
- a longitudinal repeated-session timeline
- privacy-safe shared-library reuse
- multi-household evidence
- container restart persistence
- SQLite backup and restore
- post-restore readiness and household verification

Related docs:

- [Live Household Proof Procedure](/Users/sfw/Development/dibble/docs/proof/live-household-proof.md)
- [Scenario Definitions](/Users/sfw/Development/dibble/docs/proof/scenarios.md)
- [Content Quality Review Method](/Users/sfw/Development/dibble/docs/proof/content-quality-review.md)

## Configuration

Core runtime settings include:

| Variable | Purpose |
| --- | --- |
| `DIBBLE_DATABASE_PATH` | SQLite database location |
| `DIBBLE_DEPLOYMENT_MODE` | Deployment posture such as `local_dev` or `household_container` |
| `DIBBLE_FRONTEND_DIST_PATH` | Built frontend path served by FastAPI |
| `DIBBLE_AUTH_ENABLED` | Enables auth |
| `DIBBLE_AUTH_TOKEN_SECRET` | Bearer token signing secret |
| `DIBBLE_LLM_API_BASE` | OpenAI-compatible API base |
| `DIBBLE_LLM_API_KEY` | LLM API key |
| `DIBBLE_LLM_MODEL` | LLM model name |
| `DIBBLE_LLM_ALLOW_MOCK_FALLBACK` | Mock fallback switch |
| `DIBBLE_EMBEDDING_API_KEY` | Embedding provider key |
| `DIBBLE_EMBEDDING_MODEL` | Embedding model |
| `DIBBLE_CLOUD_LIBRARY_ENABLED` | Enables remote cloud-library path |

For household proof and pilot rehearsal, use the deployment doc rather than
guessing config combinations:

- [Household Container Deployment](/Users/sfw/Development/dibble/docs/deployment/household-container.md)

## Architecture Notes

Backend:

- FastAPI + Pydantic + SQLite
- dependency injection through `bootstrap.py`
- plugin seams for router, retriever, provider, validator, and modalities
- single-responsibility services under `src/dibble/services/`

Frontend:

- React + Vite + TypeScript
- shadcn/ui + Tailwind CSS
- presentation-only relative to pedagogical logic

Privacy boundary:

- learner-private dialogue and learner-state rationale stay inside Dibble-owned
  runtime paths
- provider/cloud-library paths are constrained to curriculum-shaped payloads

## Current Risk-Reduction Roadmap

The current risk-reduction execution moved from planning into implementation.

Completed:

- diagram hardening
- retention scheduler stage 1
- stronger readiness and embedder posture
- offline content-quality eval harness
- proof/pilot operational hardening

Next:

- context-preserving modality summaries
- mastery/progression measurement pass
- retention scheduler stage 2

See:

- [Risk Reduction Implementation Plan](/Users/sfw/Development/dibble/planning/2026-06-08-risk-reduction-implementation-plan.md)
- [Risk Register](/Users/sfw/Development/dibble/planning/2026-05-05-risk-register.md)

## Useful Entry Points

- API docs: `http://localhost:8000/docs`
- Setup and readiness: [household-container.md](/Users/sfw/Development/dibble/docs/deployment/household-container.md)
- Proof posture: [final-proof-status.md](/Users/sfw/Development/dibble/docs/proof/final-proof-status.md)
- Pilot operations: [pilot-readiness.md](/Users/sfw/Development/dibble/docs/runbooks/pilot-readiness.md)
- Implementation roadmap: [2026-06-08-risk-reduction-implementation-plan.md](/Users/sfw/Development/dibble/planning/2026-06-08-risk-reduction-implementation-plan.md)

## License

All rights reserved.
