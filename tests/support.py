from __future__ import annotations


def assert_machine_readable_error(
    response, *, status_code: int, code: str, detail: str | None = None
) -> None:
    assert response.status_code == status_code
    assert response.headers["x-dibble-error-code"] == code
    payload = response.json()
    assert payload["code"] == code
    if detail is not None:
        assert payload["detail"] == detail
    else:
        assert isinstance(payload["detail"], str) and payload["detail"]


def build_profile(
    student_id,
    *,
    frustration="high",
    total_load=0.88,
    kc_mastery=None,
    engagement="medium",
    confidence_calibration=0.5,
    help_seeking="low",
    help_seeking_effectiveness=0.5,
    self_monitoring=0.5,
):
    return {
        "student_id": str(student_id),
        "grade_level": "5",
        "cognitive_traits": {
            "working_memory": {
                "value": 0.52,
                "confidence": 0.8,
            }
        },
        "knowledge_state": {
            "lo_mastery": {"LO-1": 0.5},
            "kc_mastery": kc_mastery or {"KC-1": 0.2, "KC-2": 0.35},
        },
        "affective_state": {
            "engagement": engagement,
            "frustration": frustration,
            "confusion": "medium",
            "confidence": 0.35,
        },
        "cognitive_load": {
            "intrinsic_load": 0.5,
            "extraneous_load": 0.3,
            "germane_load": 0.2,
            "total_load": total_load,
            "capacity_utilization": 0.9,
        },
        "metacognitive_state": {
            "confidence_calibration": confidence_calibration,
            "help_seeking": help_seeking,
            "help_seeking_effectiveness": help_seeking_effectiveness,
            "self_monitoring": self_monitoring,
        },
        "learning_preferences": {
            "modality_affinity": {"textual": 0.9, "interactive": 0.4},
            "example_domain_preferences": ["music", "science"],
            "scaffolding_preference": "high",
            "pace_preference": "slower_than_average",
        },
    }


def build_outcome(
    outcome_id="CURR-1",
    *,
    title="Equivalent Fractions Foundations",
    strand_id="STRAND-1",
    knowledge_component_ids=None,
    tags=None,
    description="Use visual fraction models to explain why equivalent fractions name the same amount.",
):
    return {
        "outcome_id": outcome_id,
        "title": title,
        "strand_id": strand_id,
        "grade_level": "5",
        "subject": "math",
        "knowledge_component_ids": knowledge_component_ids or ["KC-1"],
        "tags": tags or ["fractions", "equivalent fractions", "remediation"],
        "description": description,
    }


def build_knowledge_component(
    kc_id="KC-1",
    *,
    prerequisite_kc_ids=None,
    outcome_id="LO-1",
    name="Understand equivalent fractions with visual models",
    common_misconceptions=None,
    taxonomy_cluster_id=None,
    concept_family=None,
    nearby_kc_ids=None,
):
    return {
        "kc_id": kc_id,
        "name": name,
        "outcome_id": outcome_id,
        "grade_level": "5",
        "subject": "math",
        "taxonomy_cluster_id": taxonomy_cluster_id,
        "concept_family": concept_family,
        "prerequisite_kc_ids": prerequisite_kc_ids or [],
        "nearby_kc_ids": nearby_kc_ids or [],
        "difficulty": 0.5,
        "estimated_time_minutes": 8,
        "tags": ["fractions", "remediation"],
        "common_misconceptions": common_misconceptions or [],
    }


def build_classroom(
    section_id="CLASS-1",
    *,
    course_id="COURSE-1",
    title="Fraction Intervention Group",
    grade_level="5",
    subject="math",
    tags=None,
):
    return {
        "section_id": section_id,
        "course_id": course_id,
        "title": title,
        "grade_level": grade_level,
        "subject": subject,
        "tags": tags or ["math", "fractions"],
    }


def build_section(
    section_id="SECTION-1",
    *,
    course_id="COURSE-1",
    title="Fraction Intervention Group",
    grade_level="5",
    subject="math",
    tags=None,
):
    return {
        "section_id": section_id,
        "course_id": course_id,
        "title": title,
        "grade_level": grade_level,
        "subject": subject,
        "tags": tags or ["math", "fractions"],
    }
