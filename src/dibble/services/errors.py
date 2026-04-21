from __future__ import annotations

from uuid import UUID


class LearnerProfileNotFoundError(LookupError):
    def __init__(self, student_id: UUID) -> None:
        super().__init__(f"Learner profile not found for student_id {student_id}.")
        self.student_id = student_id
