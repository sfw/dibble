from uuid import uuid4

from dibble.models.session_adaptation import WithinSessionControllerState
from dibble.services.within_session_controller_store import (
    SQLiteWithinSessionControllerStore,
)
from dibble.storage import ensure_database


def test_within_session_controller_store_round_trips_state(tmp_path):
    database_path = str(tmp_path / "within-session-controller-store.db")
    ensure_database(database_path)
    store = SQLiteWithinSessionControllerStore(database_path)
    session = WithinSessionControllerState(
        learning_session_id="session-1",
        student_id=uuid4(),
        target_kc_ids=["KC-1"],
        signal="negative",
        confidence=0.82,
        support_bias=-1,
        sequence_action="hold_target",
        primary_kc_id="KC-1",
        phase="repair",
        recovery_intent="increase_support",
        support_step_budget=2,
        support_steps_remaining=1,
        stuck_loop_risk="moderate",
        arc_action="model_repair",
        observation_count=2,
        generation_count=1,
        negative_streak=2,
        rationale="Controller is staying on the repair target.",
    )

    store.upsert(session)
    loaded = store.get("session-1")

    assert loaded is not None
    assert loaded.learning_session_id == "session-1"
    assert loaded.phase == "repair"
    assert loaded.generation_count == 1
    assert loaded.support_steps_remaining == 1
    assert loaded.stuck_loop_risk == "moderate"
    assert loaded.negative_streak == 2
