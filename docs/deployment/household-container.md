# Household Container Deployment

This is the proof deployment path for Dibble: one container per household, with learner-private state persisted inside the household boundary and only curriculum-shaped content leaving the container.

## Runtime Shape

- One FastAPI process serves the API and the built React frontend.
- SQLite lives at `/data/dibble.db` inside the container.
- `/data` must be mounted as a persistent Docker volume or host directory.
- Model-provider calls receive curriculum-shaped prompts only.
- Cloud-library remote access is off by default; local curriculum-shaped reuse remains active.

## First Run

From the repository root:

```bash
cp deploy/household/.env.example deploy/household/.env
```

Edit `deploy/household/.env`:

- Set `DIBBLE_AUTH_TOKEN_SECRET` to a long random value.
- Set `DIBBLE_LLM_API_KEY` and `DIBBLE_LLM_MODEL` for real generation.
- Set `DIBBLE_LLM_ALLOW_MOCK_FALLBACK=false` for the final real-provider proof
  run. Keep it `true` only for setup and dry-run rehearsal.
- If the selected OpenAI-compatible model enforces provider-specific values,
  set them explicitly. The Moonshot `kimi-k2.5` live proof uses
  `DIBBLE_LLM_TEMPERATURE=1.0`.
- Keep `DIBBLE_LLM_THINKING_ENABLED=true` or omit it for the Moonshot
  `kimi-k2.5` proof path. Moonshot rejects `temperature=1.0` when thinking is
  explicitly disabled.
- Set `DIBBLE_LLM_RESPONSE_FORMAT_JSON=true` for the Moonshot proof path so
  generated content stays on Dibble's structured JSON contract.
- For high-latency or verbose providers, set `DIBBLE_LLM_TIMEOUT_SECONDS` and
  `DIBBLE_LLM_MAX_TOKENS` to bounded live-proof values instead of relying on
  the defaults. The `kimi-k2.5` live proof used
  `DIBBLE_LLM_THINKING_ENABLED=true`, `DIBBLE_LLM_TEMPERATURE=1.0`,
  `DIBBLE_LLM_RESPONSE_FORMAT_JSON=true`, `DIBBLE_LLM_TIMEOUT_SECONDS=300`,
  `DIBBLE_LLM_RETRY_BACKOFF_SECONDS=20`, `DIBBLE_LLM_RETRY_ATTEMPTS=6`, and
  `DIBBLE_LLM_MAX_TOKENS=8000`.
- Leave `DIBBLE_CLOUD_LIBRARY_ENABLED=false` for the first household pilot rehearsal.

Start the household runtime:

```bash
cd deploy/household
docker compose up --build
```

Open:

- App: `http://localhost:8000`
- Startup health: `http://localhost:8000/health`
- Deployment readiness: `http://localhost:8000/ready`

`/health` is liveness only: it returns `200` when the backend process can answer HTTP requests, even if first-run setup is incomplete.

`/ready` is readiness: it returns an operator-readable JSON payload with `status` set to `ready`, `setup_required`, `degraded`, or `not_ready`. The Docker healthcheck parses this payload and only treats `status: "ready"` as healthy. A container that is still in setup, degraded, or failed will keep running, but Docker will not mark it healthy.

The readiness checklist covers database persistence, provider setup, admin setup, frontend bundle, auth posture, cloud-library posture, and telemetry.

## Create the Initial Operator

The first admin endpoint is intentionally available before auth is fully bootstrapped:

```bash
curl -sS -X POST http://localhost:8000/api/setup/admin \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Household Operator"}'
```

Keep the returned API key. Use it to create the parent and learner users:

```bash
curl -sS -X POST http://localhost:8000/api/users \
  -H "X-API-Key: ADMIN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Parent","role":"parent"}'

curl -sS -X POST http://localhost:8000/api/users \
  -H "X-API-Key: ADMIN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Avery","role":"learner"}'
```

Use the parent credential and learner id to create the household:

```bash
curl -sS -X PUT http://localhost:8000/api/households/me/setup \
  -H "X-API-Key: PARENT_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "household_name": "Pilot Household",
    "learner_ids": ["LEARNER_ID"],
    "relationship_label": "parent",
    "preferences": {
      "session_cadence": "daily",
      "auto_session_suggestions": true,
      "weekly_summary_day": "sunday",
      "soft_escalation_enabled": true,
      "approval_mode": "guided",
      "modality_introduction_requires_approval": true,
      "trajectory_revision_requires_approval": true,
      "high_autonomy_session_requires_approval": true
    }
  }'
```

Recheck `/ready`. A pilot-ready household should have no failed checks. Warnings are acceptable for dry-run rehearsal, but not for real learner sessions unless the runbook explicitly accepts them.

Docker health remains unhealthy until `/ready` reports `status: "ready"`. This is intentional: `setup_required` and `not_ready` are not deployable states, and `degraded` should be resolved or explicitly accepted outside Docker health before a pilot learner uses the container.

## Persistence Check

After household setup:

```bash
docker compose restart dibble
curl -sS http://localhost:8000/ready
```

Then sign in or call `GET /api/households/me/overview` with the parent key. The household and learner should still be present. If they are missing, the `/data` mount is not persistent and the deployment is not proved.

## Live Household Proof

The final proof path is the live household proof wrapper. It runs the public API
proof scenarios against the Compose service, then exercises Docker restart,
backup, restore, and post-restore verification:

```bash
uv run python scripts/live_household_proof.py \
  --base-url http://localhost:8000 \
  --compose-dir deploy/household \
  --request-timeout-seconds 360 \
  --require-real-provider
```

If an admin already exists, pass the saved operator key:

```bash
DIBBLE_PROOF_ADMIN_API_KEY=ADMIN_API_KEY \
  uv run python scripts/live_household_proof.py \
  --base-url http://localhost:8000 \
  --compose-dir deploy/household \
  --request-timeout-seconds 360 \
  --require-real-provider
```

Artifacts are written under `proof-artifacts/live-household-*` unless
`--artifact-dir` is provided:

- `live-household-proof-report.md` for operator review and handoff
- `live-household-proof-report.json` for machine-readable evidence
- `dibble-live-household-backup.db` copied from `/data/dibble.db`

The script creates proof households, proof learners, fraction-equivalence
curriculum, guided household preferences, and explicit goals/trajectories. It
rehearses the five canonical scenarios from `docs/proof/scenarios.md`, runs the
longitudinal timeline from a clean proof household in the same container,
restarts the container, copies the SQLite database backup, restores it, fixes
database file ownership for the non-root runtime user, and verifies the
household overview still matches after restart and restore.

For API-only debugging, use the lower-level rehearsal runner:

```bash
uv run python scripts/rehearse_proof_scenarios.py \
  --base-url http://localhost:8000 \
  --timeline longitudinal_fraction_recovery \
  --summary-file proof-longitudinal-report.json \
  --operator-report-file proof-longitudinal-report.md
```

Omitting `--require-real-provider` is acceptable only for dry-run rehearsal. A
mock-backed report is not live household proof.

## Backup And Restore

For the proof deployment, the backup unit is `/data/dibble.db`.

The preferred evidence-producing path is `scripts/live_household_proof.py`,
which stops the service, uses `docker compose cp`, restarts the service, and
records the backup path, size, checksum, restart evidence, and restore evidence
in the proof report.

Manual backup:

```bash
docker compose stop dibble
mkdir -p ../../proof-artifacts/manual-backup
docker compose cp dibble:/data/dibble.db ../../proof-artifacts/manual-backup/dibble.db
docker compose start dibble
```

Manual restore:

```bash
docker compose stop dibble
docker compose cp ../../proof-artifacts/manual-backup/dibble.db dibble:/data/dibble.db
docker compose start dibble
docker compose exec -u root dibble chown dibble:dibble /data/dibble.db
curl -sS http://localhost:8000/ready
```

After restore, call `GET /api/households/me/overview` with the parent key. The
household and learner ids should match the pre-restore proof report.

## Upgrade And Rollback

For a controlled pilot:

1. Back up `/data/dibble.db`.
2. Pull or build the new image.
3. Start the container and check `/ready`.
4. Review `/api/observability/readiness` from the operator surface.
5. If readiness fails or pilot stop conditions trigger, stop the new container and restart the previous image with the same `/data` volume.

Do not enable remote cloud-library publish or automatic migration execution during the first cohort unless the pilot runbook explicitly changes the rollout policy.
