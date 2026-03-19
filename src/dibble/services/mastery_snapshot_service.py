from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dibble.models.mastery_history import (
    SectionAveragePoint,
    SectionMasteryTrendsResponse,
    LearnerMasteryTrend,
    MasteryHistoryResponse,
    MasterySnapshot,
)
from dibble.models.profile import LearnerProfile
from dibble.services.mastery_snapshot_store import SQLiteMasterySnapshotStore

MASTERED_THRESHOLD = 0.75
STRUGGLING_THRESHOLD = 0.35


@dataclass(slots=True)
class MasterySnapshotService:
    snapshot_store: SQLiteMasterySnapshotStore

    def record_from_profile(self, profile: LearnerProfile) -> MasterySnapshot:
        kc_mastery = profile.knowledge_state.kc_mastery
        lo_mastery = profile.knowledge_state.lo_mastery
        kc_values = list(kc_mastery.values())
        lo_values = list(lo_mastery.values())
        overall_kc = round(sum(kc_values) / len(kc_values), 4) if kc_values else 0.0
        overall_lo = round(sum(lo_values) / len(lo_values), 4) if lo_values else 0.0
        mastered_kc_count = sum(1 for v in kc_values if v >= MASTERED_THRESHOLD)
        struggling_kc_count = sum(1 for v in kc_values if v < STRUGGLING_THRESHOLD)

        return self.snapshot_store.record(
            student_id=str(profile.student_id),
            overall_kc_mastery=overall_kc,
            overall_lo_mastery=overall_lo,
            kc_count=len(kc_values),
            lo_count=len(lo_values),
            mastered_kc_count=mastered_kc_count,
            struggling_kc_count=struggling_kc_count,
            engagement=profile.affective_state.engagement.value,
            frustration=profile.affective_state.frustration.value,
            total_load=profile.cognitive_load.total_load,
        )

    def get_learner_history(
        self,
        *,
        student_id: UUID,
        days: int = 30,
    ) -> MasteryHistoryResponse:
        snapshots = self.snapshot_store.list_for_student(
            student_id=str(student_id),
            days=days,
        )
        return MasteryHistoryResponse(
            student_id=str(student_id),
            days=days,
            snapshot_count=len(snapshots),
            snapshots=snapshots,
        )

    def get_section_trends(
        self,
        *,
        section_id: str,
        student_ids: list[str],
        days: int = 30,
    ) -> SectionMasteryTrendsResponse:
        learner_trends: list[LearnerMasteryTrend] = []
        all_snapshots_by_time: dict[str, list[float]] = {}

        for student_id in student_ids:
            snapshots = self.snapshot_store.list_for_student(
                student_id=student_id,
                days=days,
            )
            earliest_mastery = snapshots[0].overall_kc_mastery if snapshots else None
            latest_mastery = snapshots[-1].overall_kc_mastery if snapshots else None
            mastery_delta = round(
                (latest_mastery or 0.0) - (earliest_mastery or 0.0), 4
            )

            learner_trends.append(
                LearnerMasteryTrend(
                    student_id=student_id,
                    snapshot_count=len(snapshots),
                    snapshots=snapshots,
                    earliest_mastery=earliest_mastery,
                    latest_mastery=latest_mastery,
                    mastery_delta=mastery_delta,
                )
            )

            for snapshot in snapshots:
                date_key = snapshot.created_at.strftime("%Y-%m-%d")
                all_snapshots_by_time.setdefault(date_key, []).append(
                    snapshot.overall_kc_mastery
                )

        section_averages: list[SectionAveragePoint] = []
        for date_key in sorted(all_snapshots_by_time.keys()):
            values = all_snapshots_by_time[date_key]
            section_averages.append(
                SectionAveragePoint(
                    timestamp=datetime.fromisoformat(date_key + "T00:00:00+00:00"),
                    average_mastery=round(sum(values) / len(values), 4),
                    learner_count=len(values),
                )
            )

        return SectionMasteryTrendsResponse(
            section_id=section_id,
            days=days,
            learner_count=len(student_ids),
            learner_trends=learner_trends,
            section_average_snapshots=section_averages,
        )
