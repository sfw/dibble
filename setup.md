# Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 22.14+ / npm 11.7+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## 1. Install dependencies

```bash
# Backend
uv sync

# Frontend
cd frontend && npm install
```

## 2. Start the backend

```bash
uv run python -m uvicorn --app-dir src dibble.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. On first start with no configuration, Dibble runs with default settings and mock LLM responses — no API keys required to explore the platform.

`--app-dir src` makes the `src/` layout importable directly, and `python -m uvicorn` ensures the server runs with the same Python interpreter managed by `uv`.

## 3. Start the frontend

```bash
cd frontend && npm run dev
```

Opens at `http://localhost:5173` by default (Vite dev server).

## 4. First-run setup

When the frontend detects the backend has no LLM API key configured, it shows the **Setup wizard** — a 4-step flow:

1. **Connect** — confirm the backend URL (defaults to `http://localhost:8000`)
2. **Provider** — enter your LLM API key, base URL, and model name
3. **Review & save** — writes `~/.dibble/config.toml` via the `/api/setup/configure` endpoint
4. **Done** — confirms the config path; restart the backend to pick up changes

After setup, the app routes to the login screen.

## 5. Configuration

All configuration lives in `~/.dibble/config.toml` (created automatically by the setup wizard or manually). Environment variables override TOML values.

**Precedence:** env vars > `~/.dibble/config.toml` > built-in defaults

### Minimal config (LLM only)

```toml
[llm]
api_key = "sk-..."
model = "gpt-4o"
```

### Configuration reference

#### Top-level

| Key | Type | Default | Description |
|---|---|---|---|
| `database_path` | string | `~/.dibble/dibble.db` | Path to the SQLite database. Supports `~` expansion. |
| `app_name` | string | `Dibble Adaptive Platform` | Display name shown in API docs. Not configurable via env var. |
| `app_version` | string | `0.3.0` | Platform version. Not configurable via env var. |

#### `[llm]` — Primary LLM provider

The primary LLM handles all pedagogical content generation: Socratic questioning, adaptive explanations, remediation content, and assessment items. Choose a strong reasoning model — output quality directly affects learning outcomes.

**Recommended:** A frontier-tier chat model with strong instruction following and reasoning (e.g. `gpt-4o`, `claude-sonnet-4-20250514`). Smaller/faster models like `gpt-4o-mini` work but produce noticeably weaker Socratic dialogue and less nuanced adaptive content.

| Key | Type | Default | Description |
|---|---|---|---|
| `api_base` | string | `https://api.openai.com/v1` | Base URL for the OpenAI-compatible chat completions API. |
| `api_key` | string | *none* | API key for the primary LLM. **Required for real generation** — without it, Dibble falls back to mock responses. |
| `model` | string | *none* | Model name (e.g. `gpt-4o`, `claude-sonnet-4-20250514`). |
| `timeout_seconds` | float | `20.0` | Request timeout for LLM calls. |
| `allow_mock_fallback` | bool | `true` | When `true`, returns mock/placeholder content if no LLM key is configured or the provider is unreachable. |
| `circuit_breaker_threshold` | int | `2` | Number of consecutive failures before the circuit breaker trips and stops calling the provider. |
| `circuit_breaker_cooldown_seconds` | float | `30.0` | How long a tripped circuit breaker stays open before retrying. |
| `selection_strategy` | string | `ordered` | Provider selection strategy when multiple providers are configured. Options: `ordered`, `round-robin`, `latency-aware`. |

#### `[llm.secondary]` — Failover LLM provider

Used automatically when the primary provider is unavailable (circuit breaker tripped). This is your safety net — it should be from a **different provider** than the primary so an outage at one doesn't take down both.

**Recommended:** A capable model from a different vendor than your primary. If your primary is OpenAI, use Anthropic here (or vice versa). Matching the primary's quality tier is ideal but a slightly smaller model is acceptable for failover.

| Key | Type | Default | Description |
|---|---|---|---|
| `api_base` | string | *none* | Base URL for the secondary provider. |
| `api_key` | string | *none* | API key for the secondary provider. |
| `model` | string | *none* | Model name for the secondary provider. |
| `timeout_seconds` | float | *inherits primary* | Request timeout for the secondary provider. |

#### `[embedding]` — Embedding provider

Used for semantic search over curriculum content. Embedding calls are frequent but lightweight — prioritize speed and cost over raw capability.

**Recommended:** A fast, low-cost embedding model like `text-embedding-3-small` (OpenAI) or `voyage-3-lite` (Voyage AI). The `dimensions` setting (default 256) keeps index size small; higher dimensions improve recall marginally but increase storage and latency. If no embedding key is configured, Dibble falls back to local lexical/metadata scoring — functional but less accurate for free-text curriculum queries.

| Key | Type | Default | Description |
|---|---|---|---|
| `api_base` | string | `https://api.openai.com/v1` | Base URL for the embeddings API. |
| `api_key` | string | *falls back to `llm.api_key`* | API key for embedding requests. Inherits from `llm.api_key` if not set. |
| `model` | string | *none* | Embedding model name (e.g. `text-embedding-3-small`). |
| `dimensions` | int | `256` | Embedding vector dimensions. |
| `timeout_seconds` | float | `15.0` | Request timeout for embedding calls. |
| `allow_local_fallback` | bool | `true` | Fall back to local lexical/metadata scoring when no embedding key is available. |

#### `[prompts]` — Prompt management

| Key | Type | Default | Description |
|---|---|---|---|
| `library_version` | string | `1.0` | Prompt library version to use. |
| `experiment_enabled` | bool | `false` | Enable A/B prompt experiments. |
| `adaptive_selection_enabled` | bool | `false` | Let the system choose prompt variants based on learner profile. |
| `variant_override` | string | *none* | Force a specific prompt variant (env var: `DIBBLE_PROMPT_VARIANT`). |

#### `[auth]` — Authentication

Config controls system-level auth behavior only. Users, API keys, roles, and permissions are managed in the database through the API — not in config.

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Enable authentication. When `false`, all endpoints are open. |
| `token_secret` | string | *none* | Secret for signing JWT session tokens. |
| `token_issuer` | string | `dibble` | JWT issuer claim. |
| `token_ttl_seconds` | int | `3600` | JWT access token lifetime (1 hour). |
| `refresh_ttl_seconds` | int | `604800` | JWT refresh token lifetime (7 days). |

> **Planned change:** `api_keys`, `principals`, and `header_name` will be removed from config. User accounts, API keys, and role assignments will be managed entirely in the database — created, listed, and revoked through API endpoints. The config file should only contain system functionality settings, not runtime user data.

#### `[cache]` — Caching

| Key | Type | Default | Description |
|---|---|---|---|
| `generation_cache_ttl_seconds` | int | `3600` | How long generated content is cached before regeneration (1 hour). |

#### `[performance]` — Performance tuning

| Key | Type | Default | Description |
|---|---|---|---|
| `predictive_warm_inline_process_limit` | int | `2` | Max number of content items to pre-generate inline during a request. |

#### `[plugins]` — Plugin entry points

Each value is a Python dotted path to a factory function (`module.path:function`).

| Key | Default | Description |
|---|---|---|
| `router` | `dibble.plugins.defaults.router:build` | Adaptive routing strategy for content selection. |
| `retriever` | `dibble.plugins.defaults.retriever:build` | Curriculum content retrieval (search + ranking). |
| `provider` | `dibble.plugins.defaults.provider:build` | LLM provider integration. |
| `validator` | `dibble.plugins.defaults.validator:build` | Generated content validation. |

### Full example

```toml
database_path = "~/.dibble/dibble.db"

[llm]
api_base = "https://api.openai.com/v1"
api_key = "sk-..."
model = "gpt-4o"
timeout_seconds = 20.0
allow_mock_fallback = true

[llm.secondary]
api_base = "https://api.anthropic.com/v1"
api_key = "sk-ant-..."
model = "claude-sonnet-4-20250514"

[embedding]
api_key = "sk-..."          # falls back to llm.api_key if omitted
model = "text-embedding-3-small"
dimensions = 256

[auth]
enabled = false
token_secret = "your-secret-here"

[plugins]
router = "dibble.plugins.defaults.router:build"
retriever = "dibble.plugins.defaults.retriever:build"
provider = "dibble.plugins.defaults.provider:build"
validator = "dibble.plugins.defaults.validator:build"
```

### Environment variable overrides

Every Settings field maps to `DIBBLE_{FIELD_UPPER}`:

| Field | Env var |
|---|---|
| `llm_api_key` | `DIBBLE_LLM_API_KEY` |
| `llm_model` | `DIBBLE_LLM_MODEL` |
| `database_path` | `DIBBLE_DATABASE_PATH` |
| `auth_enabled` | `DIBBLE_AUTH_ENABLED` |

File permissions on `config.toml` are set to `0600` (owner-only) since it may contain API keys.

## 6. Data storage

| What | Where |
|---|---|
| Config | `~/.dibble/config.toml` |
| Database | `~/.dibble/dibble.db` (default) |

The `~/.dibble/` directory is created with mode `0700` on first use.

## 7. Running tests

```bash
# Backend
uv run pytest
uv run ruff check src/ tests/

# Frontend
cd frontend && npm test
cd frontend && npm run build    # type-check + production build
cd frontend && npm run lint
```
