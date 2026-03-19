from __future__ import annotations

from dataclasses import dataclass

from dibble.models.admin_academics import AdminCourseSummary, AdminSectionSummary
from dibble.models.classroom import Classroom, ClassroomUpsert
from dibble.models.classroom_membership import ClassroomMembershipRole
from dibble.models.course import Course, CourseUpsert
from dibble.models.section import Section, SectionUpsert
from dibble.services.protocols import ClassroomMembershipStore, ClassroomStore, CourseStore


@dataclass(slots=True)
class AdminAcademicCatalogService:
    course_store: CourseStore
    classroom_store: ClassroomStore
    classroom_membership_store: ClassroomMembershipStore

    def get_course_summary(self, course_id: str) -> AdminCourseSummary | None:
        course = self.course_store.get(course_id)
        if course is None:
            return None
        section_count = sum(
            1
            for section in self.classroom_store.list()
            if section.course_id == course.course_id
        )
        return AdminCourseSummary(
            **course.model_dump(),
            section_count=section_count,
        )

    def list_courses(self) -> list[AdminCourseSummary]:
        section_counts: dict[str, int] = {}
        for section in self.classroom_store.list():
            section_counts[section.course_id] = (
                section_counts.get(section.course_id, 0) + 1
            )

        return [
            AdminCourseSummary(
                **course.model_dump(),
                section_count=section_counts.get(course.course_id, 0),
            )
            for course in self.course_store.list()
        ]

    def upsert_course(self, payload: CourseUpsert) -> Course:
        return self.course_store.upsert(payload)

    def get_section_summary(self, section_id: str) -> AdminSectionSummary | None:
        section = self.classroom_store.get(section_id)
        if section is None:
            return None
        courses = {course.course_id: course for course in self.course_store.list()}
        teacher_count = len(
            self.classroom_membership_store.list_classroom_user_ids(
                section.classroom_id,
                role=ClassroomMembershipRole.teacher,
            )
        )
        learner_count = len(
            self.classroom_membership_store.list_classroom_user_ids(
                section.classroom_id,
                role=ClassroomMembershipRole.learner,
            )
        )
        return AdminSectionSummary(
            **self._section_payload(section).model_dump(),
            course_title=(
                courses.get(section.course_id).title
                if section.course_id in courses
                else None
            ),
            teacher_count=teacher_count,
            learner_count=learner_count,
        )

    def list_sections(self) -> list[AdminSectionSummary]:
        courses = {course.course_id: course for course in self.course_store.list()}
        summaries: list[AdminSectionSummary] = []
        for section in self.classroom_store.list():
            teacher_count = len(
                self.classroom_membership_store.list_classroom_user_ids(
                    section.classroom_id,
                    role=ClassroomMembershipRole.teacher,
                )
            )
            learner_count = len(
                self.classroom_membership_store.list_classroom_user_ids(
                    section.classroom_id,
                    role=ClassroomMembershipRole.learner,
                )
            )
            summaries.append(
                AdminSectionSummary(
                    **self._section_payload(section).model_dump(),
                    course_title=courses.get(section.course_id).title
                    if section.course_id in courses
                    else None,
                    teacher_count=teacher_count,
                    learner_count=learner_count,
                )
            )
        return summaries

    def upsert_section(self, payload: SectionUpsert) -> Section:
        if self.course_store.get(payload.course_id) is None:
            raise LookupError(payload.course_id)
        section = self.classroom_store.upsert(
            ClassroomUpsert(
                classroom_id=payload.section_id,
                course_id=payload.course_id,
                title=payload.title,
                grade_level=payload.grade_level,
                subject=payload.subject,
                tags=payload.tags,
            )
        )
        return self._section_payload(section)

    @staticmethod
    def _section_payload(classroom: Classroom) -> Section:
        return Section(
            section_id=classroom.classroom_id,
            course_id=classroom.course_id,
            title=classroom.title,
            grade_level=classroom.grade_level,
            subject=classroom.subject,
            tags=classroom.tags,
            updated_at=classroom.updated_at,
        )
