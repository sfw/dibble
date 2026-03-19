from __future__ import annotations

from uuid import uuid4

from dibble.models.profile import (
    AffectiveState,
    CognitiveLoadState,
    KnowledgeState,
    LearnerProfile,
    SignalLevel,
)
from dibble.services.mastery_snapshot_service import MasterySnapshotService
from dibble.services.mastery_snapshot_store import SQLiteMasterySnapshotStore
from dibble.storage import ensure_database


def _store(tmp_path) -> SQLiteMasterySnapshotStore:
    db = str(tmp_path / "test.db")
    ensure_database(db)
    return SQLiteMasterySnapshotStore(db)


_SENTINEL = object()


def _profile(
    student_id=None,
    *,
    kc_mastery=_SENTINEL,
    lo_mastery=_SENTINEL,
    engagement=SignalLevel.medium,
    frustration=SignalLevel.none,
    total_load=0.4,
):
    return LearnerProfile(
        student_id=student_id or uuid4(),
        grade_level="5",
        knowledge_state=KnowledgeState(
            kc_mastery={"KC-1": 0.5, "KC-2": 0.8}
            if kc_mastery is _SENTINEL
            else kc_mastery,
            lo_mastery={"LO-1": 0.6} if lo_mastery is _SENTINEL else lo_mastery,
        ),
        affective_state=AffectiveState(
            engagement=engagement,
            frustration=frustration,
        ),
        cognitive_load=CognitiveLoadState(total_load=total_load),
    )


def test_store_record_and_retrieve(tmp_path):
    store = _store(tmp_path)
    sid = str(uuid4())
    snapshot = store.record(
        student_id=sid,
        overall_kc_mastery=0.65,
        overall_lo_mastery=0.6,
        kc_count=2,
        lo_count=1,
        mastered_kc_count=1,
        struggling_kc_count=0,
        engagement="medium",
        frustration="none",
        total_load=0.4,
    )
    assert snapshot.student_id == sid
    assert snapshot.overall_kc_mastery == 0.65
    retrieved = store.list_for_student(student_id=sid, days=30)
    assert len(retrieved) == 1
    assert retrieved[0].snapshot_id == snapshot.snapshot_id


def test_store_filters_by_student(tmp_path):
    store = _store(tmp_path)
    sid_a = str(uuid4())
    sid_b = str(uuid4())
    store.record(
        student_id=sid_a,
        overall_kc_mastery=0.5,
        overall_lo_mastery=0.5,
        kc_count=1,
        lo_count=1,
        mastered_kc_count=0,
        struggling_kc_count=0,
        engagement="medium",
        frustration="none",
        total_load=0.4,
    )
    store.record(
        student_id=sid_b,
        overall_kc_mastery=0.7,
        overall_lo_mastery=0.7,
        kc_count=1,
        lo_count=1,
        mastered_kc_count=1,
        struggling_kc_count=0,
        engagement="medium",
        frustration="none",
        total_load=0.3,
    )
    assert len(store.list_for_student(student_id=sid_a, days=30)) == 1
    assert len(store.list_for_student(student_id=sid_b, days=30)) == 1


def test_store_returns_chronological_order(tmp_path):
    store = _store(tmp_path)
    sid = str(uuid4())
    s1 = store.record(
        student_id=sid,
        overall_kc_mastery=0.3,
        overall_lo_mastery=0.3,
        kc_count=1,
        lo_count=1,
        mastered_kc_count=0,
        struggling_kc_count=1,
        engagement="low",
        frustration="high",
        total_load=0.8,
    )
    s2 = store.record(
        student_id=sid,
        overall_kc_mastery=0.5,
        overall_lo_mastery=0.5,
        kc_count=1,
        lo_count=1,
        mastered_kc_count=0,
        struggling_kc_count=0,
        engagement="medium",
        frustration="none",
        total_load=0.5,
    )
    retrieved = store.list_for_student(student_id=sid, days=30)
    assert len(retrieved) == 2
    assert retrieved[0].snapshot_id == s1.snapshot_id
    assert retrieved[1].snapshot_id == s2.snapshot_id


def test_service_record_from_profile(tmp_path):
    store = _store(tmp_path)
    service = MasterySnapshotService(snapshot_store=store)
    sid = uuid4()
    profile = _profile(
        sid,
        kc_mastery={"KC-1": 0.9, "KC-2": 0.3, "KC-3": 0.6},
        lo_mastery={"LO-1": 0.7},
    )
    snapshot = service.record_from_profile(profile)
    assert snapshot.student_id == str(sid)
    assert snapshot.kc_count == 3
    assert snapshot.lo_count == 1
    assert snapshot.mastered_kc_count == 1  # KC-1 >= 0.75
    assert snapshot.struggling_kc_count == 1  # KC-2 < 0.35
    assert 0.59 <= snapshot.overall_kc_mastery <= 0.61  # mean(0.9, 0.3, 0.6) = 0.6


def test_service_record_from_profile_empty_mastery(tmp_path):
    store = _store(tmp_path)
    service = MasterySnapshotService(snapshot_store=store)
    profile = _profile(kc_mastery={}, lo_mastery={})
    snapshot = service.record_from_profile(profile)
    assert snapshot.overall_kc_mastery == 0.0
    assert snapshot.overall_lo_mastery == 0.0
    assert snapshot.kc_count == 0
    assert snapshot.mastered_kc_count == 0


def test_service_get_learner_history(tmp_path):
    store = _store(tmp_path)
    service = MasterySnapshotService(snapshot_store=store)
    sid = uuid4()
    profile = _profile(sid)
    service.record_from_profile(profile)
    service.record_from_profile(profile)
    history = service.get_learner_history(student_id=sid, days=30)
    assert history.student_id == str(sid)
    assert history.days == 30
    assert history.snapshot_count == 2
    assert len(history.snapshots) == 2


def test_service_get_learner_history_empty(tmp_path):
    store = _store(tmp_path)
    service = MasterySnapshotService(snapshot_store=store)
    sid = uuid4()
    history = service.get_learner_history(student_id=sid, days=30)
    assert history.snapshot_count == 0
    assert history.snapshots == []


def test_service_get_section_trends(tmp_path):
    store = _store(tmp_path)
    service = MasterySnapshotService(snapshot_store=store)
    sid_a = uuid4()
    sid_b = uuid4()
    service.record_from_profile(_profile(sid_a, kc_mastery={"KC-1": 0.4}))
    service.record_from_profile(_profile(sid_b, kc_mastery={"KC-1": 0.8}))

    trends = service.get_section_trends(
        section_id="CLASS-1",
        student_ids=[str(sid_a), str(sid_b)],
        days=30,
    )
    assert trends.section_id == "CLASS-1"
    assert trends.learner_count == 2
    assert len(trends.learner_trends) == 2
    assert len(trends.section_average_snapshots) >= 1
    avg = trends.section_average_snapshots[0].average_mastery
    assert 0.5 <= avg <= 0.7  # average of 0.4 and 0.8


def test_service_section_trends_learner_delta(tmp_path):
    store = _store(tmp_path)
    service = MasterySnapshotService(snapshot_store=store)
    sid = uuid4()
    service.record_from_profile(_profile(sid, kc_mastery={"KC-1": 0.3}))
    service.record_from_profile(_profile(sid, kc_mastery={"KC-1": 0.7}))

    trends = service.get_section_trends(
        section_id="CLASS-1",
        student_ids=[str(sid)],
        days=30,
    )
    learner_trend = trends.learner_trends[0]
    assert learner_trend.earliest_mastery == 0.3
    assert learner_trend.latest_mastery == 0.7
    assert learner_trend.mastery_delta == 0.4


def test_service_section_trends_empty_student_list(tmp_path):
    store = _store(tmp_path)
    service = MasterySnapshotService(snapshot_store=store)
    trends = service.get_section_trends(
        section_id="CLASS-1",
        student_ids=[],
        days=30,
    )
    assert trends.learner_count == 0
    assert trends.learner_trends == []
    assert trends.section_average_snapshots == []


def test_service_captures_affective_state(tmp_path):
    store = _store(tmp_path)
    service = MasterySnapshotService(snapshot_store=store)
    sid = uuid4()
    profile = _profile(
        sid,
        engagement=SignalLevel.low,
        frustration=SignalLevel.high,
        total_load=0.9,
    )
    snapshot = service.record_from_profile(profile)
    assert snapshot.engagement == "low"
    assert snapshot.frustration == "high"
    assert snapshot.total_load == 0.9
