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
        existing_traits={
            "working_memory": CognitiveTraitScore(value=0.8, confidence=0.8)
        },
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
            "processing_speed_reliability": 0.78,
            "working_memory_reliability": 0.74,
            "spatial_reasoning_reliability": 0.62,
            "trait_stability": 0.8,
            "challenge_tolerance": 0.68,
            "challenge_evidence_strength": 0.7,
        },
    )
    service = CognitiveTraitInferenceService(
        trait_profile_signal_service=LearnerTraitProfileSignalService(
            audit_store=audit_store
        )
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

    traits = service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )

    assert traits["processing_speed"].value > 0.45
    assert traits["working_memory"].value > 0.55
    assert traits["spatial_reasoning"].value > 0.6


def test_cognitive_trait_inference_uses_trait_stability_and_challenge_tolerance_in_durable_blend(
    tmp_path,
):
    database_path = str(tmp_path / "cognitive-trait-profile-stability.db")
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
            "processing_speed": {"value": 0.86, "confidence": 0.84},
            "working_memory": {"value": 0.79, "confidence": 0.8},
            "processing_speed_reliability": 0.8,
            "working_memory_reliability": 0.78,
            "spatial_reasoning_reliability": 0.0,
            "trait_stability": 0.82,
            "challenge_tolerance": 0.78,
            "challenge_evidence_strength": 0.8,
        },
    )
    service = CognitiveTraitInferenceService(
        trait_profile_signal_service=LearnerTraitProfileSignalService(
            audit_store=audit_store
        )
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=15000,
            expected_duration_ms=12000,
            hints_used=1,
            error_count=1,
            pause_count=1,
            modality_switches=0,
            completed=True,
            confidence=0.68,
            task_type="practice",
            support_level="low",
        )
    ]

    traits = service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )

    assert traits["working_memory"].value > 0.6
    assert traits["processing_speed"].value > 0.55


def test_cognitive_trait_inference_downweights_mismatched_tentative_durable_profile(
    tmp_path,
):
    database_path = str(tmp_path / "cognitive-trait-profile-mismatch.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.cognitive_trait.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "matched_observation_count": 5,
            "matched_session_count": 2,
            "profile_signal": "tentative",
            "processing_speed": {"value": 0.88, "confidence": 0.8},
            "working_memory": {"value": 0.9, "confidence": 0.82},
            "processing_speed_reliability": 0.5,
            "working_memory_reliability": 0.54,
            "spatial_reasoning_reliability": 0.0,
            "trait_stability": 0.54,
            "challenge_tolerance": 0.4,
            "challenge_evidence_strength": 0.42,
        },
    )
    service = CognitiveTraitInferenceService(
        trait_profile_signal_service=LearnerTraitProfileSignalService(
            audit_store=audit_store
        )
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=28000,
            expected_duration_ms=12000,
            hints_used=3,
            error_count=3,
            pause_count=2,
            modality_switches=2,
            completed=False,
            confidence=0.35,
            task_type="practice",
            support_level="low",
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=26000,
            expected_duration_ms=12000,
            hints_used=2,
            error_count=2,
            pause_count=2,
            modality_switches=1,
            completed=False,
            confidence=0.38,
            task_type="assessment",
            support_level="low",
        ),
    ]

    traits = service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )

    assert traits["working_memory"].value < 0.65
    assert traits["processing_speed"].value < 0.65


def test_cognitive_trait_inference_downweights_stable_durable_profile_when_current_challenge_evidence_is_strong(
    tmp_path,
):
    database_path = str(tmp_path / "cognitive-trait-profile-strong-current.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.cognitive_trait.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "matched_observation_count": 8,
            "matched_session_count": 4,
            "profile_signal": "stable",
            "processing_speed": {"value": 0.9, "confidence": 0.86},
            "working_memory": {"value": 0.88, "confidence": 0.84},
            "processing_speed_reliability": 0.82,
            "working_memory_reliability": 0.8,
            "spatial_reasoning_reliability": 0.0,
            "trait_stability": 0.85,
            "challenge_tolerance": 0.42,
            "challenge_evidence_strength": 0.82,
        },
    )
    baseline_service = CognitiveTraitInferenceService()
    blended_service = CognitiveTraitInferenceService(
        trait_profile_signal_service=LearnerTraitProfileSignalService(
            audit_store=audit_store
        )
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=28000,
            expected_duration_ms=12000,
            hints_used=3,
            error_count=3,
            pause_count=2,
            modality_switches=2,
            completed=False,
            confidence=0.32,
            task_type="practice",
            support_level="low",
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=26000,
            expected_duration_ms=12000,
            hints_used=2,
            error_count=2,
            pause_count=1,
            modality_switches=1,
            completed=False,
            confidence=0.34,
            task_type="assessment",
            support_level="low",
        ),
        LearnerObservation(
            observation_id="obs-3",
            student_id=student_id,
            response_time_ms=24000,
            expected_duration_ms=12000,
            hints_used=2,
            error_count=2,
            pause_count=1,
            modality_switches=1,
            completed=False,
            confidence=0.36,
            task_type="practice",
            support_level="low",
        ),
    ]

    baseline = baseline_service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )
    blended = blended_service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )

    assert blended["working_memory"].value <= baseline["working_memory"].value + 0.05
    assert (
        blended["processing_speed"].value <= baseline["processing_speed"].value + 0.05
    )


def test_cognitive_trait_inference_uses_stable_durable_profile_more_when_current_evidence_is_sparse(
    tmp_path,
):
    database_path = str(tmp_path / "cognitive-trait-profile-sparse-current.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.cognitive_trait.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "matched_observation_count": 7,
            "matched_session_count": 4,
            "profile_signal": "stable",
            "processing_speed": {"value": 0.84, "confidence": 0.82},
            "working_memory": {"value": 0.8, "confidence": 0.8},
            "spatial_reasoning": {"value": 0.76, "confidence": 0.74},
            "processing_speed_reliability": 0.82,
            "working_memory_reliability": 0.78,
            "spatial_reasoning_reliability": 0.74,
            "trait_stability": 0.84,
            "challenge_tolerance": 0.76,
            "challenge_evidence_strength": 0.76,
        },
    )
    baseline_service = CognitiveTraitInferenceService()
    blended_service = CognitiveTraitInferenceService(
        trait_profile_signal_service=LearnerTraitProfileSignalService(
            audit_store=audit_store
        )
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=19000,
            expected_duration_ms=16000,
            hints_used=1,
            error_count=1,
            pause_count=1,
            modality_switches=0,
            completed=True,
            confidence=0.66,
            task_type="worked_example",
            support_level="high",
        )
    ]

    baseline = baseline_service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )
    blended = blended_service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )

    assert blended["spatial_reasoning"].value > baseline["spatial_reasoning"].value
    assert blended["processing_speed"].value > baseline["processing_speed"].value


def test_cognitive_trait_inference_prefers_reliable_durable_traits_over_unreliable_ones(
    tmp_path,
):
    database_path = str(tmp_path / "cognitive-trait-profile-reliability.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.cognitive_trait.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "matched_observation_count": 8,
            "matched_session_count": 4,
            "profile_signal": "stable",
            "processing_speed": {"value": 0.9, "confidence": 0.84},
            "working_memory": {"value": 0.86, "confidence": 0.82},
            "processing_speed_reliability": 0.24,
            "working_memory_reliability": 0.84,
            "spatial_reasoning_reliability": 0.0,
            "trait_stability": 0.82,
            "challenge_tolerance": 0.74,
            "challenge_evidence_strength": 0.82,
        },
    )
    baseline_service = CognitiveTraitInferenceService()
    blended_service = CognitiveTraitInferenceService(
        trait_profile_signal_service=LearnerTraitProfileSignalService(
            audit_store=audit_store
        )
    )
    observations = [
        LearnerObservation(
            observation_id="obs-1",
            student_id=student_id,
            response_time_ms=18000,
            expected_duration_ms=12000,
            hints_used=1,
            error_count=1,
            pause_count=1,
            modality_switches=0,
            completed=True,
            confidence=0.7,
            task_type="practice",
            support_level="low",
        ),
        LearnerObservation(
            observation_id="obs-2",
            student_id=student_id,
            response_time_ms=17000,
            expected_duration_ms=12000,
            hints_used=1,
            error_count=1,
            pause_count=1,
            modality_switches=0,
            completed=True,
            confidence=0.68,
            task_type="assessment",
            support_level="low",
        ),
    ]

    baseline = baseline_service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )
    blended = blended_service.infer(
        student_id=student_id, observations=observations, existing_traits={}
    )

    assert blended["working_memory"].value - baseline["working_memory"].value >= 0.04
    assert (
        blended["processing_speed"].value <= baseline["processing_speed"].value + 0.03
    )
