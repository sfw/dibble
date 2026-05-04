![dibble hero](docs/images/dibble.png)
# Dibble

A dibble is a pointed tool for making holes in the ground to plant seeds. Dibble the platform does something similar: it uses generative AI to figure out what a learner needs and then makes it for them.

It's an adaptive LMS. It generates explanations, worked examples, practice problems, and Socratic assessments on the fly, all grounded in real curriculum. It tracks mastery, estimates cognitive load and affect, and adjusts what it serves based on how the learner is actually doing. When its decisions don't help, it notices and changes course.

## What learners experience

Say a learner gets a fraction addition problem wrong. Instead of just throwing another problem at them, Dibble looks at the error pattern and their history, figures out they probably have a place-value misconception, steps back to the prerequisite, generates a worked example with fading support, and then bridges back to the original topic. This all happens in one session, and the system adjusts as the learner responds.

If the learner is frustrated, it eases off. If they're breezing through scaffolded problems without really understanding, it holds them there instead of letting inflated scores push them forward.

## What teachers experience

Teachers see their classroom in three buckets: **needs action**, **needs attention**, and **on track**. These are computed server-side from each learner's mastery trajectory and intervention history. Teachers can drill into any learner to see what the system is doing and why: why it's holding someone on repair practice, why it sent them back to a prerequisite, why it thinks they're ready for transfer.

Every decision the system makes is a proposal. Teachers can approve it, pick from alternatives (labeled by stage: repair, bridge, target, transfer), defer, or escalate. Trend lines show per-learner and classroom-level mastery over time so you can tell if interventions are actually working.

## How it works

**The backend owns all learning decisions.** Mastery gates, progression sequencing, remediation, misconception detection, content-mode selection: all backend services. The frontend renders what the backend tells it to. No pedagogical logic lives client-side.

The core loop:

1. **Observe**: ingest learner signals (time on task, correctness, help-seeking, confidence) and infer affective state, cognitive load, and metacognitive readiness
2. **Route**: pick the next move. Teach, reteach, step back to a prerequisite, stretch toward transfer, or trigger remediation
3. **Generate**: produce curriculum-aligned content through an LLM with retrieval grounding, moderation, validation, and deterministic fallbacks
4. **Assess**: run multi-turn Socratic probes that evaluate understanding through conversational evidence scoring, then feed mastery and metacognitive updates back into the loop
5. **Calibrate**: evaluate past decisions against what actually happened. Holds that helped get reinforced; holds that stalled get relaxed. Remediation that worked is noted; remediation that kept failing gets flagged for teacher review. This runs per-learner, per-concept, not as global tuning

## Repository layout

```
src/dibble/          FastAPI backend — services, models, plugins, routes
frontend/            React + Vite + TypeScript — learner, teacher, and classroom UI
planning/            Spec, gap analysis, and work plans
docs/                Extended technical documentation
```

## Quick start

For the proof household container path, see [`docs/deployment/household-container.md`](docs/deployment/household-container.md).

### Backend

```bash
uv sync --group dev                                  # install dependencies
uv run python -m uvicorn --app-dir src dibble.main:app --reload --port 8000
uv run pytest                                        # run tests
uv run ruff check src/ tests/ && uv run ruff format src/ tests/  # lint + format
```

### Frontend

```bash
cd frontend
npm ci           # install dependencies
npm run dev      # start dev server
npm test         # run tests
npm run lint     # eslint
npm run build    # type-check + production build
```

### Git hooks

```bash
pre-commit install   # installs trufflehog secret scanning hook
```

## Configuration

Dibble runs on SQLite by default (`dibble.db`). No external services needed for local dev. If you don't configure API keys, it falls back to a deterministic mock LLM provider and a local embedder.

### Core settings

| Variable | Purpose |
|---|---|
| `DIBBLE_DATABASE_PATH` | SQLite database location (default: `dibble.db`) |
| `DIBBLE_DEPLOYMENT_MODE` | Operator-readable deployment posture (`local_dev` or `household_container`) |
| `DIBBLE_FRONTEND_DIST_PATH` | Optional built React frontend served by FastAPI |
| `DIBBLE_AUTH_ENABLED` | Enable API key + bearer token auth |
| `DIBBLE_AUTH_TOKEN_SECRET` | Secret for signing bearer tokens |

### LLM provider

| Variable | Purpose |
|---|---|
| `DIBBLE_LLM_API_BASE` | OpenAI-compatible endpoint |
| `DIBBLE_LLM_API_KEY` | API key |
| `DIBBLE_LLM_MODEL` | Model name |
| `DIBBLE_LLM_SELECTION_STRATEGY` | `ordered`, `round_robin`, or `latency_aware` |
| `DIBBLE_LLM_ALLOW_MOCK_FALLBACK` | Fall back to deterministic mock (default: `true`) |

Secondary provider, circuit breaker, embedding, prompt experiment, and auth settings are documented in [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

### Plugins

The router, retriever, provider, and validator are pluggable:

```bash
export DIBBLE_ROUTER_PLUGIN=dibble.plugins.defaults.router:build
export DIBBLE_RETRIEVER_PLUGIN=dibble.plugins.defaults.retriever:build
export DIBBLE_PROVIDER_PLUGIN=dibble.plugins.defaults.provider:build
export DIBBLE_VALIDATOR_PLUGIN=dibble.plugins.defaults.validator:build
```

## API

Start the server and hit `/docs` for the interactive OpenAPI reference. Endpoints cover learners, teachers, content generation, curriculum, and platform operations.

## Architecture

Backend is **FastAPI + Pydantic + SQLite** with dependency injection (`bootstrap.py`) and a plugin system. Services are single-responsibility and talk to each other through typed Pydantic models.

Frontend is **React + Vite + TypeScript** with **shadcn/ui + Tailwind CSS**. It renders backend decisions. That's it.

Full technical changelog (calibration, misconception detection, mastery decay, feedback loops, content moderation, etc.) is in [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

## License

All rights reserved.
