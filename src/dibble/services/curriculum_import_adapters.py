from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from dibble.models.course import CourseUpsert
from dibble.models.curriculum import (
    KnowledgeComponentUpsert,
    OutcomeUpsert,
    StrandUpsert,
)
from dibble.models.curriculum_intake import (
    CurriculumFramework,
    CurriculumImportRequest,
    FrameworkImportMode,
)


@dataclass(frozen=True, slots=True)
class ImportedCurriculumBundle:
    framework: CurriculumFramework
    framework_version: str
    source_label: str
    source_uri: str | None
    planner_summary: str
    metadata: dict[str, object] = field(default_factory=dict)
    courses: list[CourseUpsert] = field(default_factory=list)
    strands: list[StrandUpsert] = field(default_factory=list)
    outcomes: list[OutcomeUpsert] = field(default_factory=list)
    knowledge_components: list[KnowledgeComponentUpsert] = field(default_factory=list)

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "framework": {
                "framework_id": self.framework.framework_id,
                "title": self.framework.title,
                "jurisdiction": self.framework.jurisdiction,
                "subject": self.framework.subject,
                "grade_band": self.framework.grade_band,
                "language": self.framework.language,
                "tags": list(self.framework.tags),
            },
            "framework_version": self.framework_version,
            "source_label": self.source_label,
            "source_uri": self.source_uri,
            "metadata": self.metadata,
            "courses": [course.model_dump(mode="json") for course in self.courses],
            "strands": [strand.model_dump(mode="json") for strand in self.strands],
            "outcomes": [outcome.model_dump(mode="json") for outcome in self.outcomes],
            "knowledge_components": [
                component.model_dump(mode="json")
                for component in self.knowledge_components
            ],
        }


class CurriculumImportAdapter:
    adapter_key: str
    import_mode: FrameworkImportMode

    def build_bundle(
        self, request: CurriculumImportRequest
    ) -> ImportedCurriculumBundle:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class AlbertaMath7CurriculumImportAdapter(CurriculumImportAdapter):
    adapter_key: str = "alberta_math_7_seed"
    import_mode: FrameworkImportMode = FrameworkImportMode.structured_seed

    def build_bundle(
        self, request: CurriculumImportRequest
    ) -> ImportedCurriculumBundle:
        from scripts import seed_alberta_math7 as alberta_seed

        framework_id = request.framework_id or "alberta-math-7"
        framework_version = request.framework_version or "2022"
        source_label = request.source_label or "Alberta Mathematics Grade 7 seed"
        source_uri = (
            request.source_uri
            or "https://curriculum.learnalberta.ca/curriculum/en/pos/MAT_79/MATH7"
        )
        tags = sorted(
            {
                *request.tags,
                "alberta",
                "grade-7",
                "mathematics",
                "seed-import",
            }
        )
        framework = CurriculumFramework(
            framework_id=framework_id,
            title=request.title or "Alberta Mathematics Grade 7",
            jurisdiction=request.jurisdiction or "Alberta",
            subject=request.subject or "mathematics",
            grade_band=request.grade_band or "7",
            language=request.language,
            tags=tags,
        )

        course = CourseUpsert(
            course_id=str(alberta_seed.COURSE["course_id"]),
            title=str(alberta_seed.COURSE["title"]),
            subject=(
                str(alberta_seed.COURSE.get("subject"))
                if alberta_seed.COURSE.get("subject") is not None
                else framework.subject
            ),
            grade_band=(
                str(alberta_seed.COURSE.get("grade_band"))
                if alberta_seed.COURSE.get("grade_band") is not None
                else framework.grade_band
            ),
            tags=list(alberta_seed.COURSE.get("tags", [])),
        )
        strands = [
            StrandUpsert.model_validate(strand) for strand in alberta_seed.STRANDS
        ]

        outcomes: list[OutcomeUpsert] = []
        knowledge_components: list[KnowledgeComponentUpsert] = []
        for outcome in alberta_seed.ALL_OUTCOMES:
            outcomes.append(
                OutcomeUpsert(
                    outcome_id=outcome.outcome_id,
                    title=outcome.title,
                    strand_id=outcome.strand_id,
                    grade_level=framework.grade_band or "7",
                    subject=framework.subject,
                    description=outcome.description,
                    knowledge_component_ids=[kc.kc_id for kc in outcome.kcs],
                    tags=["alberta"],
                )
            )
            for component in outcome.kcs:
                knowledge_components.append(
                    KnowledgeComponentUpsert(
                        kc_id=component.kc_id,
                        name=component.name,
                        outcome_id=component.outcome_id,
                        grade_level=framework.grade_band or "7",
                        subject=framework.subject,
                        taxonomy_cluster_id=component.taxonomy_cluster_id,
                        concept_family=component.concept_family,
                        prerequisite_kc_ids=list(component.prerequisite_kc_ids),
                        nearby_kc_ids=list(component.nearby_kc_ids),
                        difficulty=component.difficulty,
                        estimated_time_minutes=component.estimated_time_minutes,
                        tags=list(component.tags),
                        common_misconceptions=list(component.misconceptions),
                    )
                )

        return ImportedCurriculumBundle(
            framework=framework,
            framework_version=framework_version,
            source_label=source_label,
            source_uri=source_uri,
            planner_summary=(
                "Structured Alberta Grade 7 curriculum seed import through the"
                " deterministic Alberta adapter."
            ),
            metadata={
                **request.metadata,
                "adapter_key": self.adapter_key,
                "artifact_counts": {
                    "courses": 1,
                    "strands": len(strands),
                    "outcomes": len(outcomes),
                    "knowledge_components": len(knowledge_components),
                },
            },
            courses=[course],
            strands=strands,
            outcomes=outcomes,
            knowledge_components=knowledge_components,
        )


def default_curriculum_import_adapters() -> Sequence[CurriculumImportAdapter]:
    return [AlbertaMath7CurriculumImportAdapter()]
