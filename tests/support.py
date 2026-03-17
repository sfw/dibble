from __future__ import annotations


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


def build_curriculum_resource(
    resource_id="CURR-1",
    *,
    title="Equivalent Fractions Foundations",
    learning_objective_ids=None,
    knowledge_component_ids=None,
    tags=None,
    body="Use visual fraction models to explain why equivalent fractions name the same amount.",
):
    return {
        "resource_id": resource_id,
        "title": title,
        "grade_level": "5",
        "subject": "math",
        "learning_objective_ids": learning_objective_ids or ["LO-1"],
        "knowledge_component_ids": knowledge_component_ids or ["KC-1"],
        "tags": tags or ["fractions", "equivalent fractions", "remediation"],
        "body": body,
        "source_type": "curriculum_standard",
    }


def build_knowledge_component(
    kc_id="KC-1",
    *,
    prerequisite_kc_ids=None,
    parent_lo_id="LO-1",
    name="Understand equivalent fractions with visual models",
    common_misconceptions=None,
    taxonomy_cluster_id=None,
    concept_family=None,
    nearby_kc_ids=None,
):
    return {
        "kc_id": kc_id,
        "name": name,
        "parent_lo_id": parent_lo_id,
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
