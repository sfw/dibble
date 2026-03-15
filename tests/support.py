from __future__ import annotations


def build_profile(student_id, *, frustration="high", total_load=0.88, kc_mastery=None, engagement="medium"):
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
        "learning_preferences": {
            "modality_affinity": {"textual": 0.9, "interactive": 0.4},
            "example_domain_preferences": ["music", "science"],
            "scaffolding_preference": "high",
            "pace_preference": "slower_than_average",
        },
    }


def build_curriculum_resource(resource_id="CURR-1"):
    return {
        "resource_id": resource_id,
        "title": "Equivalent Fractions Foundations",
        "grade_level": "5",
        "subject": "math",
        "learning_objective_ids": ["LO-1"],
        "knowledge_component_ids": ["KC-1"],
        "tags": ["fractions", "equivalent fractions", "remediation"],
        "body": "Use visual fraction models to explain why equivalent fractions name the same amount.",
        "source_type": "curriculum_standard",
    }
