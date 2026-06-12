from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from dibble.models.mastery_history import MasteryHistoryResponse, MasterySnapshot
from dibble.models.telemetry import AuditEvent
from dibble.services.baseline_policy import (
    BASELINE_DECISION_EVENT_TYPE,
    BaselinePolicyService,
)
from dibble.services.pilot_metrics import (
    DEFECT_REPORT_EVENT_TYPE,
    GENERATION_EVENT_TYPE,
    INTERVENTION_DECISION_EVENT_TYPE,
    SESSION_COMPLETED_EVENT_TYPE,
    SESSION_STARTED_EVENT_TYPE,
    PilotMetricsService,
)


class StubAuditStore:
    def __init__(self, events: list[AuditEvent]) -> None:
        self._events = events

    def append(self, **kwargs: object) -> AuditEvent:
        raise NotImplementedError

    def list(self, *, limit: int = 50) -> list[AuditEvent]:
        return self._events[:limit]


class StubProfileStore:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def list_ids(self) -> list[str]:
        return list(self._ids)

    def get(self, student_id: UUID) -> None:
        return None


class StubMasterySnapshotService:
    def __init__(self, snapshots: dict[str, list[MasterySnapshot]]) -> None:
        self._snapshots = snapshots

    def get_learner_history(
        self, *, student_id: UUID, days: int = 30
    ) -> MasteryHistoryResponse:
        snapshots = self._snapshots.get(str(student_id), [])
        return MasteryHistoryResponse(
            student_id=str(student_id),
            days=days,
            snapshot_count=len(snapshots),
            snapshots=snapshots,
        )


def _event(
    *,
    student_id: UUID,
    event_type: str,
    status: str = "success",
    payload: dict[str, object] | None = None,
    created_at: datetime | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        status=status,
        student_id=student_id,
        payload=payload or {},
        created_at=created_at or datetime.now(timezone.utc),
    )


def _snapshot(student_id: UUID, mastery: float, at: datetime) -> MasterySnapshot:
    return MasterySnapshot(
        snapshot_id=str(uuid4()),
        student_id=str(student_id),
        overall_kc_mastery=mastery,
        overall_lo_mastery=mastery,
        kc_count=10,
        lo_count=4,
        mastered_kc_count=int(mastery * 10),
        struggling_kc_count=0,
        created_at=at,
    )


def _service(
    events: list[AuditEvent],
    *,
    profile_ids: list[str] | None = None,
    snapshots: dict[str, list[MasterySnapshot]] | None = None,
) -> PilotMetricsService:
    audit_store = StubAuditStore(events)
    return PilotMetricsService(
        audit_store=audit_store,
        profile_store=StubProfileStore(profile_ids or []),
        mastery_snapshot_service=StubMasterySnapshotService(snapshots or {}),
        baseline_policy_service=BaselinePolicyService(audit_store=audit_store),
    )


def test_summarize_counts_sessions_and_return_rates() -> None:
    student_id = uuid4()
    base = datetime.now(timezone.utc) - timedelta(days=5)
    events = [
        _event(
            student_id=student_id,
            event_type=SESSION_STARTED_EVENT_TYPE,
            created_at=base + timedelta(days=offset),
        )
        for offset in (0, 1, 2, 4)
    ] + [
        _event(
            student_id=student_id,
            event_type=SESSION_COMPLETED_EVENT_TYPE,
            created_at=base + timedelta(days=offset, hours=1),
        )
        for offset in (0, 1, 2)
    ]

    response = _service(events).summarize(days=30)

    assert len(response.learners) == 1
    learner = response.learners[0]
    assert learner.sessions.sessions_started == 4
    assert learner.sessions.sessions_completed == 3
    assert learner.sessions.completion_rate == 0.75
    assert learner.sessions.active_days == 4
    # 4 active days -> 3 transitions, 2 of which are consecutive days.
    assert learner.sessions.day_over_day_return_rate == round(2 / 3, 4)


def test_summarize_aggregates_mastery_deltas() -> None:
    student_id = uuid4()
    base = datetime.now(timezone.utc) - timedelta(days=10)
    snapshots = {
        str(student_id): [
            _snapshot(student_id, 0.4, base),
            _snapshot(student_id, 0.65, base + timedelta(days=9)),
        ]
    }

    response = _service(
        [], profile_ids=[str(student_id)], snapshots=snapshots
    ).summarize(days=30)

    learner = response.learners[0]
    assert learner.mastery.snapshot_count == 2
    assert learner.mastery.kc_mastery_delta == 0.25
    assert response.cohort.average_kc_mastery_delta == 0.25


def test_summarize_counts_defects_interventions_and_baseline() -> None:
    student_id = uuid4()
    events = [
        _event(student_id=student_id, event_type=DEFECT_REPORT_EVENT_TYPE),
        _event(
            student_id=student_id,
            event_type=INTERVENTION_DECISION_EVENT_TYPE,
            payload={"decision": "approve"},
        ),
        _event(
            student_id=student_id,
            event_type=INTERVENTION_DECISION_EVENT_TYPE,
            payload={"decision": "escalate"},
        ),
        _event(
            student_id=student_id,
            event_type=BASELINE_DECISION_EVENT_TYPE,
            status="agreed",
            payload={"decision_point": "router.route"},
        ),
        _event(
            student_id=student_id,
            event_type=BASELINE_DECISION_EVENT_TYPE,
            status="diverged",
            payload={"decision_point": "router.route"},
        ),
    ]

    response = _service(events).summarize(days=30)

    learner = response.learners[0]
    assert learner.defect_report_count == 1
    assert learner.intervention_decision_counts == {"approve": 1, "escalate": 1}
    assert learner.baseline_decision_count == 2
    assert learner.baseline_agreement_rate == 0.5
    assert response.baseline.total_decisions == 2
    assert response.baseline.agreement_rate == 0.5
    assert response.cohort.intervention_decision_counts == {
        "approve": 1,
        "escalate": 1,
    }


def test_summarize_aggregates_generation_cost_and_latency() -> None:
    student_id = uuid4()
    events = [
        _event(
            student_id=student_id,
            event_type=GENERATION_EVENT_TYPE,
            payload={
                "generation_latency_ms": 1200,
                "prompt_tokens": 900,
                "completion_tokens": 350,
                "cache_hit": False,
            },
        ),
        _event(
            student_id=student_id,
            event_type=GENERATION_EVENT_TYPE,
            payload={
                "generation_latency_ms": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cache_hit": True,
            },
        ),
    ]

    response = _service(events).summarize(days=30)

    generation = response.learners[0].generation
    assert generation.generation_count == 2
    assert generation.cache_hits == 1
    assert generation.average_latency_ms == 600.0
    assert generation.total_prompt_tokens == 900
    assert generation.total_completion_tokens == 350
    assert response.cohort.total_prompt_tokens == 900


def test_summarize_includes_profile_only_learners() -> None:
    quiet_learner = uuid4()
    response = _service([], profile_ids=[str(quiet_learner)]).summarize(days=30)

    assert len(response.learners) == 1
    assert response.learners[0].sessions.sessions_started == 0
    assert response.learners[0].mastery.snapshot_count == 0


def test_summarize_excludes_events_older_than_window() -> None:
    student_id = uuid4()
    old_event = _event(
        student_id=student_id,
        event_type=SESSION_STARTED_EVENT_TYPE,
        created_at=datetime.now(timezone.utc) - timedelta(days=120),
    )

    response = _service([old_event]).summarize(days=30)

    assert response.learners == []


def test_pilot_metrics_endpoint_returns_payload(client, student_id) -> None:
    response = client.get("/api/admin/pilot-metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["days"] == 90
    assert "cohort" in payload
    assert "baseline" in payload
