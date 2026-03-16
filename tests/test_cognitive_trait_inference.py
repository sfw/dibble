from uuid import uuid4

from dibble.models.observations import LearnerObservation
from dibble.models.profile import CognitiveTraitScore
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.cognitive_trait_inference import CognitiveTraitInferenceService
from dibble.services.learning_trait_profiles import LearnerTraitProfileSignalService
from dibble.storage import ensure_database


def test_cognitive_trait_inference_updates_processing_speed_and_working_memory():
    service = CognitiveTraitInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=8000,
            expected_duration_ms=12000,
            hints_used=0,
            error_count=0,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.82,
            task_type="practice",
            support_level="low",
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=9000,
            expected_duration_ms=12000,
            hints_used=0,
            error_count=0,
            pause_count=1,
            modality_switches=0,
            completed=True,
            confidence=0.78,
            task_type="assessment",
            support_level="low",
        ),
    ]

    traits = service.infer(observations=observations, existing_traits={})

    assert traits["processing_speed"].value > 0.7
    assert traits["working_memory"].value > 0.6
    assert traits["processing_speed"].confidence > 0.4


def test_cognitive_trait_inference_merges_with_existing_trait_scores():
    service = CognitiveTraitInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=26000,
            expected_duration_ms=12000,
            hints_used=3,
            error_count=2,
            pause_count=3,
            modality_switches=2,
            completed=False,
            confidence=0.3,
            task_type="worked_example",
            support_level="high",
        )
    ]

    traits = service.infer(
        observations=observations,
        existing_traits={"working_memory": CognitiveTraitScore(value=0.8, confidence=0.8)},
    )

    assert traits["working_memory"].value < 0.8
    assert traits["working_memory"].confidence > 0.3
    assert "spatial_reasoning" in traits


def test_cognitive_trait_inference_blends_durable_trait_profile(tmp_path):
    database_path = str(tmp_path / "cognitive-trait-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.cognitive_trait.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "matched_observation_count": 6,
            "matched_session_count": 3,
            "profile_signal": "stable",
            "processing_speed": {"value": 0.82, "confidence": 0.8},
            "working_memory": {"value": 0.77, "confidence": 0.78},
            "spatial_reasoning": {"value": 0.71, "confidence": 0.68},
        },
    )
    service = CognitiveTraitInferenceService(
        trait_profile_signal_service=LearnerTraitProfileSignalService(audit_store=audit_store)
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=18000,
            expected_duration_ms=12000,
            hints_used=1,
            error_count=1,
            pause_count=2,
            modality_switches=1,
            completed=True,
            confidence=0.65,
            task_type="practice",
            support_level="medium",
        )
    ]

    traits = service.infer(student_id=student_id, observations=observations, existing_traits={})

    assert traits["processing_speed"].value > 0.45
    assert traits["working_memory"].value > 0.55
    assert traits["spatial_reasoning"].value > 0.6
