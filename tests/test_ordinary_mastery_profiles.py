from uuid import UUID, uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.ordinary_mastery_profiles import (
    OrdinaryMasteryProfileBuilder,
    OrdinaryMasteryProfileRecorder,
    OrdinaryMasterySignalService,
)
from dibble.storage import ensure_database


def test_ordinary_mastery_profile_recorder_compacts_stable_low_support_evidence(
    tmp_path,
):
    database_path = str(tmp_path / "ordinary-mastery-profile.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    recorder = OrdinaryMasteryProfileRecorder(audit_store=audit_store)

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

    recorded = recorder.record_from_observation_events(
        observation_events=[observation_events[-1]]
    )

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


def test_ordinary_mastery_signal_service_does_not_fallback_to_unrelated_profile(
    tmp_path,
):
    database_path = str(tmp_path / "ordinary-mastery-unrelated.db")
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

    summary = OrdinaryMasterySignalService(audit_store=audit_store).latest_for_student(
        student_id=student_id,
        target_kc_ids=["KC-9"],
        target_lo_ids=["LO-9"],
    )

    assert summary.signal == "insufficient"
    assert summary.source == "insufficient"
    assert summary.confidence == 0.0


def test_mastery_trend_improving_when_recent_scores_higher():
    builder = OrdinaryMasteryProfileBuilder()
    # Scores are newest-first: recent observations scored higher than older ones.
    mastery_scores = [0.78, 0.74, 0.70, 0.60, 0.55, 0.50]
    weights = [1.0, 0.95, 0.90, 0.80, 0.75, 0.70]
    assert (
        builder._mastery_trend(mastery_scores=mastery_scores, weights=weights)
        == "improving"
    )


def test_mastery_trend_declining_when_recent_scores_lower():
    builder = OrdinaryMasteryProfileBuilder()
    # Scores are newest-first: recent observations scored lower than older ones.
    mastery_scores = [0.50, 0.55, 0.60, 0.70, 0.74, 0.78]
    weights = [1.0, 0.95, 0.90, 0.80, 0.75, 0.70]
    assert (
        builder._mastery_trend(mastery_scores=mastery_scores, weights=weights)
        == "declining"
    )


def test_mastery_trend_stable_when_scores_flat():
    builder = OrdinaryMasteryProfileBuilder()
    mastery_scores = [0.65, 0.64, 0.66, 0.65, 0.64]
    weights = [1.0, 0.95, 0.90, 0.85, 0.80]
    assert (
        builder._mastery_trend(mastery_scores=mastery_scores, weights=weights)
        == "stable"
    )


def test_mastery_trend_stable_with_fewer_than_three_scores():
    builder = OrdinaryMasteryProfileBuilder()
    assert (
        builder._mastery_trend(mastery_scores=[0.80, 0.50], weights=[1.0, 0.9])
        == "stable"
    )
    assert builder._mastery_trend(mastery_scores=[0.50], weights=[1.0]) == "stable"


def test_improving_trend_rescues_borderline_fragile_to_emerging():
    builder = OrdinaryMasteryProfileBuilder()
    # Average mastery is 0.48 (< 0.52 threshold for fragile), but improving
    # trend from older 0.40 to recent 0.56 should rescue to emerging_mastery.
    signal = builder._signal_label(
        matched_observation_count=4,
        matched_session_count=2,
        average_observed_mastery=0.48,
        low_support_success_rate=0.2,
        high_support_dependency_rate=0.2,
        mastery_trend="improving",
    )
    assert signal == "emerging_mastery"


def test_declining_trend_downgrades_borderline_durable_to_emerging():
    builder = OrdinaryMasteryProfileBuilder()
    # Normally durable: high mastery, stable observations, low dependency.
    # But a declining trend with mastery < 0.78 should downgrade to emerging.
    signal = builder._signal_label(
        matched_observation_count=5,
        matched_session_count=2,
        average_observed_mastery=0.74,
        low_support_success_rate=0.6,
        high_support_dependency_rate=0.1,
        mastery_trend="declining",
    )
    assert signal == "emerging_mastery"


def test_declining_trend_does_not_downgrade_strong_durable():
    builder = OrdinaryMasteryProfileBuilder()
    # Very strong durable mastery (>= 0.78) should not be downgraded.
    signal = builder._signal_label(
        matched_observation_count=6,
        matched_session_count=3,
        average_observed_mastery=0.82,
        low_support_success_rate=0.7,
        high_support_dependency_rate=0.1,
        mastery_trend="declining",
    )
    assert signal == "durable_mastery"


def test_mastery_trend_persisted_and_read_back(tmp_path):
    database_path = str(tmp_path / "trend-roundtrip.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    recorder = OrdinaryMasteryProfileRecorder(audit_store=audit_store)

    # Create observations with improving scores across two sessions.
    observation_events = []
    scores = [0.55, 0.60, 0.68, 0.74, 0.78, 0.80]
    sessions = ["s1", "s1", "s1", "s2", "s2", "s2"]
    for index, (session_id, score) in enumerate(zip(sessions, scores)):
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
                    "target_kc_ids": ["KC-T"],
                    "target_lo_ids": ["LO-T"],
                    "observation_mastery_applied": True,
                    "observation_inferred_mastery": score,
                    "observation_average_recent_mastery": score,
                },
            )
        )

    recorded = recorder.record_from_observation_events(
        observation_events=[observation_events[-1]]
    )
    assert len(recorded) == 1
    assert recorded[0].payload["mastery_trend"] == "improving"

    # Read it back through the signal service.
    summary = OrdinaryMasterySignalService(audit_store=audit_store).latest_for_student(
        student_id=UUID(student_id),
        target_kc_ids=["KC-T"],
        target_lo_ids=["LO-T"],
    )
    assert summary.mastery_trend == "improving"


def test_mastery_volatility_zero_for_consistent_scores():
    builder = OrdinaryMasteryProfileBuilder()
    # All scores are identical — volatility should be 0.
    mastery_scores = [0.70, 0.70, 0.70, 0.70]
    weights = [1.0, 0.95, 0.90, 0.85]
    volatility = builder._mastery_volatility(
        mastery_scores=mastery_scores,
        weights=weights,
        average_observed_mastery=0.70,
    )
    assert volatility == 0.0


def test_mastery_volatility_high_for_oscillating_scores():
    builder = OrdinaryMasteryProfileBuilder()
    # Large swings: 0.8 -> 0.4 -> 0.8 -> 0.4 — this is highly volatile.
    mastery_scores = [0.80, 0.40, 0.80, 0.40]
    weights = [1.0, 0.95, 0.90, 0.85]
    avg = round(sum(s * w for s, w in zip(mastery_scores, weights)) / sum(weights), 2)
    volatility = builder._mastery_volatility(
        mastery_scores=mastery_scores,
        weights=weights,
        average_observed_mastery=avg,
    )
    assert volatility >= 0.18  # should be highly volatile


def test_mastery_volatility_moderate_for_mild_instability():
    builder = OrdinaryMasteryProfileBuilder()
    # Moderate swings: 0.70, 0.55, 0.68, 0.52 — meaningful instability.
    mastery_scores = [0.70, 0.55, 0.68, 0.52]
    weights = [1.0, 0.95, 0.90, 0.85]
    avg = round(sum(s * w for s, w in zip(mastery_scores, weights)) / sum(weights), 2)
    volatility = builder._mastery_volatility(
        mastery_scores=mastery_scores,
        weights=weights,
        average_observed_mastery=avg,
    )
    assert 0.05 < volatility < 0.18


def test_mastery_volatility_zero_for_single_score():
    builder = OrdinaryMasteryProfileBuilder()
    assert (
        builder._mastery_volatility(
            mastery_scores=[0.65], weights=[1.0], average_observed_mastery=0.65
        )
        == 0.0
    )


def test_mastery_volatility_persisted_and_read_back(tmp_path):
    database_path = str(tmp_path / "volatility-roundtrip.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = str(uuid4())
    recorder = OrdinaryMasteryProfileRecorder(audit_store=audit_store)

    # Create oscillating observations across two sessions.
    observation_events = []
    scores = [0.80, 0.42, 0.78, 0.40, 0.82, 0.44]
    sessions = ["s1", "s1", "s1", "s2", "s2", "s2"]
    for session_id, score in zip(sessions, scores):
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
                    "target_kc_ids": ["KC-V"],
                    "target_lo_ids": ["LO-V"],
                    "observation_mastery_applied": True,
                    "observation_inferred_mastery": score,
                    "observation_average_recent_mastery": score,
                },
            )
        )

    recorded = recorder.record_from_observation_events(
        observation_events=[observation_events[-1]]
    )
    assert len(recorded) == 1
    assert recorded[0].payload["mastery_volatility"] >= 0.15

    # Read it back through the signal service.
    summary = OrdinaryMasterySignalService(audit_store=audit_store).latest_for_student(
        student_id=UUID(student_id),
        target_kc_ids=["KC-V"],
        target_lo_ids=["LO-V"],
    )
    assert summary.mastery_volatility >= 0.15
