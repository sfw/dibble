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

## Backup And Restore

For the proof deployment, the backup unit is `/data/dibble.db`.

Stop the container before copying the database:

```bash
docker compose stop dibble
docker run --rm -v deploy_dibble-household-data:/data -v "$PWD":/backup busybox \
  cp /data/dibble.db /backup/dibble-backup.db
docker compose start dibble
```

Restore by stopping the service, replacing `/data/dibble.db`, and starting the service again. Verify `/ready` and the household overview immediately after restore.

## Upgrade And Rollback

For a controlled pilot:

1. Back up `/data/dibble.db`.
2. Pull or build the new image.
3. Start the container and check `/ready`.
4. Review `/api/observability/readiness` from the operator surface.
5. If readiness fails or pilot stop conditions trigger, stop the new container and restart the previous image with the same `/data` volume.

Do not enable remote cloud-library publish or automatic migration execution during the first cohort unless the pilot runbook explicitly changes the rollout policy.
