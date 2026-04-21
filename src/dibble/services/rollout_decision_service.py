from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.models.rollout import (
    AssignmentUnit,
    BehaviorGate,
    EvaluationBucket,
    KillSwitchState,
    RolloutCapability,
    RolloutCapabilityDecision,
    RolloutCohort,
    RolloutInspection,
    RolloutPolicy,
    RolloutSubject,
    default_rollout_policy,
    stable_rollout_percent,
)
from dibble.services.protocols import RolloutPolicyStore, UserStore


@dataclass(slots=True)
class RolloutDecisionService:
    policy_store: RolloutPolicyStore
    user_store: UserStore | None = None

    def get_policy(self) -> RolloutPolicy:
        stored = self.policy_store.get()
        if stored is None:
            return default_rollout_policy()
        default_policy = default_rollout_policy()
        merged_gates = list(default_policy.behavior_gates)
        for gate in stored.behavior_gates:
            merged_gates = [
                existing
                for existing in merged_gates
                if existing.capability != gate.capability
            ]
            merged_gates.append(gate)
        return stored.model_copy(update={"behavior_gates": merged_gates})

    def update_policy(self, policy: RolloutPolicy) -> RolloutPolicy:
        return self.policy_store.upsert(
            policy.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        )

    def inspect_subject(
        self,
        *,
        learner_id: str | None = None,
        household_id: str | None = None,
    ) -> RolloutInspection:
        policy = self.get_policy()
        subject = self._resolve_subject(
            learner_id=learner_id,
            household_id=household_id,
        )
        cohorts = self._applicable_cohorts(policy=policy, subject=subject)
        bucket = self._bucket_for(policy=policy, subject=subject, cohorts=cohorts)
        decisions = [
            self._decision_for(
                policy=policy,
                subject=subject,
                capability=capability,
                cohorts=cohorts,
                bucket=bucket,
            )
            for capability in RolloutCapability
        ]
        return RolloutInspection(
            policy_id=policy.policy_id,
            subject=subject,
            cohort_ids=[cohort.cohort_id for cohort in cohorts],
            evaluation_bucket=bucket,
            decisions=decisions,
        )

    def decision_for(
        self,
        *,
        capability: RolloutCapability,
        learner_id: str | None = None,
        household_id: str | None = None,
    ) -> RolloutCapabilityDecision:
        inspection = self.inspect_subject(
            learner_id=learner_id,
            household_id=household_id,
        )
        decision = inspection.decision_for(capability)
        if decision is None:
            msg = f"Missing rollout decision for capability {capability.value}."
            raise LookupError(msg)
        return decision

    def evaluation_bucket_for(
        self,
        *,
        learner_id: str | None = None,
        household_id: str | None = None,
    ) -> EvaluationBucket | None:
        return self.inspect_subject(
            learner_id=learner_id,
            household_id=household_id,
        ).evaluation_bucket

    def list_cohorts(self) -> list[RolloutCohort]:
        return self.get_policy().cohorts

    def list_buckets(self) -> list[EvaluationBucket]:
        return self.get_policy().evaluation_buckets

    def list_kill_switches(self) -> list[KillSwitchState]:
        return self.get_policy().kill_switches

    def _resolve_subject(
        self,
        *,
        learner_id: str | None,
        household_id: str | None,
    ) -> RolloutSubject:
        resolved_household_id = household_id
        if resolved_household_id is None and learner_id is not None and self.user_store is not None:
            for user in self.user_store.list():
                if user.learner_id == learner_id and user.household_id is not None:
                    resolved_household_id = user.household_id
                    break
        return RolloutSubject(
            learner_id=learner_id,
            household_id=resolved_household_id,
        )

    def _applicable_cohorts(
        self,
        *,
        policy: RolloutPolicy,
        subject: RolloutSubject,
    ) -> list[RolloutCohort]:
        matched: list[RolloutCohort] = []
        for cohort in policy.cohorts:
            explicit_match = (
                (subject.learner_id is not None and subject.learner_id in cohort.learner_ids)
                or (
                    subject.household_id is not None
                    and subject.household_id in cohort.household_ids
                )
            )
            if explicit_match:
                matched.append(cohort)
                continue
            if cohort.rollout_percentage <= 0:
                continue
            assignment_key = subject.assignment_key(unit=cohort.assignment_unit)
            if assignment_key is None:
                continue
            rollout_value = stable_rollout_percent(
                salt=policy.assignment_salt,
                scope=f"cohort:{cohort.cohort_id}",
                assignment_key=assignment_key,
            )
            if rollout_value < cohort.rollout_percentage:
                matched.append(cohort)
        matched.sort(key=lambda item: item.cohort_id)
        return matched

    def _bucket_for(
        self,
        *,
        policy: RolloutPolicy,
        subject: RolloutSubject,
        cohorts: list[RolloutCohort],
    ) -> EvaluationBucket | None:
        if not policy.evaluation_buckets:
            return None
        pinned_bucket_ids = [
            cohort.pinned_evaluation_bucket_id
            for cohort in cohorts
            if cohort.pinned_evaluation_bucket_id
        ]
        if pinned_bucket_ids:
            pinned_bucket_id = sorted(pinned_bucket_ids)[0]
            return next(
                (
                    bucket
                    for bucket in policy.evaluation_buckets
                    if bucket.bucket_id == pinned_bucket_id
                ),
                None,
            )
        assignment_key = subject.assignment_key(unit=AssignmentUnit.learner) or subject.assignment_key(
            unit=AssignmentUnit.household
        )
        if assignment_key is None:
            return policy.evaluation_buckets[0]
        rollout_value = stable_rollout_percent(
            salt=policy.assignment_salt,
            scope="evaluation_bucket",
            assignment_key=assignment_key,
        )
        cursor = 0
        ordered = sorted(policy.evaluation_buckets, key=lambda item: item.bucket_id)
        for bucket in ordered:
            cursor += bucket.weight
            if rollout_value < cursor:
                return bucket
        return ordered[-1]

    def _decision_for(
        self,
        *,
        policy: RolloutPolicy,
        subject: RolloutSubject,
        capability: RolloutCapability,
        cohorts: list[RolloutCohort],
        bucket: EvaluationBucket | None,
    ) -> RolloutCapabilityDecision:
        base_gate = _gate_for(policy.behavior_gates, capability)
        if base_gate is None:
            msg = f"Missing rollout gate for capability {capability.value}."
            raise LookupError(msg)
        effective_gate = base_gate
        source = "policy"
        rationale = [f"base:{base_gate.mode_value()}"]
        applied_cohort_ids: list[str] = []
        for cohort in cohorts:
            override = _gate_for(cohort.behavior_overrides, capability)
            if override is None:
                continue
            effective_gate = override
            source = f"cohort:{cohort.cohort_id}"
            applied_cohort_ids.append(cohort.cohort_id)
            rationale.append(f"cohort:{cohort.cohort_id}:{override.mode_value()}")
        if bucket is not None:
            override = _gate_for(bucket.behavior_overrides, capability)
            if override is not None:
                effective_gate = override
                source = f"bucket:{bucket.bucket_id}"
                rationale.append(f"bucket:{bucket.bucket_id}:{override.mode_value()}")
        kill_switch = next(
            (
                item
                for item in policy.kill_switches
                if item.capability == capability and item.active
            ),
            None,
        )
        if kill_switch is not None:
            rationale.append(f"kill_switch:{kill_switch.reason or 'active'}")
            effective_gate = _disabled_gate_from(effective_gate)
            source = "kill_switch"
        return RolloutCapabilityDecision(
            capability=capability,
            enabled=effective_gate.enabled(),
            mode=effective_gate.mode_value(),
            fallback_behavior=effective_gate.fallback_behavior,
            effective_gate=effective_gate,
            source=source,
            source_cohort_ids=applied_cohort_ids,
            evaluation_bucket_id=bucket.bucket_id if bucket is not None else None,
            kill_switch_active=kill_switch is not None,
            kill_switch_reason=kill_switch.reason if kill_switch is not None else None,
            rationale=rationale,
        )


def _gate_for(
    gates: list[BehaviorGate],
    capability: RolloutCapability,
) -> BehaviorGate | None:
    return next((gate for gate in gates if gate.capability == capability), None)


def _disabled_gate_from(gate: BehaviorGate) -> BehaviorGate:
    replacements: dict[RolloutCapability, str] = {
        RolloutCapability.autonomous_session_suggestions: "disabled",
        RolloutCapability.parent_approval_enforcement: "strict",
        RolloutCapability.cloud_library_remote_read: "local_only",
        RolloutCapability.cloud_library_remote_publish: "local_only",
        RolloutCapability.non_text_modalities: "text_only",
        RolloutCapability.outcome_driven_adaptation: "off",
        RolloutCapability.migration_execution: "manual_only",
        RolloutCapability.autonomous_teacher_outbound_actions: "disabled",
    }
    payload = gate.model_dump(mode="json")
    payload["mode"] = replacements[gate.capability]
    return type(gate).model_validate(payload)
