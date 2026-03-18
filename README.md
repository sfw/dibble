![dibble hero](docs/images/dibble.png)
# Dibble

A dibble is a pointed tool used to make holes in the ground for planting seeds — precise, deliberate, and purposeful. Dibble the platform works the same way: it uses generative AI to surgically plant seeds of knowledge, adapting to each learner so every concept takes root.

Dibble is an adaptive learning management system that watches how a learner thinks, struggles, and recovers — then generates exactly the right content at the right moment. Explanations, worked examples, practice problems, and Socratic assessments are all created on the fly, grounded in real curriculum, and tuned to the learner's mastery, cognitive load, and affective state. When its own decisions don't work, the system notices: it tracks whether each hold, redirect, and progression call actually helped the learner, and adjusts its thresholds so the next decision is better.

## What learners experience

A learner working on adding fractions gets a practice problem wrong. Dibble doesn't just serve another problem — it detects a likely place-value misconception from the error pattern and prior struggle history, steps back to a prerequisite concept, generates a worked example with fading support tailored to the learner's cognitive load, then bridges back to the original topic through a connecting problem. The whole arc happens within a single session, with the system adjusting support intensity based on how the learner responds at each step.

If the learner is frustrated, Dibble notices and eases off. If they're coasting through scaffolded problems without actually understanding, it notices that too — and holds them on the concept instead of letting inflated scores push them forward prematurely.

## What teachers experience

Teachers see their classroom sorted into three triage buckets — **needs action**, **needs attention**, and **on track** — computed server-side from each learner's mastery trajectory, intervention history, and current state. They can drill into any learner to see the system's current pedagogical decision and its rationale: why it's holding a student on repair practice, why it redirected an assessment attempt back to a prerequisite, or why it's ready to let a student attempt transfer.

Every decision the system makes is a proposal. Teachers can approve the current move, choose from backend-generated alternatives (each labeled with its stage — repair, bridge, target, transfer), defer, or escalate. Mastery trend lines show per-learner trajectories and classroom averages over time, so teachers can see whether the system's interventions are actually working.

## How it works

**The backend owns all learning decisions.** Mastery gates, progression sequencing, remediation arcs, misconception detection, and content-mode selection all live in backend services. The frontend renders those decisions — it never interprets raw signals or makes pedagogical choices on its own.

The core loop:

1. **Observe** — the system ingests learner interaction signals (time on task, correctness, help-seeking, confidence) and infers affective state, cognitive load, and metacognitive readiness
2. **Route** — an adaptive router chooses the next instructional move: teach, reteach, step back to a prerequisite, stretch toward transfer, or trigger remediation
3. **Generate** — a retrieval-grounded pipeline produces curriculum-aligned content through an LLM, with moderation, validation, and deterministic fallbacks
4. **Assess** — multi-turn Socratic probes evaluate understanding through conversational evidence scoring, feeding mastery and metacognitive updates back into the loop
5. **Calibrate** — the system evaluates its own decisions against subsequent learner outcomes. Progression holds that helped are reinforced; holds that stalled are relaxed. Misconception remediation that resolved is noted; remediation that failed repeatedly is flagged for teacher review. These feedback loops run at the level of individual routing actions, mastery quality gates, and misconception detection confidence — not as global tuning, but as per-learner, per-concept self-correction

## Repository layout

```
src/dibble/          FastAPI backend — services, models, plugins, routes
frontend/            React + Vite + TypeScript — learner, teacher, and classroom UI
planning/            Spec, gap analysis, and work plans
docs/                Extended technical documentation
```

## Quick start

### Backend

```bash
uv sync --group dev                                  # install dependencies
uv run uvicorn dibble.main:app --reload              # start the API server
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

Dibble runs on SQLite by default (`dibble.db`). No external services are required for local development — the system falls back to a deterministic mock LLM provider and a local embedder when no API keys are configured.

### Core settings

| Variable | Purpose |
|---|---|
| `DIBBLE_DATABASE_PATH` | SQLite database location (default: `dibble.db`) |
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

The API is organized around learners, teachers, content generation, curriculum, and platform operations. Start the server and visit `/docs` for the full interactive OpenAPI reference.

## Architecture

The backend is built on **FastAPI + Pydantic + SQLite** with dependency injection (`bootstrap.py`) and a plugin system for extensibility. Services are single-responsibility and communicate through typed Pydantic models.

The frontend is built on **React + Vite + TypeScript** with **shadcn/ui + Tailwind CSS**. It fetches and renders backend decisions — no pedagogical logic lives client-side.

For the full technical changelog, including calibration pipelines, misconception detection, mastery decay, progression outcome feedback loops, and content moderation details, see [`docs/CHANGELOG.md`](docs/CHANGELOG.md).

## License

All rights reserved.
