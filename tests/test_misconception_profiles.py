from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.misconception_profiles import (
    LearningMisconceptionProfileRecorder,
    LearningMisconceptionProfileResolver,
    _recurrence_decay,
)
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


def test_misconception_profile_recorder_compacts_remediation_signals(tmp_path):
    database_path = str(tmp_path / "misconception-profiles.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    recorder = LearningMisconceptionProfileRecorder(audit_store=audit_store)
    student_id = str(uuid4())

    remediation_event = audit_store.append(
        event_type="remediation.trigger",
        status="success",
        student_id=student_id,
        payload={
            "target_kc_id": "KC-2",
            "misconception_signals": [
                {
                    "kc_id": "KC-2",
                    "category": "known_misconception",
                    "confidence": 0.78,
                    "misconception_id": "fraction-whole-number-bias",
                    "recommended_kc_ids": ["KC-1"],
                    "evidence_terms": ["numerator", "denominator"],
                    "remediation_hint": "Use a visual model first.",
                }
            ],
        },
    )

    recorded = recorder.record_from_remediation_event(
        remediation_event=remediation_event
    )

    assert len(recorded) == 1
    profile_event = recorded[0]
    assert profile_event.event_type == "learning.misconception.profile"
    assert profile_event.payload["target_kc_id"] == "KC-2"
    assert profile_event.payload["matched_signal_count"] == 1
    assert profile_event.payload["matched_session_count"] == 1
    assert profile_event.payload["profile_signal"] == "tentative"
    assert profile_event.payload["recurrence_signal"] == "tentative"


def test_misconception_profile_resolver_emits_persistent_profile_signal(tmp_path):
    database_path = str(tmp_path / "misconception-profile-resolver.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    resolver = LearningMisconceptionProfileResolver()
    student_id = str(uuid4())

    audit_store.append(
        event_type="learning.misconception.profile",
        status="success",
        student_id=student_id,
        payload={
            "target_kc_id": "KC-2",
            "kc_id": "KC-2",
            "category": "known_misconception",
            "misconception_id": "fraction-whole-number-bias",
            "matched_signal_count": 3,
            "matched_session_count": 3,
            "average_confidence": 0.81,
            "profile_signal": "persistent",
            "recurrence_signal": "relapsing",
            "recommended_kc_ids": ["KC-1"],
            "evidence_terms": ["numerator", "denominator"],
            "remediation_hint": "Use a visual model first.",
            "last_seen_at": "2026-03-15T12:00:00+00:00",
        },
    )

    signals = resolver.matched_profile_signals(
        profile_events=audit_store.list(limit=50),
        target_kc_id="KC-2",
        evidence_terms={"numerator", "whole", "comparison"},
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.source == "profile"
    assert signal.misconception_id == "fraction-whole-number-bias"
    assert signal.confidence > 0.81
    assert signal.recommended_kc_ids == ["KC-1"]
    assert signal.recurrence_count == 4
    assert signal.recurrence_session_count == 4
    assert signal.recurrence_signal == "relapsing"


def test_misconception_profile_recorder_marks_recurring_and_relapsing_patterns(
    tmp_path,
):
    database_path = str(tmp_path / "misconception-profile-recurrence.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    recorder = LearningMisconceptionProfileRecorder(audit_store=audit_store)
    student_id = str(uuid4())

    for index in range(3):
        remediation_event = audit_store.append(
            event_type="remediation.trigger",
            status="success",
            student_id=student_id,
            payload={
                "remediation_session_id": f"remediation-session-{index + 1}",
                "target_kc_id": "KC-2",
                "misconception_signals": [
                    {
                        "kc_id": "KC-2",
                        "category": "known_misconception",
                        "confidence": 0.78,
                        "misconception_id": "fraction-whole-number-bias",
                        "recommended_kc_ids": ["KC-1"],
                        "evidence_terms": ["numerator", "denominator"],
                        "remediation_hint": "Use a visual model first.",
                    }
                ],
            },
        )
        recorded = recorder.record_from_remediation_event(
            remediation_event=remediation_event
        )

    assert len(recorded) == 1
    profile_event = recorded[0]
    assert profile_event.payload["matched_signal_count"] == 3
    assert profile_event.payload["matched_session_count"] == 3
    assert profile_event.payload["profile_signal"] == "persistent"
    assert profile_event.payload["recurrence_signal"] == "relapsing"


def test_recurrence_decay_no_decay_within_14_days():
    now = datetime.now(timezone.utc)
    assert _recurrence_decay(last_seen_at=now, reference_time=now) == 1.0
    assert (
        _recurrence_decay(last_seen_at=now - timedelta(days=10), reference_time=now)
        == 1.0
    )
    assert (
        _recurrence_decay(last_seen_at=now - timedelta(days=14), reference_time=now)
        == 1.0
    )


def test_recurrence_decay_moderate_after_30_days():
    now = datetime.now(timezone.utc)
    decay = _recurrence_decay(last_seen_at=now - timedelta(days=30), reference_time=now)
    assert decay == 0.8


def test_recurrence_decay_heavier_after_60_days():
    now = datetime.now(timezone.utc)
    decay = _recurrence_decay(last_seen_at=now - timedelta(days=60), reference_time=now)
    assert decay == 0.55


def test_recurrence_decay_floor_beyond_60_days():
    now = datetime.now(timezone.utc)
    decay = _recurrence_decay(
        last_seen_at=now - timedelta(days=120), reference_time=now
    )
    assert decay == 0.33


def test_recurrence_decay_none_last_seen_returns_full():
    now = datetime.now(timezone.utc)
    assert _recurrence_decay(last_seen_at=None, reference_time=now) == 1.0


def test_resolver_decays_old_recurrence_to_lower_signal(tmp_path):
    """A relapsing misconception from 90 days ago should decay its recurrence
    counts enough to downgrade the recurrence signal from relapsing to a
    weaker level."""
    database_path = str(tmp_path / "misconception-profile-decay.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    resolver = LearningMisconceptionProfileResolver()
    student_id = str(uuid4())

    # Store a profile event with high recurrence but a very old last_seen_at.
    old_date = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    audit_store.append(
        event_type="learning.misconception.profile",
        status="success",
        student_id=student_id,
        payload={
            "target_kc_id": "KC-2",
            "kc_id": "KC-2",
            "category": "known_misconception",
            "misconception_id": "fraction-whole-number-bias",
            "matched_signal_count": 4,
            "matched_session_count": 4,
            "average_confidence": 0.85,
            "profile_signal": "persistent",
            "recurrence_signal": "relapsing",
            "recommended_kc_ids": ["KC-1"],
            "evidence_terms": ["numerator", "denominator"],
            "remediation_hint": "Use a visual model first.",
            "last_seen_at": old_date,
        },
    )

    signals = resolver.matched_profile_signals(
        profile_events=audit_store.list(limit=50),
        target_kc_id="KC-2",
        evidence_terms={"numerator", "whole", "comparison"},
    )

    assert len(signals) == 1
    signal = signals[0]
    # With decay factor 0.33, effective counts: round(5 * 0.33) = 2, round(5 * 0.33) = 2
    # That's enough for "recurring" but no longer "relapsing" (needs 3 sessions + 0.7 conf)
    assert signal.recurrence_signal != "relapsing"
    assert signal.recurrence_session_count < 4  # decayed from the original 4+1


def test_resolver_preserves_recent_recurrence_signal(tmp_path):
    """A relapsing misconception from 5 days ago should keep its full recurrence
    counts and signal unchanged."""
    database_path = str(tmp_path / "misconception-profile-recent.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    audit_store = SQLiteAuditStore(conn)
    resolver = LearningMisconceptionProfileResolver()
    student_id = str(uuid4())

    recent_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    audit_store.append(
        event_type="learning.misconception.profile",
        status="success",
        student_id=student_id,
        payload={
            "target_kc_id": "KC-2",
            "kc_id": "KC-2",
            "category": "known_misconception",
            "misconception_id": "fraction-whole-number-bias",
            "matched_signal_count": 3,
            "matched_session_count": 3,
            "average_confidence": 0.85,
            "profile_signal": "persistent",
            "recurrence_signal": "relapsing",
            "recommended_kc_ids": ["KC-1"],
            "evidence_terms": ["numerator", "denominator"],
            "remediation_hint": "Use a visual model first.",
            "last_seen_at": recent_date,
        },
    )

    signals = resolver.matched_profile_signals(
        profile_events=audit_store.list(limit=50),
        target_kc_id="KC-2",
        evidence_terms={"numerator", "whole", "comparison"},
    )

    assert len(signals) == 1
    signal = signals[0]
    # No decay within 14 days — counts should be original + 1
    assert signal.recurrence_signal == "relapsing"
    assert signal.recurrence_session_count == 4  # 3 + 1 current
