from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.models.rollout import (
    AssignmentUnit,
    BehaviorGate,
    CapabilityDecisionDelta,
    CapabilityDeltaSummary,
    EvaluationBucket,
    KillSwitchState,
    RolloutCapability,
    RolloutCapabilityDecision,
    RolloutCohort,
    RolloutInspection,
    RolloutPolicy,
    RolloutSimulationDiff,
    RolloutSimulationRequest,
    RolloutSimulationResponse,
    RolloutSimulationSubject,
    RolloutSubject,
    SimulationSummary,
    default_rollout_policy,
    stable_rollout_percent,
)
from dibble.services.protocols import RolloutPolicyStore, UserStore

_RISKY_CAPABILITIES = frozenset(
    {
        RolloutCapability.autonomous_session_suggestions,
        RolloutCapability.cloud_library_remote_read,
        RolloutCapability.cloud_library_remote_publish,
        RolloutCapability.non_text_modalities,
        RolloutCapability.outcome_driven_adaptation,
        RolloutCapability.migration_execution,
        RolloutCapability.autonomous_teacher_outbound_actions,
    }
)


@dataclass(slots=True)
class RolloutDecisionService:
    policy_store: RolloutPolicyStore
    user_store: UserStore | None = None

    def get_policy(self) -> RolloutPolicy:
        stored = self.policy_store.get()
        if stored is None:
            return default_rollout_policy()
        return self._merged_with_default(stored)

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
        return self._inspect_subject_for_policy(
            policy=self.get_policy(),
            learner_id=learner_id,
            household_id=household_id,
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

    def simulate_policy_change(
        self,
        request: RolloutSimulationRequest,
    ) -> RolloutSimulationResponse:
        current_policy = self.get_policy()
        proposed_policy = self._merged_with_default(request.proposed_policy)
        subjects = self._simulation_subjects(request.subjects)
        diffs: list[RolloutSimulationDiff] = []
        capability_change_counts: dict[str, int] = {}
        capability_new_risk_counts: dict[RolloutCapability, int] = {}
        changed_learner_ids: set[str] = set()
        changed_household_ids: set[str] = set()
        newly_risky_subject_keys: set[tuple[str | None, str | None]] = set()

        for simulation_subject in subjects:
            current_inspection = self._inspect_subject_for_policy(
                policy=current_policy,
                learner_id=simulation_subject.learner_id,
                household_id=simulation_subject.household_id,
            )
            proposed_inspection = self._inspect_subject_for_policy(
                policy=proposed_policy,
                learner_id=simulation_subject.learner_id,
                household_id=simulation_subject.household_id,
            )
            capability_deltas = [
                self._decision_delta(
                    current=current_inspection.decision_for(capability),
                    proposed=proposed_inspection.decision_for(capability),
                )
                for capability in RolloutCapability
            ]
            cohort_changed = current_inspection.cohort_ids != proposed_inspection.cohort_ids
            current_bucket_id = (
                current_inspection.evaluation_bucket.bucket_id
                if current_inspection.evaluation_bucket is not None
                else None
            )
            proposed_bucket_id = (
                proposed_inspection.evaluation_bucket.bucket_id
                if proposed_inspection.evaluation_bucket is not None
                else None
            )
            evaluation_bucket_changed = current_bucket_id != proposed_bucket_id
            changed = cohort_changed or evaluation_bucket_changed or any(
                delta.changed for delta in capability_deltas
            )
            if not changed and not request.include_unchanged:
                continue

            newly_risky_capabilities = [
                delta.capability
                for delta in capability_deltas
                if delta.newly_exposed_to_risky_capability
            ]
            if changed:
                if simulation_subject.learner_id is not None:
                    changed_learner_ids.add(simulation_subject.learner_id)
                if simulation_subject.household_id is not None:
                    changed_household_ids.add(simulation_subject.household_id)
            if newly_risky_capabilities:
                newly_risky_subject_keys.add(
                    (simulation_subject.learner_id, simulation_subject.household_id)
                )
            for delta in capability_deltas:
                if not delta.changed:
                    continue
                capability_change_counts[delta.capability.value] = (
                    capability_change_counts.get(delta.capability.value, 0) + 1
                )
                if delta.newly_exposed_to_risky_capability:
                    capability_new_risk_counts[delta.capability] = (
                        capability_new_risk_counts.get(delta.capability, 0) + 1
                    )

            diffs.append(
                RolloutSimulationDiff(
                    subject=simulation_subject,
                    current_inspection=current_inspection,
                    proposed_inspection=proposed_inspection,
                    cohort_changed=cohort_changed,
                    evaluation_bucket_changed=evaluation_bucket_changed,
                    newly_risky_capabilities=newly_risky_capabilities,
                    capability_deltas=capability_deltas,
                )
            )

        changed_subject_count = sum(
            1
            for diff in diffs
            if diff.cohort_changed
            or diff.evaluation_bucket_changed
            or any(delta.changed for delta in diff.capability_deltas)
        )
        top_capability_deltas = [
            CapabilityDeltaSummary(
                capability=capability,
                affected_subject_count=capability_change_counts.get(capability.value, 0),
                newly_risky_subject_count=capability_new_risk_counts.get(capability, 0),
            )
            for capability in RolloutCapability
            if capability_change_counts.get(capability.value, 0) > 0
        ]
        top_capability_deltas.sort(
            key=lambda item: (
                item.affected_subject_count,
                item.newly_risky_subject_count,
                item.capability.value,
            ),
            reverse=True,
        )
        return RolloutSimulationResponse(
            current_policy_id=current_policy.policy_id,
            proposed_policy_id=proposed_policy.policy_id,
            summary=SimulationSummary(
                total_subject_count=len(subjects),
                changed_subject_count=changed_subject_count,
                changed_learner_count=len(changed_learner_ids),
                changed_household_count=len(changed_household_ids),
                newly_risky_subject_count=len(newly_risky_subject_keys),
                capability_change_counts=dict(sorted(capability_change_counts.items())),
                top_capability_deltas=top_capability_deltas,
            ),
            diffs=diffs,
        )

    def _merged_with_default(self, policy: RolloutPolicy) -> RolloutPolicy:
        default_policy = default_rollout_policy()
        merged_gates = list(default_policy.behavior_gates)
        for gate in policy.behavior_gates:
            merged_gates = [
                existing
                for existing in merged_gates
                if existing.capability != gate.capability
            ]
            merged_gates.append(gate)
        return policy.model_copy(update={"behavior_gates": merged_gates})

    def _inspect_subject_for_policy(
        self,
        *,
        policy: RolloutPolicy,
        learner_id: str | None,
        household_id: str | None,
    ) -> RolloutInspection:
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

    def _simulation_subjects(
        self,
        subjects: list[RolloutSimulationSubject],
    ) -> list[RolloutSimulationSubject]:
        if subjects:
            return [
                self._resolve_simulation_subject(subject)
                for subject in subjects
            ]
        if self.user_store is None:
            return []
        resolved: list[RolloutSimulationSubject] = []
        for user in sorted(
            self.user_store.list(),
            key=lambda item: (
                item.display_name or "",
                item.learner_id or "",
                item.household_id or "",
                item.user_id,
            ),
        ):
            if user.learner_id is None:
                continue
            resolved.append(
                self._resolve_simulation_subject(
                    RolloutSimulationSubject(
                        learner_id=user.learner_id,
                        household_id=user.household_id,
                        label=user.display_name or user.learner_id,
                    )
                )
            )
        deduped: dict[tuple[str | None, str | None], RolloutSimulationSubject] = {}
        for subject in resolved:
            deduped[(subject.learner_id, subject.household_id)] = subject
        return list(deduped.values())

    def _resolve_simulation_subject(
        self,
        subject: RolloutSimulationSubject,
    ) -> RolloutSimulationSubject:
        resolved = self._resolve_subject(
            learner_id=subject.learner_id,
            household_id=subject.household_id,
        )
        label = subject.label
        if label is None and self.user_store is not None and resolved.learner_id is not None:
            for user in self.user_store.list():
                if user.learner_id == resolved.learner_id:
                    label = user.display_name or user.learner_id
                    break
        return RolloutSimulationSubject(
            learner_id=resolved.learner_id,
            household_id=resolved.household_id,
            label=label,
        )

    def _decision_delta(
        self,
        *,
        current: RolloutCapabilityDecision | None,
        proposed: RolloutCapabilityDecision | None,
    ) -> CapabilityDecisionDelta:
        if current is None or proposed is None:
            msg = "Rollout simulation requires both current and proposed decisions."
            raise LookupError(msg)
        changed_fields: list[str] = []
        if current.enabled != proposed.enabled:
            changed_fields.append("enabled")
        if current.mode != proposed.mode:
            changed_fields.append("mode")
        if current.source != proposed.source:
            changed_fields.append("source")
        if current.fallback_behavior != proposed.fallback_behavior:
            changed_fields.append("fallback_behavior")
        if current.evaluation_bucket_id != proposed.evaluation_bucket_id:
            changed_fields.append("evaluation_bucket_id")
        if current.source_cohort_ids != proposed.source_cohort_ids:
            changed_fields.append("source_cohort_ids")
        if current.kill_switch_active != proposed.kill_switch_active:
            changed_fields.append("kill_switch")
        newly_exposed = (
            proposed.capability in _RISKY_CAPABILITIES
            and proposed.enabled
            and (
                not current.enabled
                or current.mode != proposed.mode
                or current.source != proposed.source
            )
        )
        return CapabilityDecisionDelta(
            capability=current.capability,
            current_decision=current,
            proposed_decision=proposed,
            changed=bool(changed_fields),
            changed_fields=changed_fields,
            fallback_changed=current.fallback_behavior != proposed.fallback_behavior,
            newly_exposed_to_risky_capability=newly_exposed,
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
