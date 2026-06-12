# Pilot Operations Runbook

Operating cadence for the instrumented homeschool pilot (5–10 families,
Grades 4–6 math, 6–8 weeks). Complements `pilot-readiness.md` (launch
checklist) and `deploy/pilot/README.md` (hosting).

## Family onboarding script (one page)

1. Operator creates an invite: `POST /api/admin/guardian-invites` (or the
   staff console) and sends the code to the family.
2. Guardian opens the pilot URL → **Register with invite code** →
   `POST /api/auth/register-guardian`. They receive their sign-in credential —
   tell them to store it in a password manager; it is shown once.
3. Guardian creates 1–3 learner profiles (display name + grade only). Each
   learner receives a 3-word PIN. Write the PIN on a card for the learner.
4. Each learner completes placement (~15 minutes, 12–18 questions). The
   guardian sees the parent-readable placement report afterwards.
5. Administer the **pre-assessment** (fixed, human-authored — *not*
   system-generated) before the first real session.
6. Daily rhythm: learner signs in → **Start today's session** → works ~20
   minutes → **Finish today's session** → recap. Target ≥4 sessions/week.

## Weekly cadence

Every week, same day:

1. **Dashboard review** — `/staff/pilot` (`GET /api/admin/pilot-metrics`):
   - Sessions started/completed and return rate per learner (engagement
     criterion: ≥60% of intended sessions in weeks 3–6).
   - Mastery deltas per learner.
   - Verification failure count and defect reports (target: <1% of delivered
     items; **zero wrong answer keys**).
   - Production-vs-baseline agreement rate and divergence list.
   - Cost: tokens and latency per learner.
2. **Defect triage** — for each `content.defect.report` event: reproduce via
   the export of the `generation_id`, classify (wrong key / rendering /
   confusing wording / off-curriculum), patch corpus or prompt in the staging
   queue, close the loop with the family that reported it.
3. **Family check-in** (rotating, 10 minutes): one question each on
   friction, trust, and whether the learner asks to use it.

## Escalation path

- Intervention contract `escalate` decisions route to the operator. SLA:
  acknowledge within 24h, resolve or schedule within 72h.
- Wrong-answer-key reports are P0: pull the item from the cache
  (`generation_id`), verify the corpus entry, and respond to the family the
  same day.

## Mid-pilot patch window (week 3–4, once)

Batch corpus/prompt changes → deploy to staging → re-run synthetic personas
(`uv run pytest tests/test_placement.py tests/test_session_bookends.py
tests/test_math_verification.py`) → promote. No other deploys onto live
families.

## Data rights

- Export on request: `GET /api/admin/learners/{id}/export` → send the JSON to
  the guardian.
- Withdrawal: export first if requested, then
  `uv run python scripts/hard_delete_learner.py <student_id> --db /data/dibble.db`.

## Post-pilot (weeks 15–16)

Post-assessment, exit interviews, divergence analysis joined to
`progression.outcome` verdicts, and the written answers to the three
questions: did learning happen, did the machinery matter, would families
pay/stay.
