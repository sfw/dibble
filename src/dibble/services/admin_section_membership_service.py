from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dibble.models.admin_section_membership import (
    AdminSectionMembershipSummary,
    AdminSectionMembershipUpdateRequest,
    AdminSectionMembershipUserSummary,
)
from dibble.models.classroom_membership import ClassroomMembershipRole
from dibble.services.protocols import ClassroomMembershipStore, ClassroomStore, UserStore


class SectionMembershipUserNotFoundError(LookupError):
    def __init__(self, user_id: str) -> None:
        super().__init__(user_id)
        self.user_id = user_id


class SectionMembershipRoleMismatchError(ValueError):
    def __init__(self, *, user_id: str, expected_role: str, actual_role: str) -> None:
        super().__init__(user_id)
        self.user_id = user_id
        self.expected_role = expected_role
        self.actual_role = actual_role


@dataclass(slots=True)
class AdminSectionMembershipService:
    classroom_store: ClassroomStore
    classroom_membership_store: ClassroomMembershipStore
    user_store: UserStore

    def get_section_memberships(
        self, section_id: str
    ) -> AdminSectionMembershipSummary | None:
        if self.classroom_store.get(section_id) is None:
            return None
        return AdminSectionMembershipSummary(
            section_id=section_id,
            teachers=self._membership_users(
                section_id, role=ClassroomMembershipRole.teacher
            ),
            learners=self._membership_users(
                section_id, role=ClassroomMembershipRole.learner
            ),
        )

    def update_section_memberships(
        self,
        section_id: str,
        payload: AdminSectionMembershipUpdateRequest,
    ) -> AdminSectionMembershipSummary:
        if self.classroom_store.get(section_id) is None:
            raise LookupError(section_id)

        teacher_user_ids = self._validated_user_ids(
            payload.teacher_user_ids,
            required_role=ClassroomMembershipRole.teacher,
        )
        learner_user_ids = self._validated_user_ids(
            payload.learner_user_ids,
            required_role=ClassroomMembershipRole.learner,
        )

        prior_teacher_user_ids = set(
            self.classroom_membership_store.list_classroom_user_ids(
                section_id,
                role=ClassroomMembershipRole.teacher,
            )
        )
        prior_learner_user_ids = set(
            self.classroom_membership_store.list_classroom_user_ids(
                section_id,
                role=ClassroomMembershipRole.learner,
            )
        )

        self.classroom_membership_store.replace_for_classroom(
            classroom_id=section_id,
            role=ClassroomMembershipRole.teacher,
            user_ids=teacher_user_ids,
        )
        self.classroom_membership_store.replace_for_classroom(
            classroom_id=section_id,
            role=ClassroomMembershipRole.learner,
            user_ids=learner_user_ids,
        )

        for user_id in prior_teacher_user_ids.union(teacher_user_ids):
            self._sync_user_classroom_ids(
                user_id=user_id,
                role=ClassroomMembershipRole.teacher,
            )
        for user_id in prior_learner_user_ids.union(learner_user_ids):
            self._sync_user_classroom_ids(
                user_id=user_id,
                role=ClassroomMembershipRole.learner,
            )

        summary = self.get_section_memberships(section_id)
        if summary is None:
            raise LookupError(section_id)
        return summary

    def _membership_users(
        self,
        section_id: str,
        *,
        role: ClassroomMembershipRole,
    ) -> list[AdminSectionMembershipUserSummary]:
        members: list[AdminSectionMembershipUserSummary] = []
        for user_id in self.classroom_membership_store.list_classroom_user_ids(
            section_id,
            role=role,
        ):
            user = self.user_store.get(user_id)
            if user is None:
                continue
            members.append(
                AdminSectionMembershipUserSummary(
                    user_id=user.user_id,
                    display_name=user.display_name,
                )
            )
        return members

    def _validated_user_ids(
        self,
        user_ids: list[str],
        *,
        required_role: ClassroomMembershipRole,
    ) -> list[str]:
        normalized = sorted({user_id.strip() for user_id in user_ids if user_id.strip()})
        for user_id in normalized:
            user = self.user_store.get(user_id)
            if user is None:
                raise SectionMembershipUserNotFoundError(user_id)
            if user.role != required_role.value:
                raise SectionMembershipRoleMismatchError(
                    user_id=user_id,
                    expected_role=required_role.value,
                    actual_role=user.role,
                )
        return normalized

    def _sync_user_classroom_ids(
        self,
        *,
        user_id: str,
        role: ClassroomMembershipRole,
    ) -> None:
        user = self.user_store.get(user_id)
        if user is None or user.role != role.value:
            return
        user.classroom_ids = self.classroom_membership_store.list_user_classroom_ids(
            user_id,
            role=role,
        )
        user.updated_at = datetime.now(timezone.utc).isoformat()
        self.user_store.update(user)
