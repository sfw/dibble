from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.ordinary_mastery_profiles import (
    OrdinaryMasteryProfileRecorder,
    OrdinaryMasterySignalService,
)
from dibble.storage import ensure_database


def test_ordinary_mastery_profile_recorder_compacts_stable_low_support_evidence(tmp_path):
    database_path = str(tmp_path / "ordinary-mastery-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    recorder = OrdinaryMasteryProfileRecorder(audit_store=audit_store)

    observation_events = []
    for index, session_id in enumerate(["session-1", "session-1", "session-2", "session-2"], start=1):
        observation_events.append(
            audit_store.append(
                event_type="learner.observe",
                status="success",
                student_id=student_id,
                payload={
                    "task_type": "practice",
                    "completed": True,
                    "support_level": "low",
                    "hints_used": 0,
                    "error_count": 0,
                    "learning_session_id": session_id,
                    "target_kc_ids": ["KC-2"],
                    "target_lo_ids": ["LO-1"],
                    "observation_mastery_applied": True,
                    "observation_inferred_mastery": 0.72 + (index * 0.02),
                    "observation_average_recent_mastery": 0.72 + (index * 0.02),
                },
            )
        )

    recorded = recorder.record_from_observation_events(observation_events=[observation_events[-1]])

    assert len(recorded) == 1
    event = recorded[0]
    assert event.event_type == "learning.ordinary_mastery.profile"
    assert event.payload["profile_signal"] == "durable_mastery"
    assert event.payload["matched_observation_count"] == 4
    assert event.payload["matched_session_count"] == 2
    assert event.payload["average_observed_mastery"] >= 0.76
    assert event.payload["low_support_success_rate"] >= 0.75
    assert event.payload["high_support_dependency_rate"] == 0.0


def test_ordinary_mastery_signal_service_prefers_target_matching_profile(tmp_path):
    database_path = str(tmp_path / "ordinary-mastery-signal.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.ordinary_mastery.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "target_kc_ids": ["KC-1"],
            "target_lo_ids": ["LO-1"],
            "profile_signal": "support_dependent",
            "profile_confidence": 0.74,
            "matched_observation_count": 3,
            "matched_session_count": 2,
            "average_observed_mastery": 0.56,
            "low_support_success_rate": 0.0,
            "high_support_dependency_rate": 0.67,
            "ordinary_mastery_profile_rationale": "Practice evidence stayed support-heavy.",
        },
    )
    audit_store.append(
        event_type="learning.ordinary_mastery.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "target_kc_ids": ["KC-2"],
            "target_lo_ids": ["LO-1"],
            "profile_signal": "durable_mastery",
            "profile_confidence": 0.82,
            "matched_observation_count": 5,
            "matched_session_count": 3,
            "average_observed_mastery": 0.78,
            "low_support_success_rate": 0.8,
            "high_support_dependency_rate": 0.0,
            "ordinary_mastery_profile_rationale": "Practice evidence stayed strong.",
        },
    )

    summary = OrdinaryMasterySignalService(audit_store=audit_store).latest_for_student(
        student_id=student_id,
        target_kc_ids=["KC-2"],
        target_lo_ids=["LO-1"],
    )

    assert summary.source == "ordinary_mastery_profile"
    assert summary.signal == "durable_mastery"
    assert summary.confidence == 0.82
    assert summary.matched_observation_count == 5
    assert summary.average_observed_mastery == 0.78
    assert summary.low_support_success_rate == 0.8
    assert summary.high_support_dependency_rate == 0.0
