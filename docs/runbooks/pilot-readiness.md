# Pilot Readiness Runbook

This runbook defines the first supported pilot state: a small operator-managed household cohort.

## Default Pilot Posture

- Deployment: one household container per household.
- Persistence: SQLite mounted at `/data/dibble.db`.
- Auth: enabled.
- Telemetry: `normal`.
- Cloud-library remote read: off.
- Cloud-library remote publish: off.
- Parent approval: guided, with modality introduction and trajectory revision approval enabled.
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
- LLM provider credentials are real; mock fallback is acceptable only for rehearsal.
- Rollout kill switches are known and reachable from the operator surface.

## Daily Operator Review

- Check `/api/observability/readiness`.
- Review provider-health failures and degraded traces.
- Review pending parent approvals.
- Review stale autonomous suggestions.
- Review learner sessions that ended in repeated stall, high frustration, or fallback-only behavior.

## Weekly Operator Review

- Confirm backups exist and restore has been rehearsed at least once before the cohort starts.
- Review modality outcomes by learner.
- Review whether any non-text modality caused repeated fallback or parent confusion.
- Review parent notifications and unresolved soft-escalations.
- Review whether trajectory revisions are understandable to parents.

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

## Support Notes

- Use `/ready` for startup and configuration issues.
- Use `/api/observability/readiness` for operational degradation, blocked reviews, stale suggestions, and active kill switches.
- Use rollout policy first to narrow behavior. Use code changes only when a guardrail is missing.
- Preserve the mounted database before upgrades, migrations, and incident investigation.
