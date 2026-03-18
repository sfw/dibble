"""Tests for trend-aware curriculum progression (ORCH-001) and mastery decay
integration into progression decisions (DATA-004)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dibble.models.curriculum import CurriculumResource, KnowledgeComponent
from dibble.models.profile import (
    KnowledgeState,
    LearnerFlowSummary,
    LearnerProfile,
    OrdinaryMasterySummary,
)
from dibble.services.learner_progression_service import LearnerProgressionService


# --- Stubs ---


class StubProfileStore:
    def __init__(self, profile: LearnerProfile) -> None:
        self._profile = profile

    def get(self, student_id):
        return self._profile

    def save(self, profile):
        self._profile = profile


class StubCurriculumStore:
    def __init__(self, resources: list[CurriculumResource]) -> None:
        self._resources = resources

    def list(self):
        return list(self._resources)


class StubKnowledgeComponentStore:
    def __init__(self, components: list[KnowledgeComponent]) -> None:
        self._components = {c.kc_id: c for c in components}

    def list(self):
        return list(self._components.values())

    def get(self, kc_id):
        return self._components.get(kc_id)


class StubOrdinaryMasterySignalService:
    def __init__(self, summaries: dict[str, OrdinaryMasterySummary]) -> None:
        self._summaries = summaries

    def latest_for_student(self, *, student_id, target_kc_ids, target_lo_ids):
        for kc_id in target_kc_ids:
            if kc_id in self._summaries:
                return self._summaries[kc_id]
        return OrdinaryMasterySummary()


class StubLearnerFlowService:
    def __init__(self, flow: LearnerFlowSummary | None = None) -> None:
        self._flow = flow or LearnerFlowSummary(
            status="idle",
            flow_type="idle",
            current_phase="idle",
            progression_action="monitor",
        )

    def build_for_student(self, *, student_id):
        return self._flow


def _kc(kc_id: str, *, prereqs: list[str] | None = None) -> KnowledgeComponent:
    return KnowledgeComponent(
        kc_id=kc_id,
        name=f"KC {kc_id}",
        parent_lo_id="LO-1",
        grade_level="5",
        subject="math",
        prerequisite_kc_ids=prereqs or [],
        difficulty=0.5,
        estimated_time_minutes=8,
        tags=[],
        common_misconceptions=[],
    )


def _resource(resource_id: str, kc_ids: list[str]) -> CurriculumResource:
    return CurriculumResource(
        resource_id=resource_id,
        title=f"Resource {resource_id}",
        knowledge_component_ids=kc_ids,
        learning_objective_ids=["LO-1"],
        grade_level="5",
        subject="math",
        body=f"Curriculum resource body for {resource_id}.",
    )


def _profile(
    kc_mastery: dict[str, float], kc_last_practiced: dict[str, datetime] | None = None
) -> LearnerProfile:
    return LearnerProfile(
        student_id=uuid4(),
        grade_level="5",
        knowledge_state=KnowledgeState(
            kc_mastery=kc_mastery,
            kc_last_practiced=kc_last_practiced or {},
        ),
    )


def _mastery_summary(
    *,
    signal: str,
    trend: str,
    confidence: float = 0.7,
    low_support_success_rate: float = 0.5,
    high_support_dependency_rate: float = 0.0,
) -> OrdinaryMasterySummary:
    return OrdinaryMasterySummary(
        signal=signal,
        source="ordinary_mastery_profile",
        confidence=confidence,
        matched_observation_count=5,
        matched_session_count=3,
        average_observed_mastery=0.72,
        low_support_success_rate=low_support_success_rate,
        high_support_dependency_rate=high_support_dependency_rate,
        mastery_trend=trend,
    )


# --- DATA-004: Mastery decay integration ---


def test_stale_kc_loses_mastered_status_through_decay():
    """A KC that was mastered 90 days ago should decay below the mastery
    threshold and cause the resource to no longer be classified as mastered."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.85},
        kc_last_practiced={"KC-1": now - timedelta(days=90)},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    resource = result.current_resource or (
        result.ready_resources[0] if result.ready_resources else None
    )
    assert resource is not None
    # 0.85 * 0.6 = 0.51, well below 0.8 mastery threshold
    assert resource.state != "mastered"


def test_recent_kc_retains_mastered_status():
    """A KC practiced recently should not be decayed."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.85},
        kc_last_practiced={"KC-1": now - timedelta(days=5)},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    # Find the resource — it should still be mastered
    assert result.mastered_resource_count == 1


def test_no_timestamp_means_no_decay():
    """KCs without a last_practiced timestamp should not be penalised."""
    profile = _profile(kc_mastery={"KC-1": 0.85})
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 1


def test_stale_prerequisite_blocks_dependent_resource():
    """A prerequisite KC that decays below the prerequisite threshold should
    block the dependent resource."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-prereq": 0.70, "KC-target": 0.50},
        kc_last_practiced={
            "KC-prereq": now - timedelta(days=90),  # decays: 0.70 * 0.6 = 0.42
            "KC-target": now - timedelta(days=5),
        },
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore(
            [
                _resource("R1", ["KC-target"]),
            ]
        ),
        knowledge_component_store=StubKnowledgeComponentStore(
            [
                _kc("KC-prereq"),
                _kc("KC-target", prereqs=["KC-prereq"]),
            ]
        ),
        learner_flow_service=StubLearnerFlowService(),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.blocked_resource_count >= 1


# --- ORCH-001: Trend-aware threshold adjustments ---


def test_improving_trend_lowers_mastery_threshold():
    """When the dominant KC trend is improving, the mastery threshold should
    decrease so a borderline-mastered resource can cross the line."""
    now = datetime.now(timezone.utc)
    # 0.78 is below default MASTERY_THRESHOLD of 0.80 but above (0.80 - 0.04) = 0.76
    profile = _profile(
        kc_mastery={"KC-1": 0.78},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(signal="emerging_mastery", trend="improving"),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 1


def test_declining_trend_raises_mastery_threshold():
    """When the dominant KC trend is declining, the mastery threshold should
    increase so a borderline-mastered resource loses mastered status."""
    now = datetime.now(timezone.utc)
    # 0.82 is above default MASTERY_THRESHOLD of 0.80 but below (0.80 + 0.03) = 0.83
    profile = _profile(
        kc_mastery={"KC-1": 0.82},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(signal="emerging_mastery", trend="declining"),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 0


def test_declining_trend_raises_prerequisite_threshold():
    """A declining trend on a prerequisite should make it harder to pass the
    prerequisite check, potentially blocking a dependent resource."""
    now = datetime.now(timezone.utc)
    # 0.67 is above default PREREQUISITE_READY_THRESHOLD of 0.65 but below (0.65 + 0.04) = 0.69
    profile = _profile(
        kc_mastery={"KC-prereq": 0.67, "KC-target": 0.50},
        kc_last_practiced={"KC-prereq": now, "KC-target": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-target"])]),
        knowledge_component_store=StubKnowledgeComponentStore(
            [
                _kc("KC-prereq"),
                _kc("KC-target", prereqs=["KC-prereq"]),
            ]
        ),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-prereq": _mastery_summary(signal="fragile", trend="declining"),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.blocked_resource_count >= 1


def test_no_trend_signal_uses_default_thresholds():
    """Without ordinary mastery signals, default thresholds should apply."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.85},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        # No ordinary_mastery_signal_service
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 1


def test_stable_trend_uses_default_thresholds():
    """A stable trend should not change thresholds."""
    now = datetime.now(timezone.utc)
    # 0.79 is just below default MASTERY_THRESHOLD of 0.80
    profile = _profile(
        kc_mastery={"KC-1": 0.79},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(signal="emerging_mastery", trend="stable"),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    # 0.79 < 0.80 default threshold, so not mastered
    assert result.mastered_resource_count == 0


def test_mixed_trends_resolve_to_dominant():
    """When a resource has KCs with mixed trends and no quality-gate signals,
    the dominant trend should win for threshold adjustment."""
    now = datetime.now(timezone.utc)
    # Two improving, one declining -> improving dominates
    # 0.78 avg is below 0.80 but above 0.76 (improved threshold)
    # All KCs use emerging_mastery so the quality gate does not fire.
    profile = _profile(
        kc_mastery={"KC-A": 0.78, "KC-B": 0.78, "KC-C": 0.78},
        kc_last_practiced={"KC-A": now, "KC-B": now, "KC-C": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore(
            [_resource("R1", ["KC-A", "KC-B", "KC-C"])]
        ),
        knowledge_component_store=StubKnowledgeComponentStore(
            [
                _kc("KC-A"),
                _kc("KC-B"),
                _kc("KC-C"),
            ]
        ),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-A": _mastery_summary(signal="emerging_mastery", trend="improving"),
                "KC-B": _mastery_summary(signal="emerging_mastery", trend="improving"),
                "KC-C": _mastery_summary(signal="emerging_mastery", trend="declining"),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    # min score 0.78 >= lowered prerequisite threshold 0.62, avg 0.78 >= lowered mastery threshold 0.76
    assert result.mastered_resource_count == 1


def test_mixed_trends_with_fragile_kc_blocked_by_quality_gate():
    """When one KC in a multi-KC resource has a fragile signal, the quality
    gate should prevent mastery even when threshold adjustments would allow it."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-A": 0.78, "KC-B": 0.78, "KC-C": 0.78},
        kc_last_practiced={"KC-A": now, "KC-B": now, "KC-C": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore(
            [_resource("R1", ["KC-A", "KC-B", "KC-C"])]
        ),
        knowledge_component_store=StubKnowledgeComponentStore(
            [_kc("KC-A"), _kc("KC-B"), _kc("KC-C")]
        ),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-A": _mastery_summary(signal="emerging_mastery", trend="improving"),
                "KC-B": _mastery_summary(signal="emerging_mastery", trend="improving"),
                "KC-C": _mastery_summary(signal="fragile", trend="declining"),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    # Quality gate fires on KC-C despite trend-adjusted threshold allowing mastery
    assert result.mastered_resource_count == 0
    resource = result.ready_resources[0] if result.ready_resources else None
    assert resource is not None
    assert resource.mastery_quality == "fragile"


# --- Combined: decay + trend ---


def test_decay_and_declining_trend_compound():
    """A stale KC with a declining trend should face both decay AND a raised
    threshold, making it very hard to stay mastered."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.88},
        kc_last_practiced={"KC-1": now - timedelta(days=30)},  # decays ~8%
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(signal="fragile", trend="declining"),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    # 0.88 * ~0.91 (decay) ≈ 0.80, which is below raised threshold of 0.83
    assert result.mastered_resource_count == 0


# --- ADAPT-006: Mastery quality gate ---


def test_support_dependent_prevents_resource_mastery():
    """A resource whose KC has support_dependent signal should not be marked
    mastered even when raw mastery is above threshold."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.90},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(
                    signal="support_dependent",
                    trend="stable",
                    confidence=0.6,
                    high_support_dependency_rate=0.7,
                ),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 0
    resource = result.ready_resources[0] if result.ready_resources else None
    assert resource is not None
    assert resource.state == "ready"
    assert resource.mastery_quality == "support_dependent"
    assert "scaffolded" in (resource.rationale or "")


def test_fragile_prevents_resource_mastery():
    """A resource whose KC has fragile signal should not be marked mastered."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.85},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(
                    signal="fragile",
                    trend="declining",
                    confidence=0.55,
                ),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    # Both threshold raise (declining) and quality gate should prevent mastery
    assert result.mastered_resource_count == 0
    # Find the resource in ready list
    resource = next(
        (r for r in result.ready_resources if r.resource_id == "R1"), None
    )
    assert resource is not None
    assert resource.mastery_quality == "fragile"
    assert "unstable" in (resource.rationale or "")


def test_durable_mastery_allows_resource_mastery():
    """A resource whose KCs all have durable_mastery signal should still be
    marked mastered normally."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.88},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(
                    signal="durable_mastery",
                    trend="stable",
                    confidence=0.85,
                ),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 1


def test_insufficient_signal_does_not_block_mastery():
    """If the mastery signal is 'insufficient' (not enough observations),
    it should not block resource mastery."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.85},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        # No ordinary mastery signal service means insufficient data
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 1


def test_low_confidence_signal_does_not_block_mastery():
    """A support_dependent signal with very low confidence should not
    block mastery — sparse evidence should not override raw scores."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.88},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(
                    signal="support_dependent",
                    trend="stable",
                    confidence=0.25,  # below 0.4 threshold
                    high_support_dependency_rate=0.7,
                ),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 1


def test_multi_kc_resource_blocked_by_worst_signal():
    """If even one KC in a multi-KC resource is support_dependent,
    the resource should not be mastered."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-A": 0.90, "KC-B": 0.85},
        kc_last_practiced={"KC-A": now, "KC-B": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore(
            [_resource("R1", ["KC-A", "KC-B"])]
        ),
        knowledge_component_store=StubKnowledgeComponentStore(
            [_kc("KC-A"), _kc("KC-B")]
        ),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-A": _mastery_summary(
                    signal="durable_mastery", trend="stable", confidence=0.8
                ),
                "KC-B": _mastery_summary(
                    signal="support_dependent",
                    trend="stable",
                    confidence=0.6,
                    high_support_dependency_rate=0.7,
                ),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    assert result.mastered_resource_count == 0
    resource = result.ready_resources[0] if result.ready_resources else None
    assert resource is not None
    assert resource.mastery_quality == "support_dependent"


def test_emerging_mastery_allows_resource_mastery():
    """A resource with emerging_mastery signal should still be allowed
    to be mastered — the quality gate only blocks support_dependent and fragile."""
    now = datetime.now(timezone.utc)
    profile = _profile(
        kc_mastery={"KC-1": 0.82},
        kc_last_practiced={"KC-1": now},
    )
    service = LearnerProgressionService(
        profile_store=StubProfileStore(profile),
        curriculum_store=StubCurriculumStore([_resource("R1", ["KC-1"])]),
        knowledge_component_store=StubKnowledgeComponentStore([_kc("KC-1")]),
        learner_flow_service=StubLearnerFlowService(),
        ordinary_mastery_signal_service=StubOrdinaryMasterySignalService(
            {
                "KC-1": _mastery_summary(
                    signal="emerging_mastery",
                    trend="improving",
                    confidence=0.65,
                ),
            }
        ),
    )
    result = service.build_for_student(student_id=profile.student_id)
    assert result is not None
    # 0.82 > lowered threshold (0.76), and emerging_mastery is not gated
    assert result.mastered_resource_count == 1
