# Live Household Proof Procedure

This is the operator-facing proof run for the household-container deployment.
It runs against the real Docker Compose household service, uses public API paths
for learning proof, and captures restart, backup, and restore evidence for
handoff review.

## Preconditions

- `deploy/household/.env` exists and the container starts with
  `docker compose up --build`.
- `DIBBLE_LLM_API_KEY` and `DIBBLE_LLM_MODEL` are set for a real provider-backed
  proof.
- `DIBBLE_LLM_ALLOW_MOCK_FALLBACK=false` for the final live proof run. Leave it
  `true` only for dry-run rehearsal.
- Provider-specific generation settings are explicit when needed. The Moonshot
  `kimi-k2.5` live proof uses `DIBBLE_LLM_TEMPERATURE=1.0`, keeps thinking
  enabled with `DIBBLE_LLM_THINKING_ENABLED=true` or leaves the setting
  omitted, and sets bounded `DIBBLE_LLM_TIMEOUT_SECONDS` and
  `DIBBLE_LLM_MAX_TOKENS` values. Moonshot rejects `temperature=1.0` when
  thinking is explicitly disabled. The Moonshot proof path also sets
  `DIBBLE_LLM_RESPONSE_FORMAT_JSON=true` so generated content stays on Dibble's
  structured JSON contract. The `kimi-k2.5` live proof used
  `DIBBLE_LLM_TIMEOUT_SECONDS=300`, `DIBBLE_LLM_RETRY_BACKOFF_SECONDS=20`,
  `DIBBLE_LLM_RETRY_ATTEMPTS=6`, and `DIBBLE_LLM_MAX_TOKENS=8000`.
- `/data` is mounted through the Compose service volume.
- The operator has the initial admin API key, or the runtime has no admin yet.

## Run The Live Proof

From the repository root:

```bash
uv run python scripts/live_household_proof.py \
  --base-url http://localhost:8000 \
  --compose-dir deploy/household \
  --request-timeout-seconds 720 \
  --require-real-provider
```

If an admin already exists:

```bash
DIBBLE_PROOF_ADMIN_API_KEY=ADMIN_API_KEY \
  uv run python scripts/live_household_proof.py \
  --base-url http://localhost:8000 \
  --compose-dir deploy/household \
  --request-timeout-seconds 720 \
  --require-real-provider
```

The script:

- seeds a canonical proof household through public API paths
- runs the five canonical proof scenarios
- seeds a second longitudinal proof household in the same container so the
  multi-session timeline starts from clean planning state
- runs the `longitudinal_fraction_recovery` timeline against that same live
  container deployment
- restarts the Compose service and verifies household state is still present
- stops the service, copies `/data/dibble.db` to the artifact directory, copies
  it back, restarts the service, fixes restored database ownership for the
  non-root `dibble` runtime user, and verifies household state again
- writes JSON and Markdown proof reports under `proof-artifacts/`

Use `--artifact-dir PATH` to choose a specific handoff directory.

## Artifacts

Each run writes:

- `live-household-proof-report.json`: machine-readable proof evidence
- `live-household-proof-report.md`: operator review report
- `dibble-live-household-backup.db`: SQLite backup captured from `/data/dibble.db`

The Markdown report is the review artifact. It summarizes readiness, provider
posture, scenario results, longitudinal checkpoints, generated sample metadata,
privacy-audit results, restart preservation, backup checksum, and restore
verification.

## Dry Run

For a dry run before real provider credentials are available, omit
`--require-real-provider`. The report will still show whether mock fallback was
enabled. Do not use a mock-backed report as final live household proof.

To exercise API proof only without restarting or copying the database:

```bash
uv run python scripts/live_household_proof.py --skip-container-ops
```

This is useful for debugging proof scenarios, but it does not satisfy the live
household proof definition because restart and restore are not exercised.
