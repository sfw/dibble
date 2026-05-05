# Dibble Live Household Proof Report

- Generated: 2026-05-05T16:37:40.502391+00:00
- Base URL: http://127.0.0.1:8000
- Household ID: 321ca841-1122-4987-8f8d-56c3dd6887f0
- Run stamp: dc41e00a

## Readiness

- Status: ready
- Deployment mode: household_container
- LLM provider: pass (Primary LLM provider credentials are configured.)
- Mock fallback enabled: False
- Cloud library enabled: False

Proof households:
- canonical: 321ca841-1122-4987-8f8d-56c3dd6887f0
- longitudinal: 1bacc3ce-657a-4ca9-a237-7dca2e8dc2f2

## Canonical Scenarios

- new_household_onboarding: overview shows 4 learners and readiness is ready
- adaptive_modality_change: text -> diagram; inspected effective=diagram
- parent_governed_autonomy: rejected then approved modality_introduction; explanation=approval_blocked
- cross_session_planning_revision: revisions 4->5; revisit_density=2; nodes=['recovery_scaffold', 'instruction']
- shared_library_reuse_without_privacy_leakage: reuse_source generation=9f43a1bb-0eb6-40da-98ca-37beca84f99a; reuse_peer cache_hit=True; audit_entries=10

## Longitudinal Timelines

### Longitudinal fraction recovery household rehearsal

- day-0-baseline: ready=ready, approvals=5, planning_revisions=1, signals=0
  Proof signal: Governance was visible before learner delivery.
- session-1-stall: ready=ready, approvals=6, planning_revisions=3, signals=5
  Proof signal: Repeated weak observations created adaptation pressure and approval-gated recovery remained inspectable.
- session-2-recovery-plan: ready=ready, approvals=7, planning_revisions=4, signals=7
  Proof signal: Planning state changed after accumulated session evidence and remained readable from observability.
- session-3-recovery: ready=ready, approvals=7, planning_revisions=5, signals=7
  Proof signal: Recovery, proven cross-learner library reuse, readiness, traces, and privacy audit are inspectable without database access.

Content samples captured: 5
- session-1-stall/avery: 219e9111-103a-4766-b5bc-3657d255bf75 modality=text cache_hit=False
- session-2-recovery-plan/avery: 56485433-49ab-4ed2-8758-b21cffe44cb9 modality=diagram cache_hit=False
- session-3-recovery/avery: b76a93d1-8343-440f-b2fd-8c0b98966336 modality=text cache_hit=False
- session-3-recovery/reuse_source: 60d075c1-a54d-4d60-8512-585663d18f09 modality=diagram cache_hit=False
- session-3-recovery/reuse_peer: 4ed14d88-e3fb-42ae-9f0e-6656ec63f112 modality=diagram cache_hit=True
Privacy audit: entries=19, forbidden_hits=0

## Live Container Evidence

- Restart preserved household state: True
- Backup: /Users/sfw/Development/dibble/proof-artifacts/live-household-real-provider-2026-05-04/dibble-live-household-backup.db (2236416 bytes, sha256=641ae84dc18972339693182696d4423f70982c98c26e259cd3a6f5bcbf23609e)
- Restore preserved household state: True
- Post-restore readiness: ready

## Operator Review Checklist

- Confirm `/ready` is acceptable for the intended run posture.
- Confirm real-provider proof has mock fallback disabled.
- Review generated content samples for curriculum fit and privacy.
- Confirm restart and restore evidence are present before learner use.
