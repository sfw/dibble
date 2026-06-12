from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from dibble.models.curriculum import KnowledgeComponentUpsert
from dibble.models.generation import (
    GeneratedBlock,
    GenerationResponse,
    MultipleChoiceInteraction,
    MultipleChoiceOption,
)
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.placement import PlacementError, PlacementService
from dibble.services.placement_session_store import SQLitePlacementSessionStore
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database

CORRECT_OPTION = "A"
WRONG_OPTION = "B"


class StubGenerationEngine:
    """Returns a deterministic verified-style MC item for the requested KC."""

    def __init__(self) -> None:
        self.requested_kc_ids: list[str] = []

    def generate(self, profile, request) -> GenerationResponse:
        kc_id = request.target_kc_ids[0]
        self.requested_kc_ids.append(kc_id)
        block = GeneratedBlock(
            kind="practice_problem",
            title=f"Probe {kc_id}",
            body=f"Question about {kc_id}",
            interaction=MultipleChoiceInteraction(
                prompt=f"Answer the {kc_id} question.",
                options=[
                    MultipleChoiceOption(
                        option_id=CORRECT_OPTION, label="Option A", body="reasoning a"
                    ),
                    MultipleChoiceOption(
                        option_id=WRONG_OPTION, label="Option B", body="reasoning b"
                    ),
                ],
                correct_option_id=CORRECT_OPTION,
            ),
        )
        return GenerationResponse(
            student_id=profile.student_id,
            generation_id=f"gen-{kc_id}-{len(self.requested_kc_ids)}",
            route=_route(),
            grounding=[],
            blocks=[block],
            curriculum_context=[kc_id],
            safety_notes=[],
            validation_issues=[],
        )


def _route():
    from dibble.models.generation import (
        AdaptiveRouteDecision,
        DeliveryMode,
        InterventionType,
    )

    return AdaptiveRouteDecision(
        intervention_type=InterventionType.targeted_practice,
        delivery_mode=DeliveryMode.generated,
        scaffolding_level="medium",
        reasons=["placement probe"],
    )


def _kc(
    kc_id: str,
    *,
    grade: str,
    prerequisites: list[str] | None = None,
    anchor: bool = False,
) -> KnowledgeComponentUpsert:
    return KnowledgeComponentUpsert(
        kc_id=kc_id,
        name=f"KC {kc_id}",
        outcome_id=f"lo-{kc_id}",
        grade_level=grade,
        subject="mathematics",
        prerequisite_kc_ids=prerequisites or [],
        tags=["anchor"] if anchor else [],
    )


GRAPH = [
    # Grade 4 foundations
    _kc("kc-count", grade="4"),
    _kc("kc-add-basic", grade="4", prerequisites=["kc-count"]),
    # Grade 5 anchors
    _kc("kc-add", grade="5", prerequisites=["kc-add-basic"], anchor=True),
    _kc("kc-mult", grade="5", prerequisites=["kc-add-basic"], anchor=True),
    # Grade 5/6 dependents
    _kc("kc-frac", grade="5", prerequisites=["kc-add"]),
    _kc("kc-div", grade="6", prerequisites=["kc-mult"]),
]


@pytest.fixture
def placement(tmp_path):
    db_path = str(tmp_path / "placement.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    kc_store = SQLiteKnowledgeComponentStore(conn)
    for kc in GRAPH:
        kc_store.upsert(kc)
    profile_store = SQLiteProfileStore(conn)
    service = PlacementService(
        knowledge_component_store=kc_store,
        profile_store=profile_store,
        generation_engine=StubGenerationEngine(),
        session_store=SQLitePlacementSessionStore(conn),
    )
    return service, profile_store


def _run_persona(
    service: PlacementService,
    *,
    student_id: UUID,
    mastered: set[str],
    budget: int = 12,
):
    state = service.start(student_id=student_id, grade_band="5", question_budget=budget)
    steps = 0
    while state.status == "active" and state.current_item is not None:
        knows = state.current_item.kc_id in mastered
        state = service.respond(
            student_id=student_id,
            session_id=state.session_id,
            selected_option_id=CORRECT_OPTION if knows else WRONG_OPTION,
        )
        steps += 1
        assert steps <= budget + 1, "placement did not terminate"
    return state


def test_advanced_persona_places_at_dependent_frontier(placement) -> None:
    service, _ = placement
    student_id = uuid4()
    mastered = {"kc-count", "kc-add-basic", "kc-add", "kc-mult", "kc-frac", "kc-div"}

    state = _run_persona(service, student_id=student_id, mastered=mastered)

    assert state.status == "completed"
    report = state.report
    assert report is not None
    assert {kc.kc_id for kc in report.gap_kcs} == set()
    strong_ids = {kc.kc_id for kc in report.strong_kcs}
    assert {"kc-add", "kc-mult", "kc-frac", "kc-div"} <= strong_ids
    assert report.probed_count <= 12


def test_at_level_persona_places_at_grade_dependents(placement) -> None:
    service, _ = placement
    student_id = uuid4()
    mastered = {"kc-count", "kc-add-basic", "kc-add", "kc-mult"}

    state = _run_persona(service, student_id=student_id, mastered=mastered)

    report = state.report
    assert report is not None
    strong_ids = {kc.kc_id for kc in report.strong_kcs}
    gap_ids = {kc.kc_id for kc in report.gap_kcs}
    assert {"kc-add", "kc-mult"} <= strong_ids
    assert gap_ids <= {"kc-frac", "kc-div"}
    starting_ids = {kc.kc_id for kc in report.starting_kcs}
    # Gaps whose prerequisites are met are the right starting points.
    assert starting_ids <= {"kc-frac", "kc-div"}
    assert starting_ids


def test_one_gap_persona_starts_at_the_gap(placement) -> None:
    service, _ = placement
    student_id = uuid4()
    # Knows everything except multiplication (and its dependent).
    mastered = {"kc-count", "kc-add-basic", "kc-add", "kc-frac"}

    state = _run_persona(service, student_id=student_id, mastered=mastered)

    report = state.report
    assert report is not None
    gap_ids = {kc.kc_id for kc in report.gap_kcs}
    assert "kc-mult" in gap_ids
    starting_ids = {kc.kc_id for kc in report.starting_kcs}
    assert "kc-mult" in starting_ids


def test_multi_gap_persona_descends_to_prerequisites(placement) -> None:
    service, _ = placement
    student_id = uuid4()
    # Anchors fail; the grade-4 prerequisite is known.
    mastered = {"kc-count", "kc-add-basic"}

    state = _run_persona(service, student_id=student_id, mastered=mastered)

    report = state.report
    assert report is not None
    gap_ids = {kc.kc_id for kc in report.gap_kcs}
    assert {"kc-add", "kc-mult"} <= gap_ids
    # Their shared prerequisite was probed and demonstrated.
    strong_ids = {kc.kc_id for kc in report.strong_kcs}
    assert "kc-add-basic" in strong_ids
    # Start at the deepest gaps (whose prerequisites are met).
    starting_ids = {kc.kc_id for kc in report.starting_kcs}
    assert starting_ids <= {"kc-add", "kc-mult"}


def test_below_band_persona_descends_to_foundations(placement) -> None:
    service, _ = placement
    student_id = uuid4()

    state = _run_persona(service, student_id=student_id, mastered=set())

    report = state.report
    assert report is not None
    gap_ids = {kc.kc_id for kc in report.gap_kcs}
    # The walk descended below the band to the deepest foundation.
    assert "kc-count" in gap_ids
    starting_ids = {kc.kc_id for kc in report.starting_kcs}
    assert "kc-count" in starting_ids


def test_profile_seeded_with_low_confidence_values(placement) -> None:
    service, profile_store = placement
    student_id = uuid4()
    mastered = {"kc-count", "kc-add-basic", "kc-add", "kc-mult"}

    _run_persona(service, student_id=student_id, mastered=mastered)

    profile = profile_store.get(student_id)
    assert profile is not None
    kc_mastery = profile.knowledge_state.kc_mastery
    assert kc_mastery["kc-add"] == pytest.approx(0.7)
    # Graph-propagated estimate for the unprobed prerequisite.
    assert kc_mastery["kc-add-basic"] >= 0.6
    # Gaps seeded low but not floored, so live evidence can move them.
    for kc_id in ("kc-frac", "kc-div"):
        if kc_id in kc_mastery:
            assert 0.2 <= kc_mastery[kc_id] <= 0.4


def test_question_budget_terminates_session(placement) -> None:
    service, _ = placement
    student_id = uuid4()

    state = _run_persona(service, student_id=student_id, mastered=set(), budget=4)

    assert state.status == "completed"
    assert state.report is not None
    assert state.report.probed_count <= 4


def test_start_without_anchors_raises(tmp_path) -> None:
    db_path = str(tmp_path / "empty.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    service = PlacementService(
        knowledge_component_store=SQLiteKnowledgeComponentStore(conn),
        profile_store=SQLiteProfileStore(conn),
        generation_engine=StubGenerationEngine(),
        session_store=SQLitePlacementSessionStore(conn),
    )

    with pytest.raises(PlacementError):
        service.start(student_id=uuid4(), grade_band="5")


def test_respond_rejects_foreign_session(placement) -> None:
    service, _ = placement
    student_id = uuid4()
    state = service.start(student_id=student_id, grade_band="5")

    with pytest.raises(PlacementError):
        service.respond(
            student_id=uuid4(),
            session_id=state.session_id,
            selected_option_id=CORRECT_OPTION,
        )


def test_placement_endpoints_round_trip(client, student_id) -> None:
    # Seed one anchor KC through the API.
    response = client.put(
        "/api/knowledge-components/kc-anchor",
        json={
            "kc_id": "kc-anchor",
            "name": "Anchor KC",
            "outcome_id": "lo-anchor",
            "grade_level": "5",
            "subject": "mathematics",
            "tags": ["anchor"],
        },
    )
    assert response.status_code == 200

    start = client.post(
        f"/api/learners/{student_id}/placement",
        json={"grade_band": "5", "question_budget": 5},
    )
    assert start.status_code == 200
    payload = start.json()
    assert payload["status"] == "active"
    assert payload["current_item"] is not None
    session_id = payload["session_id"]
    interaction = payload["current_item"]["block"]["interaction"]

    answer = (
        {"selected_option_id": interaction["correct_option_id"]}
        if interaction
        else {"correct": True}
    )
    respond = client.post(
        f"/api/learners/{student_id}/placement/{session_id}/respond",
        json=answer,
    )
    assert respond.status_code == 200

    state = client.get(f"/api/learners/{student_id}/placement/{session_id}")
    assert state.status_code == 200

    report = client.get(f"/api/learners/{student_id}/placement-report")
    assert report.status_code == 200


def test_start_placement_without_corpus_returns_400(client, student_id) -> None:
    response = client.post(
        f"/api/learners/{student_id}/placement",
        json={"grade_band": "5"},
    )

    assert response.status_code == 400
    assert response.headers.get("X-Dibble-Error-Code") == "placement_unavailable"
