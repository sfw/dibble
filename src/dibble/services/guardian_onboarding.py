"""Guardian onboarding for the homeschool pilot.

Maps the existing auth model to the homeschool shape: an admin issues an
invite code; a guardian consumes it to register (a `guardian` role aliases
the teacher capabilities plus parent surfaces); the family becomes a
classroom binding 1-3 learners; learners get name/grade-only profiles with a
simple PIN login. PII is minimized by design — no emails or real-name
requirements beyond a display name. (POC roadmap 2.2)
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from dibble.models.auth import User
from dibble.models.classroom import ClassroomUpsert
from dibble.models.classroom_membership import (
    ClassroomMembershipRole,
    ClassroomMembershipUpsert,
)
from dibble.models.guardian import (
    FamilyLearnerCreateResponse,
    FamilyLearnerSummary,
    GuardianInvite,
    GuardianRegisterResponse,
)
from dibble.models.profile import LearnerProfile
from dibble.services.auth import hash_credential
from dibble.services.guardian_invite_store import SQLiteGuardianInviteStore
from dibble.services.passphrase import generate_passphrase
from dibble.services.protocols import AuditStore, ProfileStore

logger = logging.getLogger(__name__)

GUARDIAN_ROLE = "guardian"
DEFAULT_FAMILY_COURSE_ID = "family"
MAX_FAMILY_LEARNERS = 3


class GuardianOnboardingError(ValueError):
    pass


@dataclass(slots=True)
class GuardianOnboardingService:
    user_store: object  # SQLiteUserStore
    classroom_store: object  # SQLiteClassroomStore
    classroom_membership_store: object  # SQLiteClassroomMembershipStore
    profile_store: ProfileStore
    invite_store: SQLiteGuardianInviteStore
    audit_store: AuditStore | None = None

    # -- invites -------------------------------------------------------------

    def create_invite(
        self, *, created_by: str | None = None, family_name: str | None = None
    ) -> GuardianInvite:
        invite = GuardianInvite(
            code=self._generate_code(),
            family_name=family_name,
            created_by=created_by,
        )
        self.invite_store.upsert(invite)
        self._emit(
            "guardian.invite.created",
            payload={"code": invite.code, "family_name": family_name},
        )
        return invite

    def list_invites(self) -> list[GuardianInvite]:
        return self.invite_store.list()

    # -- registration ---------------------------------------------------------

    def register_guardian(
        self,
        *,
        invite_code: str,
        display_name: str,
        course_id: str | None = None,
    ) -> GuardianRegisterResponse:
        invite = self.invite_store.get(invite_code.strip())
        if invite is None:
            raise GuardianOnboardingError("Invite code not recognized.")
        if invite.used:
            raise GuardianOnboardingError("Invite code has already been used.")

        family_section_id = f"family-{uuid4().hex[:8]}"
        family_title = invite.family_name or f"{display_name} family"
        self.classroom_store.upsert(
            ClassroomUpsert(
                classroom_id=family_section_id,
                course_id=course_id or DEFAULT_FAMILY_COURSE_ID,
                title=family_title,
                tags=["family"],
            )
        )

        credential = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        user = User(
            user_id=str(uuid4()),
            display_name=display_name,
            role=GUARDIAN_ROLE,
            api_key_hash=hash_credential(credential),
            section_ids=[family_section_id],
            created_at=now,
            updated_at=now,
        )
        self.user_store.create(user)
        self.classroom_membership_store.upsert(
            ClassroomMembershipUpsert(
                classroom_id=family_section_id,
                user_id=user.user_id,
                role=ClassroomMembershipRole.teacher,
            )
        )
        invite.used_by_user_id = user.user_id
        invite.used_at = datetime.now(timezone.utc)
        self.invite_store.upsert(invite)
        self._emit(
            "guardian.registered",
            payload={
                "user_id": user.user_id,
                "family_section_id": family_section_id,
                "invite_code": invite.code,
            },
        )
        return GuardianRegisterResponse(
            user_id=user.user_id,
            credential=credential,
            display_name=display_name,
            family_section_id=family_section_id,
        )

    # -- learners --------------------------------------------------------------

    def create_family_learner(
        self,
        *,
        guardian_user_id: str | None,
        display_name: str,
        grade_level: str,
        section_id: str | None = None,
    ) -> FamilyLearnerCreateResponse:
        family_section_id = self._resolve_family_section(
            guardian_user_id=guardian_user_id, section_id=section_id
        )
        existing = self.classroom_membership_store.list_classroom_user_ids(
            classroom_id=family_section_id,
            role=ClassroomMembershipRole.learner,
        )
        if len(existing) >= MAX_FAMILY_LEARNERS:
            raise GuardianOnboardingError(
                f"A family unit supports at most {MAX_FAMILY_LEARNERS} learners."
            )

        pin = generate_passphrase(3)
        now = datetime.now(timezone.utc).isoformat()
        learner_id = str(uuid4())
        user = User(
            user_id=str(uuid4()),
            display_name=display_name,
            role="learner",
            passphrase_hash=hash_credential(pin),
            learner_id=learner_id,
            section_ids=[family_section_id],
            created_at=now,
            updated_at=now,
        )
        self.user_store.create(user)
        self.classroom_membership_store.upsert(
            ClassroomMembershipUpsert(
                classroom_id=family_section_id,
                user_id=user.user_id,
                role=ClassroomMembershipRole.learner,
            )
        )
        self.profile_store.upsert(
            LearnerProfile(student_id=UUID(learner_id), grade_level=grade_level)
        )
        self._emit(
            "guardian.learner.created",
            student_id=learner_id,
            payload={
                "user_id": user.user_id,
                "family_section_id": family_section_id,
                "grade_level": grade_level,
            },
        )
        return FamilyLearnerCreateResponse(
            user_id=user.user_id,
            learner_id=learner_id,
            display_name=display_name,
            grade_level=grade_level,
            pin=pin,
            family_section_id=family_section_id,
        )

    def list_family_learners(
        self, *, guardian_user_id: str | None, section_id: str | None = None
    ) -> list[FamilyLearnerSummary]:
        family_section_id = self._resolve_family_section(
            guardian_user_id=guardian_user_id, section_id=section_id
        )
        user_ids = self.classroom_membership_store.list_classroom_user_ids(
            classroom_id=family_section_id,
            role=ClassroomMembershipRole.learner,
        )
        summaries: list[FamilyLearnerSummary] = []
        for user_id in user_ids:
            user = self.user_store.get(user_id)
            if user is None:
                continue
            grade_level: str | None = None
            if user.learner_id:
                profile = self.profile_store.get(UUID(user.learner_id))
                grade_level = profile.grade_level if profile else None
            summaries.append(
                FamilyLearnerSummary(
                    user_id=user.user_id,
                    learner_id=user.learner_id,
                    display_name=user.display_name,
                    grade_level=grade_level,
                )
            )
        return summaries

    # -- internals ---------------------------------------------------------------

    def _resolve_family_section(
        self, *, guardian_user_id: str | None, section_id: str | None
    ) -> str:
        if guardian_user_id is not None:
            user = self.user_store.get(guardian_user_id)
            if user is not None:
                section_ids = list(user.section_ids)
                if not section_ids:
                    section_ids = self.classroom_membership_store.list_user_section_ids(
                        user_id=guardian_user_id,
                        role=ClassroomMembershipRole.teacher,
                    )
                if section_ids:
                    return section_ids[0]
        if section_id is not None:
            return section_id
        raise GuardianOnboardingError(
            "A family section is required to manage learners."
        )

    def _generate_code(self) -> str:
        # Short, human-typable, unambiguous (hex avoids 0/O 1/l confusion in
        # most fonts and is easy to read over the phone).
        return f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()

    def _emit(
        self,
        event_type: str,
        *,
        payload: dict[str, object],
        student_id: str | None = None,
    ) -> None:
        if self.audit_store is None:
            return
        try:
            self.audit_store.append(
                event_type=event_type,
                status="success",
                student_id=student_id,
                payload=payload,
            )
        except Exception:  # noqa: BLE001 - telemetry must not break onboarding
            logger.warning("Failed to record guardian audit event", exc_info=True)
