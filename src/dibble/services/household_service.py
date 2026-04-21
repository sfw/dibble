from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.models.auth import User
from dibble.models.household import (
    Household,
    HouseholdLearnerOverview,
    HouseholdNotificationSnoozeRequest,
    HouseholdOverview,
    ParentApprovalStatus,
    ParentApprovalType,
    HouseholdPreferenceUpdateRequest,
    HouseholdSessionSuggestionSnoozeRequest,
    HouseholdSetupRequest,
    HouseholdSetupResponse,
    ParentProfile,
)
from dibble.models.observability import HarnessBoundary, OperationalTraceStatus
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.autonomous_teacher_harness import AutonomousTeacherHarness
from dibble.services.protocols import (
    AuditStore,
    HouseholdStore,
    ParentNotificationStore,
    UserStore,
)


@dataclass(slots=True)
class HouseholdService:
    household_store: HouseholdStore
    user_store: UserStore
    autonomous_teacher_harness: AutonomousTeacherHarness
    parent_notification_store: ParentNotificationStore
    audit_store: AuditStore | None = None
    operational_observability_service: OperationalObservabilityService | None = None

    def setup_household(
        self,
        *,
        parent_user_id: str,
        request: HouseholdSetupRequest,
    ) -> HouseholdSetupResponse:
        user = self.user_store.get(parent_user_id)
        if user is None:
            raise RuntimeError("Parent user not found.")
        if user.role not in {"parent", "household_admin", "admin"}:
            raise RuntimeError("User is not allowed to manage a household.")
        existing = self._household_for_user(user)
        learner_ids = self._validated_learner_ids(
            learner_ids=request.learner_ids,
            existing_household_id=existing.household_id if existing is not None else None,
        )
        now = datetime.now(timezone.utc)
        existing_profiles = (
            {profile.parent_user_id: profile for profile in existing.parent_profiles}
            if existing is not None
            else {}
        )
        existing_profiles[parent_user_id] = ParentProfile(
            parent_user_id=parent_user_id,
            display_name=user.display_name,
            relationship_label=request.relationship_label,
            preferences=request.preferences,
        )
        household = Household(
            household_id=existing.household_id if existing is not None else str(uuid4()),
            household_name=request.household_name,
            parent_profiles=list(existing_profiles.values()),
            learner_ids=learner_ids,
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
        )
        self.household_store.upsert(household)
        updated_user = user.model_copy(
            update={"household_id": household.household_id, "updated_at": now.isoformat()}
        )
        self.user_store.update(updated_user)
        self._sync_learner_membership(
            household_id=household.household_id,
            previous_learner_ids=existing.learner_ids if existing is not None else [],
            learner_ids=learner_ids,
            updated_at=now.isoformat(),
        )
        return HouseholdSetupResponse(household=household)

    def get_household_overview(self, *, parent_user_id: str) -> HouseholdOverview:
        return self.get_household_overview_at(parent_user_id=parent_user_id)

    def get_household_overview_at(
        self,
        *,
        parent_user_id: str,
        now: datetime | None = None,
    ) -> HouseholdOverview:
        user = self.user_store.get(parent_user_id)
        if user is None:
            raise RuntimeError("Parent user not found.")
        household = self._household_for_user(user)
        reference_time = now or datetime.now(timezone.utc)
        available_learners = [
            {
                "learner_id": item.learner_id,
                "display_name": item.display_name,
            }
            for item in self.user_store.list()
            if item.role == "learner"
            and item.learner_id is not None
            and (item.household_id is None or household is None or item.household_id == household.household_id)
        ]
        if household is None:
            return HouseholdOverview(available_learners=available_learners)
        orchestration = self.autonomous_teacher_harness.orchestrate_household(
            household=household,
            now=reference_time,
        )
        learners = [
            HouseholdLearnerOverview(
                learner_id=plan.learner_id,
                learner_label=plan.learner_label,
                grade_level=plan.grade_level,
                goal_title=plan.goal_title,
                mastery_ratio=plan.mastery_ratio,
                engagement=plan.relationship_state.engagement_status,
                frustration=plan.relationship_state.frustration_status,
                current_stage=plan.relationship_state.cadence_status,
                next_session_focus=plan.relationship_state.next_session_focus,
                suggested_modality=plan.relationship_state.suggested_modality or "text",
                cadence_decision=plan.cadence_decision,
                soft_escalation_active=plan.relationship_state.soft_escalation_active,
                summary_headline=plan.relationship_state.summary_headline,
                pending_approval_count=len(
                    [
                        approval
                        for approval in plan.relationship_state.approval_requests
                        if approval.status == ParentApprovalStatus.pending
                    ]
                ),
            )
            for plan in orchestration.learner_plans
        ]
        return HouseholdOverview(
            household=household,
            learners=learners,
            session_suggestions=[
                plan.next_session
                for plan in orchestration.learner_plans
                if plan.next_session is not None
            ],
            weekly_summaries=[
                plan.weekly_summary
                for plan in orchestration.learner_plans
                if plan.weekly_summary is not None
            ],
            pending_approvals=[
                approval
                for plan in orchestration.learner_plans
                for approval in plan.relationship_state.approval_requests
                if approval.status == ParentApprovalStatus.pending
            ],
            notifications=self._active_notifications(
                household_id=household.household_id,
                now=reference_time,
            ),
            available_learners=available_learners,
        )

    def mark_notification_read(
        self, *, parent_user_id: str, notification_id: str
    ) -> HouseholdOverview:
        user = self.user_store.get(parent_user_id)
        if user is None:
            raise RuntimeError("Parent user not found.")
        household = self._household_for_user(user)
        if household is None:
            return HouseholdOverview()
        notification = self.parent_notification_store.get(notification_id)
        if notification is not None and notification.household_id == household.household_id:
            self.parent_notification_store.upsert(
                notification.model_copy(
                    update={
                        "status": "read",
                        "snoozed_until": None,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            )
        return self.get_household_overview(parent_user_id=parent_user_id)

    def dismiss_notification(
        self, *, parent_user_id: str, notification_id: str
    ) -> HouseholdOverview:
        user = self.user_store.get(parent_user_id)
        if user is None:
            raise RuntimeError("Parent user not found.")
        household = self._household_for_user(user)
        if household is None:
            return HouseholdOverview()
        notification = self.parent_notification_store.get(notification_id)
        if notification is not None and notification.household_id == household.household_id:
            self.parent_notification_store.upsert(
                notification.model_copy(
                    update={
                        "status": "dismissed",
                        "snoozed_until": None,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
            )
        return self.get_household_overview(parent_user_id=parent_user_id)

    def snooze_notification(
        self,
        *,
        parent_user_id: str,
        notification_id: str,
        request: HouseholdNotificationSnoozeRequest,
    ) -> HouseholdOverview:
        user = self.user_store.get(parent_user_id)
        if user is None:
            raise RuntimeError("Parent user not found.")
        household = self._household_for_user(user)
        if household is None:
            return HouseholdOverview()
        notification = self.parent_notification_store.get(notification_id)
        if notification is not None and notification.household_id == household.household_id:
            now = datetime.now(timezone.utc)
            self.parent_notification_store.upsert(
                notification.model_copy(
                    update={
                        "status": "snoozed",
                        "snoozed_until": now + timedelta(hours=request.hours),
                        "updated_at": now,
                    }
                )
            )
        return self.get_household_overview(parent_user_id=parent_user_id)

    def update_parent_preferences(
        self,
        *,
        parent_user_id: str,
        request: HouseholdPreferenceUpdateRequest,
    ) -> HouseholdOverview:
        user = self.user_store.get(parent_user_id)
        if user is None:
            raise RuntimeError("Parent user not found.")
        household = self._household_for_user(user)
        if household is None:
            raise RuntimeError("Household not found.")
        updated = False
        parent_profiles: list[ParentProfile] = []
        for profile in household.parent_profiles:
            if profile.parent_user_id == parent_user_id:
                parent_profiles.append(
                    profile.model_copy(
                        update={
                            "relationship_label": (
                                request.relationship_label or profile.relationship_label
                            ),
                            "preferences": request.preferences,
                        }
                    )
                )
                updated = True
            else:
                parent_profiles.append(profile)
        if not updated:
            parent_profiles.append(
                ParentProfile(
                    parent_user_id=parent_user_id,
                    display_name=user.display_name,
                    relationship_label=request.relationship_label or "parent",
                    preferences=request.preferences,
                )
            )
        self.household_store.upsert(
            household.model_copy(
                update={
                    "parent_profiles": parent_profiles,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        )
        return self.get_household_overview(parent_user_id=parent_user_id)

    def accept_session_suggestion(
        self, *, parent_user_id: str, learner_id: str
    ) -> HouseholdOverview:
        return self._update_session_suggestion_state(
            parent_user_id=parent_user_id,
            learner_id=learner_id,
            status="accepted",
            snoozed_until=None,
        )

    def defer_session_suggestion(
        self, *, parent_user_id: str, learner_id: str
    ) -> HouseholdOverview:
        return self._update_session_suggestion_state(
            parent_user_id=parent_user_id,
            learner_id=learner_id,
            status="deferred",
            snoozed_until=None,
        )

    def snooze_session_suggestion(
        self,
        *,
        parent_user_id: str,
        learner_id: str,
        request: HouseholdSessionSuggestionSnoozeRequest,
    ) -> HouseholdOverview:
        now = datetime.now(timezone.utc)
        return self._update_session_suggestion_state(
            parent_user_id=parent_user_id,
            learner_id=learner_id,
            status="snoozed",
            snoozed_until=now + timedelta(hours=request.hours),
            now=now,
        )

    def approve_parent_approval(
        self,
        *,
        parent_user_id: str,
        learner_id: str,
        approval_id: str,
    ) -> HouseholdOverview:
        return self._update_parent_approval(
            parent_user_id=parent_user_id,
            learner_id=learner_id,
            approval_id=approval_id,
            status=ParentApprovalStatus.approved,
        )

    def reject_parent_approval(
        self,
        *,
        parent_user_id: str,
        learner_id: str,
        approval_id: str,
    ) -> HouseholdOverview:
        return self._update_parent_approval(
            parent_user_id=parent_user_id,
            learner_id=learner_id,
            approval_id=approval_id,
            status=ParentApprovalStatus.rejected,
        )

    def _household_for_user(self, user: User) -> Household | None:
        if user.household_id:
            household = self.household_store.get(user.household_id)
            if household is not None:
                return household
        return self.household_store.get_by_parent_user_id(user.user_id)

    def _active_notifications(
        self,
        *,
        household_id: str,
        now: datetime,
    ) -> list:
        notifications = self.parent_notification_store.list_for_household(
            household_id=household_id
        )
        visible = []
        for notification in notifications:
            if (
                notification.status == "snoozed"
                and notification.snoozed_until is not None
                and notification.snoozed_until <= now
            ):
                notification = self.parent_notification_store.upsert(
                    notification.model_copy(
                        update={
                            "status": "unread",
                            "snoozed_until": None,
                            "updated_at": now,
                        }
                    )
                )
            if notification.status == "dismissed":
                continue
            if (
                notification.status == "snoozed"
                and notification.snoozed_until is not None
                and notification.snoozed_until > now
            ):
                continue
            visible.append(notification)
        return visible

    def _update_session_suggestion_state(
        self,
        *,
        parent_user_id: str,
        learner_id: str,
        status: str,
        snoozed_until: datetime | None,
        now: datetime | None = None,
    ) -> HouseholdOverview:
        user = self.user_store.get(parent_user_id)
        if user is None:
            raise RuntimeError("Parent user not found.")
        household = self._household_for_user(user)
        if household is None:
            return HouseholdOverview()
        relationship_state = self.autonomous_teacher_harness.learner_relationship_state_store.get(
            household_id=household.household_id,
            learner_id=learner_id,
        )
        if relationship_state is None:
            self.get_household_overview(parent_user_id=parent_user_id)
            relationship_state = (
                self.autonomous_teacher_harness.learner_relationship_state_store.get(
                    household_id=household.household_id,
                    learner_id=learner_id,
                )
            )
        if relationship_state is None:
            return self.get_household_overview(parent_user_id=parent_user_id)
        updated_at = now or datetime.now(timezone.utc)
        adaptation_state = relationship_state.adaptation_state
        if (
            relationship_state.session_suggestion_status != status
            or relationship_state.session_suggestion_updated_at is None
        ):
            update_payload = {
                "session_suggestion_count": (
                    adaptation_state.session_suggestion_count + 1
                ),
                "updated_at": updated_at,
            }
            if status == "accepted":
                update_payload["accepted_suggestion_count"] = (
                    adaptation_state.accepted_suggestion_count + 1
                )
            elif status == "deferred":
                update_payload["deferred_suggestion_count"] = (
                    adaptation_state.deferred_suggestion_count + 1
                )
            elif status == "snoozed":
                update_payload["snoozed_suggestion_count"] = (
                    adaptation_state.snoozed_suggestion_count + 1
                )
            adaptation_state = adaptation_state.model_copy(update=update_payload)
        self.autonomous_teacher_harness.learner_relationship_state_store.upsert(
            relationship_state.model_copy(
                update={
                    "session_suggestion_status": status,
                    "session_suggestion_snoozed_until": snoozed_until,
                    "session_suggestion_updated_at": updated_at,
                    "adaptation_state": adaptation_state,
                    "updated_at": updated_at,
                }
            )
        )
        payload = {
            "learner_id": learner_id,
            "status": status,
            "snoozed_until": snoozed_until.isoformat() if snoozed_until else None,
            "approval_request_count": len(relationship_state.approval_requests),
        }
        if self.audit_store is not None:
            self.audit_store.append(
                event_type="autonomous_teacher.session_suggestion",
                status=status,
                student_id=learner_id,
                payload=payload,
            )
        if self.operational_observability_service is not None:
            self.operational_observability_service.record_trace(
                harness=HarnessBoundary.autonomous_teacher,
                operation="session_suggestion_update",
                status=OperationalTraceStatus.success,
                summary="Parent updated an autonomous session suggestion.",
                student_id=learner_id,
                household_id=household.household_id,
                reason_code=f"session_suggestion_{status}",
                payload=payload,
            )
        return self.get_household_overview(parent_user_id=parent_user_id)

    def _validated_learner_ids(
        self,
        *,
        learner_ids: list[str],
        existing_household_id: str | None,
    ) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        learners_by_id = {
            user.learner_id: user
            for user in self.user_store.list()
            if user.role == "learner" and user.learner_id is not None
        }
        for learner_id in learner_ids:
            if learner_id in seen:
                continue
            seen.add(learner_id)
            learner_user = learners_by_id.get(learner_id)
            if learner_user is None:
                raise RuntimeError(f"Learner {learner_id} was not found.")
            if (
                learner_user.household_id is not None
                and learner_user.household_id != existing_household_id
            ):
                raise RuntimeError(
                    f"Learner {learner_id} already belongs to another household."
                )
            deduped.append(learner_id)
        return deduped

    def _sync_learner_membership(
        self,
        *,
        household_id: str,
        previous_learner_ids: list[str],
        learner_ids: list[str],
        updated_at: str,
    ) -> None:
        requested = set(learner_ids)
        previous = set(previous_learner_ids)
        learners_by_id = {
            user.learner_id: user
            for user in self.user_store.list()
            if user.role == "learner" and user.learner_id is not None
        }
        for learner_id in requested:
            learner_user = learners_by_id.get(learner_id)
            if learner_user is None:
                continue
            if learner_user.household_id != household_id:
                self.user_store.update(
                    learner_user.model_copy(
                        update={
                            "household_id": household_id,
                            "updated_at": updated_at,
                        }
                    )
                )
        for learner_id in previous - requested:
            learner_user = learners_by_id.get(learner_id)
            if learner_user is None or learner_user.household_id != household_id:
                continue
            self.user_store.update(
                learner_user.model_copy(
                    update={
                        "household_id": None,
                        "updated_at": updated_at,
                    }
                )
            )

    def _update_parent_approval(
        self,
        *,
        parent_user_id: str,
        learner_id: str,
        approval_id: str,
        status: ParentApprovalStatus,
    ) -> HouseholdOverview:
        user = self.user_store.get(parent_user_id)
        if user is None:
            raise RuntimeError("Parent user not found.")
        household = self._household_for_user(user)
        if household is None:
            return HouseholdOverview()
        relationship_state = self.autonomous_teacher_harness.learner_relationship_state_store.get(
            household_id=household.household_id,
            learner_id=learner_id,
        )
        if relationship_state is None:
            return self.get_household_overview(parent_user_id=parent_user_id)
        decided_at = datetime.now(timezone.utc)
        approved_modalities = list(relationship_state.approved_modalities)
        updated_approvals = []
        adaptation_state = relationship_state.adaptation_state
        for approval in relationship_state.approval_requests:
            if approval.approval_id != approval_id:
                updated_approvals.append(approval)
                continue
            already_decided = approval.status != ParentApprovalStatus.pending
            resolved = approval.model_copy(
                update={
                    "status": status,
                    "decided_at": decided_at,
                }
            )
            updated_approvals.append(resolved)
            if not already_decided:
                adaptation_state = adaptation_state.model_copy(
                    update={
                        "approval_request_count": (
                            adaptation_state.approval_request_count + 1
                        ),
                        "updated_at": decided_at,
                    }
                )
            if (
                status == ParentApprovalStatus.approved
                and resolved.approval_type == ParentApprovalType.modality_introduction
                and resolved.proposed_value is not None
                and resolved.proposed_value not in approved_modalities
            ):
                approved_modalities.append(resolved.proposed_value)
        self.autonomous_teacher_harness.learner_relationship_state_store.upsert(
            relationship_state.model_copy(
                update={
                    "approved_modalities": approved_modalities,
                    "approval_requests": updated_approvals,
                    "adaptation_state": adaptation_state,
                    "updated_at": decided_at,
                }
            )
        )
        resolved_approval = next(
            (approval for approval in updated_approvals if approval.approval_id == approval_id),
            None,
        )
        payload = {
            "approval_id": approval_id,
            "learner_id": learner_id,
            "approval_status": status.value,
            "approval_type": (
                resolved_approval.approval_type.value if resolved_approval is not None else None
            ),
            "proposed_value": (
                resolved_approval.proposed_value if resolved_approval is not None else None
            ),
            "approved_modalities": list(approved_modalities),
        }
        if self.audit_store is not None:
            self.audit_store.append(
                event_type="autonomous_teacher.parent_approval",
                status=status.value,
                student_id=learner_id,
                payload=payload,
            )
        if self.operational_observability_service is not None:
            self.operational_observability_service.record_trace(
                harness=HarnessBoundary.autonomous_teacher,
                operation="parent_approval_update",
                status=OperationalTraceStatus.success,
                summary="Parent approval updated autonomous teaching state.",
                student_id=learner_id,
                household_id=household.household_id,
                entity_kind="parent_approval",
                entity_id=approval_id,
                reason_code=f"parent_approval_{status.value}",
                payload=payload,
            )
        return self.get_household_overview(parent_user_id=parent_user_id)
