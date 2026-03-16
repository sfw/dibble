from uuid import uuid4

from dibble.models.observations import LearnerObservation
from dibble.models.profile import CognitiveTraitScore
from dibble.services.cognitive_trait_inference import CognitiveTraitInferenceService


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
