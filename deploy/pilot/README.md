# Dibble pilot deployment

Single hosted instance for the homeschool pilot: FastAPI + SQLite (WAL)
behind Caddy with automatic TLS, plus a nightly backup sidecar. No heroics by
design — ≤10 families is well within SQLite's envelope.

## Bring-up

```bash
cd deploy/pilot
cp .env.example .env        # fill in domain, auth secret, LLM key
docker compose up -d --build
curl -fsS https://<your-domain>/ready | jq .   # must report "ready"
```

`GET /ready` enforces the production guards: auth enabled with a real token
secret, an LLM key present, and mock fallback **disabled** (a silent mock
fallback mid-pilot corrupts pilot data while looking like uptime).

## Corpus load

```bash
docker compose exec dibble /app/.venv/bin/python \
  scripts/ingest_curriculum.py data/curriculum/grade4_math.json \
  data/curriculum/grade5_math.json data/curriculum/grade6_math.json \
  --db /data/dibble.db
```

(Or run the ingestion locally against a copy and ship the DB before launch.)

## Backups

The `backup` service runs `scripts/backup_database.sh` nightly at 02:15 UTC:
an online `sqlite3 .backup` (safe under WAL), gzip, 14-snapshot rotation in
the `dibble-pilot-backups` volume. Set `DIBBLE_BACKUP_REMOTE` to rsync each
snapshot off-host. Restore: stop the stack, gunzip a snapshot over
`/data/dibble.db` in the data volume, start the stack.

## Monitoring

- Uptime: poll `GET /health` (any uptime monitor; alert on non-200).
- Provider health: `GET /api/observability/metrics` exposes provider
  telemetry — alert on circuit-open events.
- Weekly pilot review: `/staff/pilot` dashboard (admin login), backed by
  `GET /api/admin/pilot-metrics`.

## Staging

Run a second copy of this stack on a different host/port with the mock
provider for rehearsing changes before they touch pilot families:

```bash
docker compose -p dibble-staging up -d --build
# In the staging .env: leave DIBBLE_LLM_API_KEY empty and set
# DIBBLE_LLM_ALLOW_MOCK_FALLBACK=true — /ready will report "degraded",
# which is correct for staging.
```

Mid-pilot patches: batch changes, verify on staging with the synthetic
personas (`uv run pytest tests/test_placement.py tests/test_session_bookends.py`),
then promote in the single mid-pilot patch window — no continuous deployment
onto live families.
