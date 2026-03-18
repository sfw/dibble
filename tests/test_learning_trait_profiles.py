from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.learning_trait_profiles import (
    LearningTraitProfileRecorder,
    LearnerTraitProfileSignalService,
)
from dibble.storage import ensure_database


def test_learning_trait_profile_recorder_compacts_recent_observations(tmp_path):
    database_path = str(tmp_path / "learning-trait-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    recorder = LearningTraitProfileRecorder(audit_store=audit_store)
    observation_events = []
    for index, session_id in enumerate(
        ["session-1", "session-1", "session-2", "session-2"], start=1
    ):
        observation_events.append(
            audit_store.append(
                event_type="learner.observe",
                status="success",
                student_id=student_id,
                payload={
                    "response_time_ms": 9000 + (index * 250),
                    "expected_duration_ms": 12000,
                    "hints_used": 0,
                    "error_count": 0,
                    "pause_count": 0,
                    "modality_switches": 0,
                    "completed": True,
                    "task_type": "practice" if index % 2 else "assessment",
                    "support_level": "low",
                    "learning_session_id": session_id,
                },
            )
        )
    audit_store.append(
        event_type="learning.state.profile",
        status="success",
        student_id=student_id,
        payload={
            "state_profile_signal": "independence_ready",
            "average_run_confidence": 0.78,
            "engagement": "high",
            "total_load": 0.42,
            "confidence_calibration": 0.79,
        },
    )

    recorded = recorder.record_from_observation_events(
        observation_events=[observation_events[-1]]
    )

    assert len(recorded) == 1
    event = recorded[0]
    assert event.event_type == "learning.cognitive_trait.profile"
    assert event.payload["matched_observation_count"] == 4
    assert event.payload["matched_session_count"] == 2
    assert event.payload["profile_signal"] == "stable"
    assert event.payload["processing_speed"]["value"] > 0.7
    assert event.payload["working_memory"]["value"] > 0.6
    assert event.payload["processing_speed_reliability"] > 0.5
    assert event.payload["working_memory_reliability"] > 0.45
    assert event.payload["trait_stability"] >= 0.55
    assert event.payload["challenge_tolerance"] > 0.6
    assert event.payload["challenge_evidence_strength"] > 0.5


def test_learner_trait_profile_signal_service_returns_latest_profile(tmp_path):
    database_path = str(tmp_path / "learning-trait-profile-signal.db")
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
            "processing_speed": {"value": 0.74, "confidence": 0.78},
            "working_memory": {"value": 0.69, "confidence": 0.76},
            "spatial_reasoning": {"value": 0.63, "confidence": 0.64},
            "trait_stability": 0.78,
            "challenge_tolerance": 0.66,
            "trait_profile_rationale": "Recent learner observations were compacted into a durable cognitive-trait profile.",
        },
    )

    summary = LearnerTraitProfileSignalService(
        audit_store=audit_store
    ).latest_for_student(student_id=student_id)

    assert summary.source == "trait_profile"
    assert summary.signal == "stable"
    assert summary.matched_session_count == 3
    assert summary.processing_speed is not None
    assert summary.processing_speed.value == 0.74
    assert summary.working_memory is not None
    assert summary.working_memory.value == 0.69
    assert summary.processing_speed_reliability == 0.0
    assert summary.challenge_evidence_strength == 0.0
    assert summary.trait_stability == 0.78
    assert summary.challenge_tolerance == 0.66
