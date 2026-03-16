from uuid import uuid4

from dibble.models.curriculum import KnowledgeComponentUpsert
from dibble.models.profile import LearnerProfile, LearnerStrategySummary
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.misconception_profiles import LearningMisconceptionProfileResolver
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


def test_misconception_detector_matches_catalogued_misconception_patterns(tmp_path):
    database_path = str(tmp_path / "misconceptions-catalog.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                name="Generate equivalent fractions",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-whole-number-bias",
                        "label": "Treats numerator and denominator like unrelated whole numbers",
                        "description": "The learner compares fraction parts separately instead of the overall amount.",
                        "trigger_terms": ["numerator", "denominator", "whole number", "separately"],
                        "prerequisite_kc_ids": ["KC-1"],
                        "remediation_hint": "Use one visual model to compare the whole fraction amount before naming each part.",
                    }
                ],
            )
        )
    )
    profile = LearnerProfile.model_validate(build_profile(uuid4(), kc_mastery={"KC-2": 0.42}))
    detector = MisconceptionDetector(kc_store)

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner compares the numerator and denominator separately like whole numbers.",
        curriculum_context=["Equivalent fractions"],
    )

    assert signals[0].category == "known_misconception"
    assert signals[0].source == "catalog"
    assert signals[0].misconception_id == "fraction-whole-number-bias"
    assert signals[0].recommended_kc_ids == ["KC-1"]
    assert signals[0].remediation_hint is not None


def test_misconception_detector_matches_alias_terms_for_catalogued_patterns(tmp_path):
    database_path = str(tmp_path / "misconceptions-alias-catalog.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                name="Generate equivalent fractions",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-part-role-swap",
                        "label": "Swaps numerator and denominator roles",
                        "description": "The learner treats the top and bottom numbers as interchangeable.",
                        "trigger_terms": ["numerator", "denominator", "interchangeable"],
                        "prerequisite_kc_ids": ["KC-1"],
                    }
                ],
            )
        )
    )
    profile = LearnerProfile.model_validate(build_profile(uuid4(), kc_mastery={"KC-2": 0.46}))
    detector = MisconceptionDetector(kc_store)

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner swaps the top and bottom numbers while solving the problem.",
        curriculum_context=["Equivalent fractions"],
    )

    assert signals[0].misconception_id == "fraction-part-role-swap"
    assert set(signals[0].evidence_terms) >= {"top", "bottom", "swap"}


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


def test_misconception_detector_weights_nearby_prerequisites_above_deeper_links(tmp_path):
    database_path = str(tmp_path / "misconceptions-prereq-depth.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1", name="Understand fraction language")))
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                prerequisite_kc_ids=["KC-1"],
                name="Identify denominator roles",
            )
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-3",
                prerequisite_kc_ids=["KC-2"],
                name="Generate equivalent fractions",
            )
        )
    )
    profile = LearnerProfile.model_validate(build_profile(uuid4(), kc_mastery={"KC-1": 0.2, "KC-2": 0.24, "KC-3": 0.55}))
    detector = MisconceptionDetector(kc_store)

    signals = detector.detect(
        profile,
        target_kc_id="KC-3",
        misconception_description="The learner is still confused while generating equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
    )

    prerequisite_signals = [signal for signal in signals if signal.category == "prerequisite_gap"]
    assert [signal.kc_id for signal in prerequisite_signals[:2]] == ["KC-2", "KC-1"]
    assert "depth-1 prerequisite" in prerequisite_signals[0].rationale


def test_remediation_planner_builds_structured_blueprint_for_known_misconceptions(tmp_path):
    database_path = str(tmp_path / "remediation-blueprint.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-1",
                name="Identify numerator and denominator",
            )
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-part-role-swap",
                        "label": "Swaps numerator and denominator roles",
                        "description": "The learner treats the top and bottom numbers as interchangeable.",
                        "trigger_terms": ["numerator", "denominator", "swap"],
                        "prerequisite_kc_ids": ["KC-1"],
                        "remediation_hint": "Anchor each number to what it counts before generating an equivalent fraction.",
                    }
                ],
            )
        )
    )
    profile = LearnerProfile.model_validate(build_profile(uuid4(), kc_mastery={"KC-1": 0.3, "KC-2": 0.52}))
    planner = RemediationPlanner(kc_store, MisconceptionDetector(kc_store))

    plan = planner.plan(
        profile,
        "KC-2",
        misconception_description="The learner swaps numerator and denominator language while generating equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
    )

    catalog_signal = next(
        signal
        for signal in plan.misconception_signals
        if signal.misconception_id == "fraction-part-role-swap"
    )
    assert catalog_signal.source == "catalog"
    assert plan.module_blueprint["trigger"] == "misconception_detected"
    assert plan.module_blueprint["primary_misconception_id"] == "fraction-part-role-swap"
    assert plan.module_blueprint["repair_target_kc_ids"] == ["KC-1"]
    assert plan.module_blueprint["sequence_action"] == "rebuild_prerequisite_first"
    assert [step["phase"] for step in plan.module_blueprint["steps"]] == ["step_back", "repair", "return"]


def test_remediation_planner_can_hold_target_before_prerequisite_step_back(tmp_path):
    database_path = str(tmp_path / "remediation-hold-target.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component("KC-1", name="Identify numerator and denominator")
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
            )
        )
    )
    profile = LearnerProfile.model_validate(build_profile(uuid4(), kc_mastery={"KC-1": 0.35, "KC-2": 0.54}))
    planner = RemediationPlanner(kc_store, MisconceptionDetector(kc_store))

    plan = planner.plan(
        profile,
        "KC-2",
        misconception_description="The learner still needs guided repair on equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
        strategy_summary=LearnerStrategySummary(
            signal="stabilizing",
            source="strategy_profile",
            recovery_focus="guided_practice",
            trajectory_state="plateaued",
            recommended_next_action="introduce_varied_support",
        ),
    )

    assert plan.kc_sequence.action == "hold_target"
    assert plan.focus_kc_ids == ["KC-2"]
    assert plan.module_blueprint["sequence_action"] == "hold_target"
    assert [step["phase"] for step in plan.module_blueprint["steps"]] == ["return"]


def test_remediation_planner_adds_same_lo_bridge_between_repair_and_return(tmp_path):
    database_path = str(tmp_path / "remediation-bridge.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1", name="Identify numerator and denominator")))
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                parent_lo_id="LO-2",
                prerequisite_kc_ids=["KC-1"],
                name="Use visual models for equivalent fractions",
            )
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-3",
                parent_lo_id="LO-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-part-role-swap",
                        "label": "Swaps numerator and denominator roles",
                        "description": "The learner treats the top and bottom numbers as interchangeable.",
                        "trigger_terms": ["numerator", "denominator", "swap"],
                        "prerequisite_kc_ids": ["KC-1"],
                        "remediation_hint": "Anchor each number to what it counts before generating an equivalent fraction.",
                    }
                ],
            )
        )
    )
    profile = LearnerProfile.model_validate(build_profile(uuid4(), kc_mastery={"KC-1": 0.28, "KC-2": 0.5, "KC-3": 0.44}))
    planner = RemediationPlanner(kc_store, MisconceptionDetector(kc_store))

    plan = planner.plan(
        profile,
        "KC-3",
        misconception_description="The learner swaps numerator and denominator language while generating equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
    )

    assert plan.focus_kc_ids == ["KC-1", "KC-2", "KC-3"]
    assert plan.kc_sequence.bridge_kc_ids == ["KC-2"]
    assert plan.module_blueprint["bridge_target_kc_ids"] == ["KC-2"]
    assert [step["phase"] for step in plan.module_blueprint["steps"]] == ["step_back", "repair", "bridge", "return"]
    assert "nearby bridge KC(s) KC-2" in (plan.kc_sequence.rationale or "")


def test_remediation_planner_can_bridge_through_curated_taxonomy_neighbor(tmp_path):
    database_path = str(tmp_path / "remediation-taxonomy-bridge.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-1",
                name="Identify numerator and denominator",
                concept_family="fraction-sense",
                taxonomy_cluster_id="fractions-core",
            )
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                parent_lo_id="LO-3",
                prerequisite_kc_ids=["KC-1"],
                name="Use benchmark fractions to compare amounts",
                concept_family="fraction-equivalence",
                taxonomy_cluster_id="fractions-core",
                nearby_kc_ids=["KC-3"],
            )
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-3",
                parent_lo_id="LO-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
                concept_family="fraction-equivalence",
                taxonomy_cluster_id="fractions-core",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-part-role-swap",
                        "label": "Swaps numerator and denominator roles",
                        "description": "The learner treats the top and bottom numbers as interchangeable.",
                        "trigger_terms": ["numerator", "denominator", "swap"],
                        "prerequisite_kc_ids": ["KC-1"],
                        "remediation_hint": "Anchor each number to what it counts before generating an equivalent fraction.",
                    }
                ],
            )
        )
    )
    profile = LearnerProfile.model_validate(
        build_profile(uuid4(), kc_mastery={"KC-1": 0.26, "KC-2": 0.53, "KC-3": 0.41})
    )
    planner = RemediationPlanner(kc_store, MisconceptionDetector(kc_store))

    plan = planner.plan(
        profile,
        "KC-3",
        misconception_description="The learner swaps numerator and denominator language while generating equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
    )

    assert plan.focus_kc_ids == ["KC-1", "KC-2", "KC-3"]
    assert plan.kc_sequence.bridge_kc_ids == ["KC-2"]
    assert plan.module_blueprint["bridge_target_kc_ids"] == ["KC-2"]
    assert [step["phase"] for step in plan.module_blueprint["steps"]] == ["step_back", "repair", "bridge", "return"]


def test_misconception_detector_uses_profile_signals_to_reinforce_prior_patterns(tmp_path):
    from dibble.services.audit_store import SQLiteAuditStore

    database_path = str(tmp_path / "misconception-profile-detector.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    audit_store = SQLiteAuditStore(database_path)
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                name="Generate equivalent fractions",
                common_misconceptions=[
                    {
                        "misconception_id": "fraction-whole-number-bias",
                        "label": "Treats numerator and denominator like unrelated whole numbers",
                        "description": "The learner compares parts separately.",
                        "trigger_terms": ["numerator", "denominator", "whole number"],
                        "prerequisite_kc_ids": ["KC-1"],
                        "remediation_hint": "Use one visual model to compare the whole amount.",
                    }
                ],
            )
        )
    )
    audit_store.append(
        event_type="learning.misconception.profile",
        status="success",
        student_id=str(uuid4()),
        payload={
            "target_kc_id": "KC-2",
            "kc_id": "KC-2",
            "category": "known_misconception",
            "misconception_id": "fraction-whole-number-bias",
            "matched_signal_count": 2,
            "matched_session_count": 2,
            "average_confidence": 0.8,
            "profile_signal": "persistent",
            "recurrence_signal": "recurring",
            "recommended_kc_ids": ["KC-1"],
            "evidence_terms": ["numerator", "denominator"],
            "remediation_hint": "Use one visual model to compare the whole amount.",
        },
    )
    student_id = uuid4()
    audit_store.append(
        event_type="learning.misconception.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "target_kc_id": "KC-2",
            "kc_id": "KC-2",
            "category": "known_misconception",
            "misconception_id": "fraction-whole-number-bias",
            "matched_signal_count": 2,
            "matched_session_count": 2,
            "average_confidence": 0.8,
            "profile_signal": "persistent",
            "recurrence_signal": "recurring",
            "recommended_kc_ids": ["KC-1"],
            "evidence_terms": ["numerator", "denominator"],
            "remediation_hint": "Use one visual model to compare the whole amount.",
        },
    )
    profile = LearnerProfile.model_validate(build_profile(student_id, kc_mastery={"KC-2": 0.42}))
    detector = MisconceptionDetector(
        kc_store,
        audit_store=audit_store,
        misconception_profile_resolver=LearningMisconceptionProfileResolver(),
    )

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner keeps comparing numerator values before the full fraction.",
        curriculum_context=["Equivalent fractions"],
    )

    assert signals[0].source == "profile"
    assert signals[0].misconception_id == "fraction-whole-number-bias"
    assert signals[0].recurrence_signal == "relapsing"


def test_remediation_planner_prioritizes_recurring_profile_patterns(tmp_path):
    from dibble.services.audit_store import SQLiteAuditStore

    database_path = str(tmp_path / "remediation-recurring-profile.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component("KC-1", name="Identify numerator and denominator")
        )
    )
    kc_store.upsert(
        KnowledgeComponentUpsert.model_validate(
            build_knowledge_component(
                "KC-2",
                prerequisite_kc_ids=["KC-1"],
                name="Generate equivalent fractions",
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
            "average_confidence": 0.84,
            "profile_signal": "persistent",
            "recurrence_signal": "relapsing",
            "recommended_kc_ids": ["KC-1"],
            "evidence_terms": ["numerator", "denominator"],
            "remediation_hint": "Use one visual model to compare the whole amount.",
        },
    )
    profile = LearnerProfile.model_validate(build_profile(student_id, kc_mastery={"KC-1": 0.4, "KC-2": 0.48}))
    planner = RemediationPlanner(
        kc_store,
        MisconceptionDetector(
            kc_store,
            audit_store=audit_store,
            misconception_profile_resolver=LearningMisconceptionProfileResolver(),
        ),
    )

    plan = planner.plan(
        profile,
        "KC-2",
        misconception_description="The learner still compares numerator counts before considering the whole fraction.",
        curriculum_context=["Equivalent fractions"],
    )

    assert plan.misconception_signals[0].source == "profile"
    assert plan.misconception_signals[0].recurrence_signal == "relapsing"
    assert "repeated pattern" in plan.rationale
    assert plan.module_blueprint["primary_misconception_source"] == "profile"
    assert plan.module_blueprint["primary_recurrence_signal"] == "relapsing"
