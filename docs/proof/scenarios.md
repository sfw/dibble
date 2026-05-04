# Canonical Proof Scenarios

The canonical proof scenarios live in `proof/scenarios/*.json` and are validated by `scripts/validate_proof_scenarios.py`.

Run:

```bash
uv run python scripts/validate_proof_scenarios.py
```

The validator enforces that every scenario has rehearsal steps, expected observations, success criteria, and an explicit privacy contract for model-provider and cloud-library flows.

## Scenario Set

1. `new_household_onboarding`
   - Proves a fresh household container can start, expose readiness, create an operator, create learners, and attach them to a parent-managed household.

2. `adaptive_modality_change`
   - Proves weak outcomes can lead to a visible backend-owned modality change or an explicit rollout fallback.

3. `parent_governed_autonomy`
   - Proves autonomous teacher suggestions are constrained by parent approvals and that approvals or rejections change the next state.

4. `cross_session_planning_revision`
   - Proves accumulated evidence across sessions can revise the active trajectory and make the revision inspectable.

5. `shared_library_reuse_without_privacy_leakage`
   - Proves curriculum-shaped artifacts can be reused without learner-private fields entering the shared-library contract.

## Rehearsal Rule

A scenario is not considered passed because an endpoint returns `200`. It is passed only when the expected observation is visible to a parent or operator and the privacy contract still holds.
