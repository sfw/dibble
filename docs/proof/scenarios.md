# Canonical Proof Scenarios

The canonical proof scenarios live in `proof/scenarios/*.json`. They are
validated by `scripts/validate_proof_scenarios.py` and rehearsed against the
household container with `scripts/rehearse_proof_scenarios.py`.

Validate the scenario assets:

```bash
uv run python scripts/validate_proof_scenarios.py
```

Run all five scenarios against a running household container:

```bash
uv run python scripts/rehearse_proof_scenarios.py --base-url http://localhost:8000
```

If the container already has an admin user, pass the saved operator key:

```bash
DIBBLE_PROOF_ADMIN_API_KEY=ADMIN_API_KEY \
  uv run python scripts/rehearse_proof_scenarios.py --base-url http://localhost:8000
```

Run one scenario:

```bash
uv run python scripts/rehearse_proof_scenarios.py \
  --base-url http://localhost:8000 \
  --admin-api-key ADMIN_API_KEY \
  --scenario adaptive_modality_change
```

The script seeds the runtime through public API paths only. It creates a parent,
two learners, proof curriculum, learner profiles, household preferences, and an
explicit first goal/trajectory. It does not require database edits.

## Seeded Runtime

Shared seed asset: `proof/fixtures/scenario_household_seed.json`.

Seeded participants:

- Parent: Morgan Proof Parent
- Learner A: Avery Proof Learner
- Learner B: Blair Proof Learner

Seeded curriculum target:

- Outcome: `PROOF-FRAC-2` / Equivalent Fraction Practice
- Primary KC: `KC-FRAC-EQUIV`
- Prerequisite KC: `KC-FRAC-FOUNDATION`
- Follow-on KC: `KC-FRAC-COMPARE`

The default proof posture matches the pilot posture: guided parent approvals,
remote cloud-library access disabled, local curriculum reuse active, and
non-text modalities available unless rollout policy disables them.

## Scenario Steps

### 1. New Household Onboarding

Setup:

```bash
uv run python scripts/rehearse_proof_scenarios.py \
  --base-url http://localhost:8000 \
  --scenario new_household_onboarding
```

Execution path:

- `GET /ready`
- `POST /api/setup/admin` when the runtime has no admin
- `POST /api/users` for parent and learners
- `PUT /api/households/me/setup`
- `POST /api/households/me/learners/{learner_id}/goals`
- `GET /api/households/me/overview`

Expected visible outcome: the parent overview shows the household, both learners,
guided approval posture, and first-session state. `/ready` remains operator
readable and explains whether the runtime is ready, degraded, or still in setup.

### 2. Adaptive Modality Change

Execution path:

- Generate baseline practice content for Avery.
- Record weak observations tied to the returned `generation_id`.
- Inspect modality routing for the same KC with a visual worked-example request.
- Generate the follow-up.
- Record improved observations.

Expected visible outcome: the follow-up changes modality, usually from text to
diagram, or the inspection explicitly shows rollout fallback to text.

Primary hooks:

- `POST /api/observability/adaptation/modality-routing/inspect`
- `POST /api/observability/adaptation/modality-routing/explain`
- `GET /api/admin/rollout/inspect`

### 3. Parent-Governed Autonomy

Execution path:

- `GET /api/households/me/overview` and copy a pending `approval_id`.
- `GET /api/households/me/approvals/{learner_id}/{approval_id}/preview`
- Reject the approval.
- Inspect autonomous-teacher explanation.
- Approve the same request.

Expected visible outcome: preview explains both branches, rejection keeps the
session suggestion blocked, and approval clears or reduces the blocker list.

Primary hooks:

- Parent approval preview, reject, and approve endpoints
- `GET /api/observability/adaptation/autonomous-teacher/{household_id}/{learner_id}/explain`
- `GET /api/observability/traces?harness=autonomous_teacher`

### 4. Cross-Session Planning Revision

Execution path:

- Inspect Avery's baseline planning state.
- Generate and observe repeated weak/strong attempts against `KC-FRAC-EQUIV`.
- Open or fetch the learner workspace to refresh active planning state.
- Inspect planning again.
- Review parent overview for any trajectory approval posture.

Expected visible outcome: the trajectory revision count, revisit density,
recovery scaffold, or adaptation rationale changes after accumulated evidence.
The change is visible through planning observability rather than frontend logic.

Primary hooks:

- `GET /api/observability/adaptation/planning/{student_id}`
- `GET /api/learners/{student_id}/workspace`
- `GET /api/households/me/overview`

### 5. Shared Library Reuse Without Privacy Leakage

Execution path:

- Generate a curriculum-shaped worked example for Avery.
- Generate the same curriculum-shaped request for Blair.
- Inspect the library privacy audit.
- Inspect content-library traces.

Expected visible outcome: Blair receives a cache/library hit. The privacy audit
reports no forbidden field hits and only sentinel student ids in reusable library
templates.

Primary hooks:

- `GET /api/observability/adaptation/library/privacy-audit`
- `POST /api/observability/adaptation/library/inspect`
- `GET /api/observability/traces?harness=content_library`

## Rehearsal Rule

A scenario is not considered passed because an endpoint returns `200`. It is
passed only when the expected observation is visible to a parent or operator and
the privacy contract still holds.
