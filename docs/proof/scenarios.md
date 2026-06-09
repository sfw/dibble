# Canonical Proof Scenarios

The canonical proof scenarios live in `proof/scenarios/*.json`. They are
validated by `scripts/validate_proof_scenarios.py` and rehearsed against the
household container with `scripts/rehearse_proof_scenarios.py`.

Longitudinal proof timelines live in `proof/timelines/*.json`. They reuse the
same seeded household and public API rehearsal runner, but organize the proof as
multiple parent/operator review checkpoints over repeated learner sessions.

Validate the scenario assets:

```bash
uv run python scripts/validate_proof_scenarios.py
```

Run all five scenarios against a running household container:

```bash
uv run python scripts/rehearse_proof_scenarios.py --base-url http://localhost:8000
```

Run the longitudinal recovery timeline and write an operator review report:

```bash
uv run python scripts/rehearse_proof_scenarios.py \
  --base-url http://localhost:8000 \
  --timeline longitudinal_fraction_recovery \
  --summary-file proof-longitudinal-report.json \
  --operator-report-file proof-longitudinal-report.md
```

When `--timeline` is provided without `--scenario`, the runner executes the
timeline only. Pass both flags when you want a single run to include selected
canonical scenarios and the longitudinal timeline.

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
multiple proof learners, proof curriculum, learner profiles, household
preferences, and an explicit first goal/trajectory. It does not require
database edits.

For the live household proof milestone, use
`scripts/live_household_proof.py` instead of the lower-level rehearsal command.
That wrapper runs these scenarios and the longitudinal timeline against the real
Compose household service, then captures restart, backup, and restore evidence
in the same operator report. See `docs/proof/live-household-proof.md`.

## Seeded Runtime

Shared seed asset: `proof/fixtures/scenario_household_seed.json`.

Additional multi-household proof seed:
`proof/fixtures/operator_household_seed.json`. The live proof runner uses this
by default to exercise a varied operator-review household after the canonical
and longitudinal households. It keeps the same proof curriculum so scenario
assertions remain comparable, but varies names, learner profiles, grade mix,
household cadence, and preference posture enough to show the proof is not only
the first household's exact state path.

Seeded participants:

- Parent: Morgan Proof Parent
- Learner A: Avery Proof Learner
- Learner B: Blair Proof Learner
- Reuse source: Riley Reuse Source
- Reuse peer: Quinn Reuse Peer

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

- Generate a curriculum-shaped worked example for Riley Reuse Source.
- Generate the same curriculum-shaped request for Quinn Reuse Peer.
- Inspect the library privacy audit.
- Inspect content-library traces.

Expected visible outcome: Quinn receives a cache/library hit from Riley's
matching request. Avery and Blair keep their intentionally different adaptive
profiles for the longitudinal proof, while the reuse pair has identical
curriculum-routing state so the cache-hit assertion proves cross-learner
curriculum reuse rather than learner-specific route coincidence. The privacy
audit reports no forbidden field hits and only sentinel student ids in reusable
library templates.

Primary hooks:

- `GET /api/observability/adaptation/library/privacy-audit`
- `POST /api/observability/adaptation/library/inspect`
- `GET /api/observability/traces?harness=content_library`

## Rehearsal Rule

A scenario is not considered passed because an endpoint returns `200`. It is
passed only when the expected observation is visible to a parent or operator and
the privacy contract still holds.

## Longitudinal Timeline

The first longitudinal proof asset is
`proof/timelines/longitudinal_fraction_recovery.json`.

Narrative:

- Day 0: Morgan reviews the seeded household, pending approvals, `/ready`, and
  `/api/observability/readiness` before learner work begins. One gated
  autonomous action is previewed and rejected to prove the block matters.
- Session 1: Avery receives equivalent-fraction practice and records repeated
  weak outcomes. The operator inspects modality routing, readiness, pending
  approvals, planning state, and the first content-quality sample.
- Session 2: Avery receives a recovery step with visual-model context. Mixed
  weak/strong evidence is recorded, planning is refreshed, remaining approvals
  are previewed and approved, and the trajectory review must show accumulated
  evidence, revision, or revisit-density change.
- Session 3: Avery records a strong follow-up, then generates a curriculum-shaped
  worked example with the same reusable request Blair will make. Blair's matching
  request must return a cache/library hit. The operator reviews readiness, recent
  traces, generated samples, and the library privacy audit.

The timeline report captures, per phase:

- deployment readiness status
- release-readiness degraded trace count and pending review queues
- blocked review preview count
- pending approval and session suggestion counts
- planning revision count, revisit density, and recent signal count
- autonomous-teacher blockers
- recent trace summaries
- parent approval decisions
- content-quality sample metadata
- Quinn cache/library hit status for the reused sample
- library privacy audit summary
- structured content-review categories for each captured sample

Longitudinal proof passes only when the timeline can be rehearsed without
database edits, the review surfaces remain understandable across repeated
sessions, planning/adaptation evidence changes over time, parent approval
decisions remain enforceable, Quinn's reused sample reports a cache/library hit,
captured content samples are reviewable, and the privacy audit remains clean
after cross-learner reuse.

Use `docs/proof/content-quality-review.md` to turn sample capture into repeatable
human review notes. Capturing samples alone is not enough for the final proof
package; an operator should record what looked acceptable, questionable, or
blocking.

This is still not full controlled-pilot confidence. Before calling the POC fully
proven, we still need non-scripted parent comprehension checks, more than one
household, real provider behavior under pilot load, and sustained review of
generated content quality beyond curated checkpoints.
