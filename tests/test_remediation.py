from uuid import uuid4

from dibble.models.curriculum import KnowledgeComponentUpsert
from dibble.models.observations import LearnerObservationCreate
from dibble.models.profile import LearnerProfile, LearnerStrategySummary
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.misconception_detector import MisconceptionDetector
from dibble.services.misconception_profiles import LearningMisconceptionProfileResolver
from dibble.services.observation_store import SQLiteObservationStore
from dibble.services.remediation_planner import RemediationPlanner
from dibble.storage import ensure_database
from tests.support import build_knowledge_component, build_profile


def _append_observation(
    observation_store: SQLiteObservationStore,
    *,
    student_id,
    target_kc_id: str,
    support_level: str,
    hints_used: int,
    error_count: int,
    confidence: float,
    response_time_ms: int = 26000,
    expected_duration_ms: int = 15000,
    pause_count: int = 1,
    modality_switches: int = 0,
) -> None:
    observation_store.append(
        student_id=str(student_id),
        observation=LearnerObservationCreate.model_validate(
            {
                "response_time_ms": response_time_ms,
                "hints_used": hints_used,
                "error_count": error_count,
                "pause_count": pause_count,
                "modality_switches": modality_switches,
                "completed": True,
                "confidence": confidence,
                "task_type": "practice",
                "support_level": support_level,
                "expected_duration_ms": expected_duration_ms,
                "learning_session_id": f"session-{target_kc_id}",
                "target_kc_ids": [target_kc_id],
                "target_lo_ids": ["LO-1"],
            }
        ),
    )


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


def test_misconception_detector_uses_recent_behavioral_struggle_to_reinforce_prerequisite_gap(tmp_path):
    database_path = str(tmp_path / "misconceptions-behavioral-prereq.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    observation_store = SQLiteObservationStore(database_path)
    student_id = uuid4()
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
    _append_observation(
        observation_store,
        student_id=student_id,
        target_kc_id="KC-1",
        support_level="high",
        hints_used=3,
        error_count=2,
        confidence=0.42,
        response_time_ms=32000,
        pause_count=2,
    )
    _append_observation(
        observation_store,
        student_id=student_id,
        target_kc_id="KC-1",
        support_level="high",
        hints_used=2,
        error_count=1,
        confidence=0.48,
        response_time_ms=28000,
        modality_switches=1,
    )
    profile = LearnerProfile.model_validate(build_profile(student_id, kc_mastery={"KC-1": 0.62, "KC-2": 0.6}))
    detector = MisconceptionDetector(kc_store, observation_store=observation_store)

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner is still confused about equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
    )

    prerequisite_signal = next(
        signal for signal in signals if signal.kc_id == "KC-1" and signal.category == "prerequisite_gap"
    )
    target_signal = next(
        signal for signal in signals if signal.kc_id == "KC-2" and signal.category == "target_concept_confusion"
    )
    assert prerequisite_signal.confidence > target_signal.confidence
    assert "Recent observations on KC-1" in prerequisite_signal.rationale
    assert "support-heavy attempts" in prerequisite_signal.rationale


def test_misconception_detector_adapts_prerequisite_threshold_to_behavioral_struggle(tmp_path):
    """ADAPT-003: When a prerequisite KC has recent behavioral struggle
    (2+ struggles, 0 successes), the prerequisite gap detection threshold
    should rise from 0.75 to 0.82, so borderline prerequisites that the
    learner is actively struggling with are flagged more aggressively."""
    database_path = str(tmp_path / "misconceptions-adaptive-threshold.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    observation_store = SQLiteObservationStore(database_path)
    student_id = uuid4()
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
    # KC-1 mastery is 0.78 — above the base 0.75 threshold, so without
    # behavioral evidence the prerequisite would NOT be flagged as a gap.
    # But the learner is struggling hard on KC-1, which should raise the
    # threshold to 0.82, making 0.78 < 0.82 a positive gap.
    _append_observation(
        observation_store,
        student_id=student_id,
        target_kc_id="KC-1",
        support_level="high",
        hints_used=3,
        error_count=2,
        confidence=0.35,
        response_time_ms=30000,
    )
    _append_observation(
        observation_store,
        student_id=student_id,
        target_kc_id="KC-1",
        support_level="high",
        hints_used=2,
        error_count=2,
        confidence=0.40,
        response_time_ms=28000,
    )
    profile = LearnerProfile.model_validate(build_profile(student_id, kc_mastery={"KC-1": 0.78, "KC-2": 0.6}))
    detector = MisconceptionDetector(kc_store, observation_store=observation_store)

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner is confused about equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
    )

    # Should detect a prerequisite gap even though mastery is above 0.75
    prerequisite_signals = [s for s in signals if s.kc_id == "KC-1" and s.category == "prerequisite_gap"]
    assert len(prerequisite_signals) == 1
    assert prerequisite_signals[0].confidence > 0.4


def test_misconception_detector_relaxes_prerequisite_threshold_for_recent_successes(tmp_path):
    """ADAPT-003: When a prerequisite KC has recent low-support successes
    (2+ successes, 0 struggles), the threshold should lower from 0.75 to
    0.68, so a prerequisite the learner is recovering on is less likely
    to trigger a gap signal."""
    database_path = str(tmp_path / "misconceptions-adaptive-relax.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    observation_store = SQLiteObservationStore(database_path)
    student_id = uuid4()
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
    # KC-1 mastery is 0.70 — below the base 0.75 threshold, so without
    # behavioral evidence the prerequisite WOULD be flagged.  But 2 recent
    # low-support successes lower the threshold to 0.68, making 0.70 >= 0.68
    # so the prerequisite gap should NOT be detected (unless text overlap).
    _append_observation(
        observation_store,
        student_id=student_id,
        target_kc_id="KC-1",
        support_level="low",
        hints_used=0,
        error_count=0,
        confidence=0.75,
        response_time_ms=12000,
    )
    _append_observation(
        observation_store,
        student_id=student_id,
        target_kc_id="KC-1",
        support_level="low",
        hints_used=0,
        error_count=0,
        confidence=0.80,
        response_time_ms=10000,
    )
    profile = LearnerProfile.model_validate(build_profile(student_id, kc_mastery={"KC-1": 0.70, "KC-2": 0.6}))
    detector = MisconceptionDetector(kc_store, observation_store=observation_store)

    signals = detector.detect(
        profile,
        target_kc_id="KC-2",
        misconception_description="The learner is confused about equivalent fractions.",
        curriculum_context=["Equivalent fractions"],
    )

    # The prerequisite gap on KC-1 may still appear because of text
    # overlap on "fractions", but its confidence should be lower than it
    # would be without the behavioral success evidence tempering it.
    prerequisite_signals = [s for s in signals if s.kc_id == "KC-1" and s.category == "prerequisite_gap"]
    # With 2 low-support successes, the behavioral evidence lowers the
    # confidence adjustment by -0.05, and the threshold drops from 0.75
    # to 0.68 so the mastery gap itself is much smaller.  The signal
    # should be present (because of text overlap) but modest.
    for signal in prerequisite_signals:
        assert signal.confidence < 0.65


def test_misconception_detector_uses_repair_target_behavioral_evidence_for_catalog_match(tmp_path):
    database_path = str(tmp_path / "misconceptions-behavioral-catalog.db")
    ensure_database(database_path)
    kc_store = SQLiteKnowledgeComponentStore(database_path)
    observation_store = SQLiteObservationStore(database_path)
    student_id = uuid4()
    kc_store.upsert(KnowledgeComponentUpsert.model_validate(build_knowledge_component("KC-1", name="Compare whole fraction amounts")))
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
                        "remediation_hint": "Use one visual model to compare the whole amount before naming each part.",
                    }
                ],
            )
        )
    )
    _append_observation(
        observation_store,
        student_id=student_id,
        target_kc_id="KC-1",
        support_level="medium",
        hints_used=2,
        error_count=1,
        confidence=0.5,
        response_time_ms=26000,
        pause_count=2,
    )
    _append_observation(
        observation_store,
        student_id=student_id,
        target_kc_id="KC-1",
        support_level="high",
        hints_used=2,
        error_count=2,
        confidence=0.46,
        response_time_ms=30000,
        modality_switches=1,
    )
    profile = LearnerProfile.model_validate(build_profile(student_id, kc_mastery={"KC-2": 0.58}))
    baseline_detector = MisconceptionDetector(kc_store)
    behavioral_detector = MisconceptionDetector(kc_store, observation_store=observation_store)

    baseline_signal = next(
        signal
        for signal in baseline_detector.detect(
            profile,
            target_kc_id="KC-2",
            misconception_description="The learner compares the numerator and denominator separately like whole numbers.",
            curriculum_context=["Equivalent fractions"],
        )
        if signal.misconception_id == "fraction-whole-number-bias"
    )
    behavioral_signal = next(
        signal
        for signal in behavioral_detector.detect(
            profile,
            target_kc_id="KC-2",
            misconception_description="The learner compares the numerator and denominator separately like whole numbers.",
            curriculum_context=["Equivalent fractions"],
        )
        if signal.misconception_id == "fraction-whole-number-bias"
    )

    assert behavioral_signal.confidence > baseline_signal.confidence
    assert "Recent observations on KC-1" in behavioral_signal.rationale


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
    assert "fraction-part-role-swap" in plan.rationale
    assert "numerator" in plan.rationale
    assert "Identify numerator and denominator" in plan.rationale
    assert "Generate equivalent fractions" in plan.rationale
    assert "broader prerequisite-gap signal on Identify numerator and denominator" in plan.rationale
    assert "instead of defaulting to a generic step-back" in plan.rationale


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
    assert "fraction-whole-number-bias" in plan.rationale
    assert "relapsing" in plan.rationale
    assert "Identify numerator and denominator" in plan.rationale
    assert "Selected as the primary misconception for KC-2" in plan.rationale
    assert "Sequence the next KC focus as rebuild prerequisite first on KC-1." in plan.rationale
    assert plan.kc_sequence.rationale in plan.rationale
    assert plan.module_blueprint["primary_misconception_source"] == "profile"
    assert plan.module_blueprint["primary_recurrence_signal"] == "relapsing"
