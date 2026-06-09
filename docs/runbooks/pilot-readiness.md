# Pilot Readiness Runbook

This runbook defines the first supported pilot state: a small operator-managed household cohort.

## Default Pilot Posture

- Deployment: one household container per household.
- Persistence: SQLite mounted at `/data/dibble.db`.
- Auth: enabled.
- Telemetry: `normal`.
- Cloud-library remote read: off.
- Cloud-library remote publish: off.
- Parent approval: guided, with modality introduction, trajectory revision, and high-autonomy session approval enabled.
- Non-text modalities: available through rollout policy, with parent approval and kill-switch fallback.
- Outcome-driven adaptation: conservative.
- Curriculum migration execution: manual only.
- Autonomous outbound actions: in-product notifications only.

## Launch Checklist

- `/ready` has no failed checks.
- `/api/observability/readiness` has no unresolved degraded operations that affect the household.
- The household overview shows every pilot learner.
- Parent preferences are reviewed and match the consented pilot posture.
- A database backup has been taken before the first learner session.
- Operator has validated the five proof scenarios in `proof/scenarios`.
- Operator has run the live household proof against the Compose deployment:
  `uv run python scripts/live_household_proof.py --base-url http://localhost:8000 --compose-dir deploy/household --request-timeout-seconds 720 --require-real-provider`.
- The live proof report includes restart, backup, and restore evidence.
- Restore evidence includes corrected `/data/dibble.db` ownership for the
  non-root container user after the backup is copied back into the container.
- The live proof report includes multi-household evidence. The default live
  proof seeds a canonical household, a clean longitudinal household, and a
  varied operator-review household unless `--skip-multi-household-evidence` is
  passed.
- LLM provider credentials are real and `DIBBLE_LLM_ALLOW_MOCK_FALLBACK=false`
  for the final proof run. Mock fallback is acceptable only for dry-run
  rehearsal.
- Provider-specific LLM settings are recorded in the household `.env`; for
  high-latency real providers, review `DIBBLE_LLM_TIMEOUT_SECONDS`,
  `DIBBLE_LLM_TEMPERATURE`, `DIBBLE_LLM_MAX_TOKENS`, and
  `DIBBLE_LLM_THINKING_ENABLED` before learner use.
- For the Moonshot `kimi-k2.5` live proof posture, confirm
  `DIBBLE_LLM_TEMPERATURE=1.0`, do not disable thinking, and set
  `DIBBLE_LLM_RESPONSE_FORMAT_JSON=true` with a token budget such as
  `DIBBLE_LLM_MAX_TOKENS=8000` so thinking does not exhaust the final-answer
  budget.
- If the provider returns overload/rate-limit responses during live proof,
  configure bounded `DIBBLE_LLM_RETRY_BACKOFF_SECONDS` and
  `DIBBLE_LLM_RETRY_ATTEMPTS` instead of enabling mock fallback.
- Rollout kill switches are known and reachable from the operator surface.

## Daily Operator Review

- Check `/api/observability/readiness`.
- Review provider-health failures and degraded traces.
- Review pending parent approvals.
- Review stale autonomous suggestions.
- Review learner sessions that ended in repeated stall, high frustration, or fallback-only behavior.
- During proof rehearsal, compare the current review checkpoint with the previous checkpoint in the longitudinal report: readiness status, pending approvals, planning revision count, revisit density, recent signal count, and recent trace summaries should remain explainable.
- During live proof review, confirm the Markdown report lists the backup
  checksum and both restart and restore state-preservation checks.
- During human/operator review, ask whether each report count explains what to
  do next. Pending approvals are fine in guided mode; unclear approval previews,
  unexplained degraded traces, or ambiguous content-review actions are friction
  to fix or document.

## Weekly Operator Review

- Confirm backups exist and restore has been rehearsed at least once before the cohort starts.
- Confirm the latest `proof-artifacts/live-household-*` report is backed by a
  real-provider run, not a mock-backed dry run.
- Review modality outcomes by learner.
- Review whether any non-text modality caused repeated fallback or parent confusion.
- Review parent notifications and unresolved soft-escalations.
- Review whether trajectory revisions are understandable to parents.
- Review captured generated-content samples from the longitudinal report for curriculum fit, misconception targeting, age fit, and absence of learner-private fields.
- Record generated-content review notes using
  `docs/proof/content-quality-review.md`; use `pass`, `watch`, or `fail` for
  curriculum fit, misconception targeting, age fit, privacy, and actionability.

## Stop Conditions

Pause the pilot for a household if any of these occur:

- Learner-private fields appear in a cloud-library artifact, remote request, or operator export.
- `/ready` reports a database failure or persistence is not preserved across restart.
- Parent approval enforcement fails to block a gated autonomy action.
- A learner receives repeated content-generation failures with no clear fallback or operator trace.
- Sustained high frustration appears across sessions without a parent notification or soft-escalation.
- A rollout kill switch does not constrain the targeted capability.

## Success Criteria

The pilot is evidence-positive when:

- A parent can run the container and recover from restart without operator database edits.
- Each canonical scenario can be demonstrated with one pilot household or a seeded rehearsal household.
- At least one learner shows a visible adaptive modality change or a documented policy fallback.
- At least one parent approval changes an autonomous teacher action.
- Planning revision is inspectable after accumulated evidence.
- Shared-library reuse is demonstrated without learner-private leakage.
- A seeded longitudinal timeline demonstrates stall, constrained adaptation, planning review, parent approval decisions, recovery, repeated readiness review, and content-quality checkpoints without raw database inspection.
- The live household proof report demonstrates restart persistence, backup
  capture, restore execution, and post-restore overview verification.
- At least two household labels are present in restart/restore evidence before
  making a multi-household proof claim.

## Longitudinal Proof Criteria

The POC is stronger than demoable when these are true in a rehearsal household:

- A multi-session timeline can be run through public API paths only.
- Parent approval preview, rejection, and approval still change autonomous behavior after repeated learner sessions.
- Planning observability shows accumulated evidence through revision count, revisit density, recovery scaffolding, or recent signal summaries.
- `/ready`, `/api/observability/readiness`, approval previews, planning inspection, autonomous-teacher explanation, traces, and library privacy audit remain useful at multiple checkpoints.
- Operators can review generated sample metadata and notes for content quality without inspecting the database.
- Privacy audit stays clean after cross-learner reusable content is generated or reused.
- Restart and restore evidence are captured from the Compose household service,
  not inferred from a local seeded test harness.

Do not describe the POC as fully proven for unsupervised real-world parent use
until at least one non-scripted parent or operator can interpret the
longitudinal report, more than one household has rehearsed the flow, real
provider behavior has been observed, and generated content quality has been
reviewed over more than curated proof checkpoints. With the current proof
package, the honest claim is stronger but narrower: Dibble is credibly proven
for a small, operator-managed pilot rehearsal.

## Support Notes

- Use `/ready` for startup and configuration issues.
- Use `/api/observability/readiness` for operational degradation, blocked reviews, stale suggestions, and active kill switches.
- Use rollout policy first to narrow behavior. Use code changes only when a guardrail is missing.
- Preserve the mounted database before upgrades, migrations, and incident investigation.
