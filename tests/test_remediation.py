from uuid import uuid4

from dibble.models.curriculum import KnowledgeComponentUpsert
from dibble.models.profile import LearnerProfile
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.remediation_planner import RemediationPlanner
from dibble.storage import ensure_database
from tests.support import build_knowledge_component, build_profile


def test_misconception_detector_prefers_low_mastery_prerequisites(tmp_path):
    database_path = str(tmp_path / "misconceptions.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1", name="Identify numerator and denominator")))
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
            )
        )
    )
    profile = LearnerProfile.model_validate(build_profile(uuid4(), kc_mastery={"KC-1": 0.2, "KC-2": 0.55}))
    detector = MisconceptionDetector(kc_store)

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner mixes up numerators and denominators while comparing equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
    )

    assert signals[0].kc_id == "KC-1"
    assert signals[0].category == "prerequisite_gap"
    assert signals[0].confidence > 0.7


def test_remediation_planner_uses_misconception_signals_to_order_focus(tmp_path):
    database_path = str(tmp_path / "remediation-plan.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1", name="Identify numerator and denominator")))
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
            )
        )
    )
    profile = LearnerProfile.model_validate(build_profile(uuid4(), kc_mastery={"KC-1": 0.3, "KC-2": 0.6}))
    planner = RemediationPlanner(kc_store, MisconceptionDetector(kc_store))

    plan = planner.plan(
        profile,
        "KC-2",
        misconception_description="The learner confuses numerator language before solving equivalent fractions problems.",
        curriculum_context=["Equivalent fractions"],
    )

    assert plan.focus_kc_ids == ["KC-1", "KC-2"]
    assert plan.prerequisite_kc_ids == ["KC-1"]
    assert plan.misconception_signals[0].kc_id == "KC-1"
    assert "prerequisite knowledge components" in plan.rationale
