# Dibble Live Household Proof Report

- Generated: 2026-05-04T17:42:18.486260+00:00
- Base URL: http://localhost:8000
- Household ID: 0ba6e6e1-b6cf-4d2a-8d66-e5f4b6b03cdc
- Run stamp: 1fe02c25

## Readiness

- Status: degraded
- Deployment mode: household_container
- LLM provider: warn (No LLM key is configured; deterministic mock fallback is active.)
- Mock fallback enabled: True
- Cloud library enabled: False
- Warning checks: llm_provider

Next steps from `/ready`:
- Configure a real LLM provider before running pilot learners.

Proof households:
- canonical: 0ba6e6e1-b6cf-4d2a-8d66-e5f4b6b03cdc
- longitudinal: 73396090-8971-407b-9697-6560903f1a7a

## Canonical Scenarios

- new_household_onboarding: overview shows 4 learners and readiness is degraded
- adaptive_modality_change: text -> diagram; inspected effective=diagram
- parent_governed_autonomy: rejected then approved modality_introduction; explanation=approval_blocked
- cross_session_planning_revision: revisions 4->5; revisit_density=2; nodes=['recovery_scaffold', 'instruction']
- shared_library_reuse_without_privacy_leakage: reuse_source generation=612fc89c-73e3-40d2-bc7f-a8360cb0323b; reuse_peer cache_hit=True; audit_entries=10

## Longitudinal Timelines

### Longitudinal fraction recovery household rehearsal

- day-0-baseline: ready=degraded, approvals=5, planning_revisions=1, signals=0
  Proof signal: Governance was visible before learner delivery.
- session-1-stall: ready=degraded, approvals=6, planning_revisions=3, signals=5
  Proof signal: Repeated weak observations created adaptation pressure and approval-gated recovery remained inspectable.
- session-2-recovery-plan: ready=degraded, approvals=7, planning_revisions=4, signals=7
  Proof signal: Planning state changed after accumulated session evidence and remained readable from observability.
- session-3-recovery: ready=degraded, approvals=7, planning_revisions=5, signals=7
  Proof signal: Recovery, proven cross-learner library reuse, readiness, traces, and privacy audit are inspectable without database access.

Content samples captured: 5
- session-1-stall/avery: f45101e0-8808-4e64-a6a9-45157d9a97d6 modality=text cache_hit=False
- session-2-recovery-plan/avery: 07dec95d-01c3-4b98-b823-5014db058986 modality=diagram cache_hit=False
- session-3-recovery/avery: b7d900c9-d51e-4d95-8260-ef8e925f9337 modality=text cache_hit=False
- session-3-recovery/reuse_source: c278c709-aa32-46d3-adfa-c9fa99f5ad4b modality=diagram cache_hit=False
- session-3-recovery/reuse_peer: dc1d1632-879b-4ecd-8243-34dbb5ab4778 modality=diagram cache_hit=True
Privacy audit: entries=19, forbidden_hits=0

## Live Container Evidence

- Restart preserved household state: True
- Backup: /Users/sfw/Development/dibble/proof-artifacts/live-household-dry-run/dibble-live-household-backup.db (2060288 bytes, sha256=6a9d4537a605c1a6aa5938de12bce335b841879493bf63f39188f6a08ec7466d)
- Restore preserved household state: True
- Post-restore readiness: degraded

## Operator Review Checklist

- Confirm `/ready` is acceptable for the intended run posture.
- Confirm real-provider proof has mock fallback disabled.
- Review generated content samples for curriculum fit and privacy.
- Confirm restart and restore evidence are present before learner use.
