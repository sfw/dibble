from uuid import uuid4

from dibble.models.observations import LearnerObservation
from dibble.models.profile import SignalLevel
from dibble.services.state_inference import LearnerStateInferenceService


def test_state_inference_detects_high_frustration_and_load():
    service = LearnerStateInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=28000,
            hints_used=3,
            error_count=3,
            pause_count=4,
            modality_switches=2,
            completed=False,
            confidence=0.2,
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=32000,
            hints_used=2,
            error_count=2,
            pause_count=3,
            modality_switches=1,
            completed=False,
            confidence=0.25,
        ),
    ]

    inferred = service.infer(student_id=student_id, observations=observations)

    assert inferred.affective_state.frustration == SignalLevel.high
    assert inferred.affective_state.confusion in {SignalLevel.medium, SignalLevel.high}
    assert inferred.cognitive_load.total_load >= 0.6
    assert inferred.metacognitive_state.help_seeking in {SignalLevel.medium, SignalLevel.high}
    assert inferred.metacognitive_state.confidence_calibration >= 0.7
    assert inferred.metacognitive_state.self_monitoring <= 0.5
    assert inferred.observation_count == 2


def test_state_inference_tracks_calibrated_confidence_when_performance_matches():
    service = LearnerStateInferenceService()
    student_id = uuid4()
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=9000,
            hints_used=1,
            error_count=0,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.9,
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=11000,
            hints_used=0,
            error_count=0,
            pause_count=0,
            modality_switches=0,
            completed=True,
            confidence=0.85,
        ),
    ]

    inferred = service.infer(student_id=student_id, observations=observations)

    assert inferred.metacognitive_state.confidence_calibration >= 0.8
    assert inferred.metacognitive_state.help_seeking in {SignalLevel.none, SignalLevel.low}
    assert inferred.metacognitive_state.self_monitoring >= 0.6
