from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.models.curriculum import KnowledgeComponentUpsert
from dibble.models.generation import MisconceptionSignal
from dibble.models.profile import LearnerProfile
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.misconception_disambiguation import (
    MisconceptionDisambiguationService,
)
from dibble.services.misconception_profiles import LearningMisconceptionProfileResolver
from dibble.services.remediation_planner import RemediationPlanner
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database
from tests.support import build_knowledge_component, build_profile


def test_misconception_detector_marks_one_primary_signal_per_kc(tmp_path):
    database_path = str(tmp_path / "misconception-disambiguation.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    kc_store = SQLiteKnowledgeComponentStore(conn)
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                name="Generate equivalent fractions",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-whole-number-bias",
                        "label": "Treats fraction parts like unrelated whole numbers",
                        "description": "The learner compares numerator and denominator separately instead of the whole amount.",
                        "trigger_terms": [
                            "numerator",
                            "denominator",
                            "whole number",
                            "separately",
                        ],
                        "prerequisite_kc_ids": ["KC-1"],
                    },
                    {
                        "misconception_id": "fraction-part-role-swap",
                        "label": "Swaps numerator and denominator roles",
                        "description": "The learner treats the top and bottom numbers as interchangeable.",
                        "trigger_terms": [
                            "swap",
                            "top",
                            "bottom",
                            "interchangeable",
                            "numerator",
                            "denominator",
                        ],
                        "prerequisite_kc_ids": ["KC-3"],
                    },
                ],
            )
        )
    )
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), kc_mastery={"KC-2": 0.48})
    )
    detector = MisconceptionDetector(kc_store)

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner swaps the top and bottom numbers and treats numerator and denominator as interchangeable.",
        curriculum_context=["Equivalent fractions"],
    )

    catalog_signals = [
        signal for signal in signals if signal.category == "known_misconception"
    ]
    primary_signals = [signal for signal in catalog_signals if signal.primary_for_kc]
    secondary_signal = next(
        signal
        for signal in catalog_signals
        if signal.misconception_id == "fraction-whole-number-bias"
    )
    assert len(primary_signals) == 1
    assert primary_signals[0].misconception_id == "fraction-part-role-swap"
    assert (
        primary_signals[0].disambiguation_score > secondary_signal.disambiguation_score
    )
    assert primary_signals[0].disambiguation_rationale is not None
    assert secondary_signal.disambiguation_rationale is not None


def test_misconception_detector_merges_profile_recurrence_with_catalog_match(tmp_path):
    database_path = str(tmp_path / "misconception-disambiguation-profile.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    kc_store = SQLiteKnowledgeComponentStore(conn)
    audit_store = SQLiteAuditStore(conn)
    student_id = uuid4()
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                name="Generate equivalent fractions",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-whole-number-bias",
                        "label": "Treats fraction parts like unrelated whole numbers",
                        "description": "The learner compares numerator and denominator separately instead of the whole amount.",
                        "trigger_terms": ["numerator", "denominator", "whole number"],
                        "prerequisite_kc_ids": ["KC-1"],
                        "remediation_hint": "Use a visual fraction model before comparing parts.",
                    }
                ],
            )
        )
    )
    audit_store.append(
        event_type="learning.misconception.profile",
        status="success",
        student_id=str(student_id),
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
            "remediation_hint": "Use a visual fraction model before comparing parts.",
        },
    )
    profile = LearnerProfile.model_validate(
        build_profile(student_id, kc_mastery={"KC-2": 0.42})
    )
    detector = MisconceptionDetector(
        kc_store,
        audit_store=audit_store,
        misconception_profile_resolver=LearningMisconceptionProfileResolver(),
    )

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner still compares numerator and denominator counts before reasoning about the full fraction.",
        curriculum_context=["Equivalent fractions"],
    )

    signal = next(
        signal
        for signal in signals
        if signal.misconception_id == "fraction-whole-number-bias"
    )
    assert signal.source == "profile"
    assert signal.primary_for_kc is True
    assert signal.recurrence_signal == "relapsing"
    assert set(signal.evidence_terms) >= {"numerator", "denominator"}
    assert signal.confidence >= 0.81


def test_remediation_planner_uses_primary_misconception_targets_per_kc(tmp_path):
    database_path = str(tmp_path / "misconception-disambiguation-plan.db")
    ensure_database(database_path)
    conn = create_connection(database_path)
    kc_store = SQLiteKnowledgeComponentStore(conn)
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component("KC-1", name="Compare whole-number counts")
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-3", name="Name numerator and denominator roles"
            )
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                name="Generate equivalent fractions",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-whole-number-bias",
                        "label": "Treats fraction parts like unrelated whole numbers",
                        "description": "The learner compares numerator and denominator separately instead of the whole amount.",
                        "trigger_terms": [
                            "numerator",
                            "denominator",
                            "whole number",
                            "separately",
                        ],
                        "prerequisite_kc_ids": ["KC-1"],
                    },
                    {
                        "misconception_id": "fraction-part-role-swap",
                        "label": "Swaps numerator and denominator roles",
                        "description": "The learner treats the top and bottom numbers as interchangeable.",
                        "trigger_terms": [
                            "swap",
                            "top",
                            "bottom",
                            "interchangeable",
                            "numerator",
                            "denominator",
                        ],
                        "prerequisite_kc_ids": ["KC-3"],
                    },
                ],
            )
        )
    )
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            kc_mastery={"KC-1": 0.9, "KC-2": 0.58, "KC-3": 0.92},
            frustration="medium",
            total_load=0.55,
        )
    )
    planner = RemediationPlanner(kc_store, MisconceptionDetector(kc_store))

    plan = planner.plan(
        profile,
        "KC-2",
        misconception_description="The learner keeps swapping the top and bottom numbers when naming the fraction parts.",
        curriculum_context=["Equivalent fractions"],
    )

    primary_signal = next(
        signal for signal in plan.misconception_signals if signal.primary_for_kc
    )
    assert primary_signal.misconception_id == "fraction-part-role-swap"
    assert plan.focus_kc_ids == ["KC-3", "KC-2"]
    assert (
        plan.module_blueprint["primary_misconception_id"] == "fraction-part-role-swap"
    )
    assert plan.module_blueprint["repair_target_kc_ids"] == ["KC-3"]


def test_disambiguation_decays_recurrence_bonus_for_old_signals():
    """A signal with high recurrence but old last_seen_at should score lower
    than the same signal with recent last_seen_at."""
    now = datetime.now(timezone.utc)
    service = MisconceptionDisambiguationService()

    recent_signal = MisconceptionSignal(
        kc_id="KC-2",
        category="known_misconception",
        confidence=0.75,
        rationale="test",
        source="catalog",
        misconception_id="misconception-a",
        evidence_terms=["term1"],
        recurrence_count=4,
        recurrence_session_count=3,
        last_seen_at=now - timedelta(days=2),
    )
    old_signal = MisconceptionSignal(
        kc_id="KC-2",
        category="known_misconception",
        confidence=0.75,
        rationale="test",
        source="catalog",
        misconception_id="misconception-b",
        evidence_terms=["term2"],
        recurrence_count=4,
        recurrence_session_count=3,
        last_seen_at=now - timedelta(days=90),
    )

    term_counts = {"term1": 1, "term2": 1}
    recent_score = service._score(recent_signal, term_counts=term_counts)
    old_score = service._score(old_signal, term_counts=term_counts)

    # The old signal's recurrence bonus should be attenuated by the decay factor
    assert recent_score > old_score
    # Both should still be positive
    assert old_score > 0
