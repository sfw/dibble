from __future__ import annotations

from uuid import uuid4

from dibble.models.curriculum import KnowledgeComponent
from dibble.models.generation import GenerationRequest
from dibble.models.observations import LearnerObservation
from dibble.models.profile import LearnerProfile
from dibble.models.remediation import RemediationWorkflowSession
from dibble.services.knowledge_state_migration import KnowledgeStateMigrator
from dibble.services.observation_profile_update import ObservationProfileUpdater
from dibble.services.ordinary_mastery_profiles import OrdinaryMasterySignalService
from dibble.services.audit_store import SQLiteAuditStore
from dibble.storage import ensure_database
from tests.support import build_profile


class StubKnowledgeComponentStore:
    def __init__(self) -> None:
        self.components = {
            "KC-1": KnowledgeComponent(
                kc_id="KC-1",
                name="KC-1",
                parent_lo_id="LO-1",
                grade_level="5",
                subject="math",
                prerequisite_kc_ids=[],
                difficulty=0.4,
                estimated_time_minutes=8,
                tags=[],
                common_misconceptions=[],
            ),
            "KC-2": KnowledgeComponent(
                kc_id="KC-2",
                name="KC-2",
                parent_lo_id="LO-1",
                grade_level="5",
                subject="math",
                prerequisite_kc_ids=["KC-1"],
                difficulty=0.5,
                estimated_time_minutes=8,
                tags=[],
                common_misconceptions=[],
            ),
        }

    def list(self):
        return list(self.components.values())

    def get(self, kc_id):
        return self.components.get(kc_id)

    def list_prerequisites(self, kc_id):
        if kc_id == "KC-2":
            return [self.components["KC-1"]]
        return []


def test_observation_profile_updater_updates_linked_practice_mastery():
    student_id = uuid4()
    profile = build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.3, "KC-2": 0.25})
    updater = ObservationProfileUpdater(
        knowledge_state_migrator=KnowledgeStateMigrator(knowledge_component_store=StubKnowledgeComponentStore())
    )

    result = updater.apply(
        profile=LearnerProfile.model_validate(profile),
        observation=LearnerObservation.model_validate(
            {
                "observation_id": "obs-1",
                "student_id": str(student_id),
                "response_time_ms": 14000,
                "hints_used": 0,
                "error_count": 0,
                "pause_count": 0,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.76,
                "task_type": "practice",
                "support_level": "low",
                "expected_duration_ms": 18000,
                "learning_session_id": "session-practice",
                "generation_id": "gen-practice",
                "observed_content_type": "practice_problem",
                "target_kc_ids": ["KC-2"],
                "target_lo_ids": ["LO-1"],
            }
        ),
    )

    assert result.applied is True
    assert result.inferred_mastery is not None
    assert result.kc_mastery_updates["KC-2"] > 0.25
    assert result.propagated_kc_mastery_updates["KC-1"] >= 0.3
    assert result.profile.knowledge_state.lo_mastery["LO-1"] >= 0.3


def test_observation_profile_updater_uses_recent_linked_evidence_bundle():
    student_id = uuid4()
    profile = build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-2": 0.25})
    updater = ObservationProfileUpdater()
    recent_observations = [
        LearnerObservation.model_validate(
            {
                "observation_id": "obs-2",
                "student_id": str(student_id),
                "response_time_ms": 15000,
                "hints_used": 0,
                "error_count": 0,
                "pause_count": 0,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.74,
                "task_type": "practice",
                "support_level": "low",
                "expected_duration_ms": 18000,
                "learning_session_id": "session-practice",
                "generation_id": "gen-practice",
                "observed_content_type": "practice_problem",
                "target_kc_ids": ["KC-2"],
            }
        ),
        LearnerObservation.model_validate(
            {
                "observation_id": "obs-1",
                "student_id": str(student_id),
                "response_time_ms": 14000,
                "hints_used": 0,
                "error_count": 0,
                "pause_count": 0,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.76,
                "task_type": "practice",
                "support_level": "low",
                "expected_duration_ms": 18000,
                "learning_session_id": "session-practice",
                "generation_id": "gen-practice",
                "observed_content_type": "practice_problem",
                "target_kc_ids": ["KC-2"],
            }
        ),
    ]

    result = updater.apply(
        profile=LearnerProfile.model_validate(profile),
        observation=recent_observations[0],
        recent_observations=recent_observations,
    )

    assert result.applied is True
    assert result.matched_observation_count == 2
    assert result.average_recent_observed_mastery is not None
    assert result.average_recent_observed_mastery >= result.inferred_mastery - 0.05
    assert result.evidence_confidence >= 0.5
    assert "across 2 recent linked observations" in (result.rationale or "")
    assert result.linkage_source == "generation_linked"


def test_observation_profile_updater_updates_strong_target_scoped_practice_without_links():
    student_id = uuid4()
    profile = build_profile(student_id, frustration="low", total_load=0.2, kc_mastery={"KC-1": 0.3, "KC-2": 0.25})
    updater = ObservationProfileUpdater(
        knowledge_state_migrator=KnowledgeStateMigrator(knowledge_component_store=StubKnowledgeComponentStore())
    )

    result = updater.apply(
        profile=LearnerProfile.model_validate(profile),
        observation=LearnerObservation.model_validate(
            {
                "observation_id": "obs-2",
                "student_id": str(student_id),
                "response_time_ms": 15000,
                "hints_used": 1,
                "error_count": 0,
                "pause_count": 0,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.72,
                "task_type": "practice",
                "support_level": "low",
                "expected_duration_ms": 18000,
                "observed_content_type": "practice_problem",
                "target_kc_ids": ["KC-2"],
                "target_lo_ids": ["LO-1"],
            }
        ),
    )

    assert result.applied is True
    assert result.linkage_source == "target_scoped_strong_observation"
    assert result.kc_mastery_updates["KC-2"] > 0.25


def test_observation_profile_updater_uses_durable_mastery_signal_for_low_support_writeback(tmp_path):
    database_path = str(tmp_path / "observation-ordinary-mastery.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    audit_store.append(
        event_type="learning.ordinary_mastery.profile",
        status="success",
        student_id=str(student_id),
        payload={
            "target_kc_ids": ["KC-2"],
            "target_lo_ids": ["LO-1"],
            "profile_signal": "durable_mastery",
            "profile_confidence": 0.84,
            "matched_observation_count": 5,
            "matched_session_count": 3,
            "average_observed_mastery": 0.8,
            "low_support_success_rate": 0.8,
            "high_support_dependency_rate": 0.0,
            "ordinary_mastery_profile_rationale": "Practice evidence stayed strong.",
        },
    )
    updater = ObservationProfileUpdater(
        ordinary_mastery_signal_service=OrdinaryMasterySignalService(audit_store=audit_store)
    )
    profile = LearnerProfile.model_validate(build_profile(student_id, kc_mastery={"KC-2": 0.25}, frustration="low"))

    result = updater.apply(
        profile=profile,
        observation=LearnerObservation.model_validate(
            {
                "observation_id": "obs-durable-1",
                "student_id": str(student_id),
                "response_time_ms": 13000,
                "hints_used": 0,
                "error_count": 0,
                "pause_count": 0,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.82,
                "task_type": "practice",
                "support_level": "low",
                "expected_duration_ms": 18000,
                "observed_content_type": "practice_problem",
                "target_kc_ids": ["KC-2"],
                "target_lo_ids": ["LO-1"],
            }
        ),
    )

    assert result.applied is True
    assert result.durable_mastery_signal == "durable_mastery"
    assert result.durable_mastery_confidence == 0.84
    assert result.durable_mastery_low_support_success_rate == 0.8
    assert result.kc_mastery_updates["KC-2"] > 0.42


def test_observation_profile_updater_holds_remediation_return_when_recent_evidence_is_weak():
    updater = ObservationProfileUpdater()
    session = RemediationWorkflowSession.model_validate(
        {
            "session_id": "rem-session-1",
            "student_id": str(uuid4()),
            "target_kc_id": "KC-2",
            "misconception_description": "Needs repair.",
            "rationale": "Repair before return.",
            "steps": [
                {
                    "phase": "step_back",
                    "title": "Step back",
                    "target_kc_ids": ["KC-1"],
                    "support_level": "high",
                    "objective": "Reconnect prerequisite.",
                    "guidance": "Use one example.",
                    "recommended_content_type": "remedial_micro_module",
                    "status": "completed",
                    "generated_content_id": "gen-step-back",
                },
                {
                    "phase": "repair",
                    "title": "Repair",
                    "target_kc_ids": ["KC-1"],
                    "support_level": "medium",
                    "objective": "Repair the misconception.",
                    "guidance": "Contrast correct reasoning.",
                    "recommended_content_type": "remedial_micro_module",
                    "status": "completed",
                    "generated_content_id": "gen-repair",
                },
                {
                    "phase": "return",
                    "title": "Return",
                    "target_kc_ids": ["KC-2"],
                    "support_level": "low",
                    "objective": "Return to the target.",
                    "guidance": "Use one transfer check.",
                    "recommended_content_type": "practice_problem",
                    "status": "active",
                },
            ],
            "current_step_index": 2,
            "completed_generation_ids": ["gen-step-back", "gen-repair"],
        }
    )
    observations = [
        LearnerObservation.model_validate(
            {
                "observation_id": "obs-remediate-1",
                "student_id": str(session.student_id),
                "response_time_ms": 33000,
                "hints_used": 4,
                "error_count": 3,
                "pause_count": 3,
                "modality_switches": 1,
                "completed": False,
                "confidence": 0.18,
                "task_type": "remediation",
                "support_level": "high",
                "expected_duration_ms": 18000,
                "learning_session_id": session.session_id,
                "generation_id": "gen-repair",
                "observed_content_type": "remedial_micro_module",
                "target_kc_ids": ["KC-1"],
                "target_lo_ids": ["LO-1"],
            }
        )
    ]

    decision = updater.evaluate_remediation_progress(session=session, observations=observations)

    assert decision.decision == "hold_repair_target"
    assert decision.hold_step_index == 1
    assert decision.matched_observation_count == 1
    assert decision.average_observed_mastery is not None
    assert decision.average_observed_mastery < 0.58
    assert decision.evidence_confidence > 0.0
    assert decision.low_support_success_count == 0


def test_observation_profile_updater_holds_bridge_before_final_target_return_without_low_support_success():
    updater = ObservationProfileUpdater()
    session = RemediationWorkflowSession.model_validate(
        {
            "session_id": "rem-session-bridge-1",
            "student_id": str(uuid4()),
            "target_kc_id": "KC-3",
            "misconception_description": "Needs bridge before return.",
            "rationale": "Repair and bridge before the final return.",
            "steps": [
                {
                    "phase": "step_back",
                    "title": "Reconnect prerequisite",
                    "target_kc_ids": ["KC-1"],
                    "support_level": "high",
                    "objective": "Reconnect prerequisite.",
                    "guidance": "Use one simple example.",
                    "recommended_content_type": "remedial_micro_module",
                    "status": "completed",
                    "generated_content_id": "gen-step-back",
                },
                {
                    "phase": "repair",
                    "title": "Repair target",
                    "target_kc_ids": ["KC-1"],
                    "support_level": "medium",
                    "objective": "Repair the misconception.",
                    "guidance": "Contrast the misconception.",
                    "recommended_content_type": "remedial_micro_module",
                    "status": "completed",
                    "generated_content_id": "gen-repair",
                },
                {
                    "phase": "bridge",
                    "title": "Bridge to nearby KC",
                    "target_kc_ids": ["KC-2"],
                    "support_level": "medium",
                    "objective": "Bridge toward the target.",
                    "guidance": "Fade support but stay guided.",
                    "recommended_content_type": "remedial_micro_module",
                    "status": "completed",
                    "generated_content_id": "gen-bridge",
                },
                {
                    "phase": "return",
                    "title": "Return to target",
                    "target_kc_ids": ["KC-3"],
                    "support_level": "low",
                    "objective": "Return to the target.",
                    "guidance": "End with a transfer check.",
                    "recommended_content_type": "practice_problem",
                    "status": "active",
                },
            ],
            "current_step_index": 3,
        }
    )
    observations = [
        LearnerObservation.model_validate(
            {
                "observation_id": "obs-bridge-1",
                "student_id": str(session.student_id),
                "response_time_ms": 18000,
                "hints_used": 0,
                "error_count": 0,
                "pause_count": 0,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.76,
                "task_type": "remediation",
                "support_level": "medium",
                "expected_duration_ms": 18000,
                "learning_session_id": session.session_id,
                "generation_id": "gen-bridge",
                "observed_content_type": "remedial_micro_module",
                "target_kc_ids": ["KC-2"],
                "target_lo_ids": ["LO-1"],
            }
        )
    ]

    decision = updater.evaluate_remediation_progress(session=session, observations=observations)

    assert decision.decision == "hold_bridge_target"
    assert decision.hold_step_index == 2
    assert decision.average_observed_mastery is not None
    assert decision.average_observed_mastery >= 0.62
    assert decision.low_support_success_count == 0


def test_observation_profile_updater_marks_transfer_ready_from_strong_same_session_evidence():
    updater = ObservationProfileUpdater()
    student_id = uuid4()
    request = GenerationRequest(
        student_id=student_id,
        learning_session_id="session-transfer",
        target_kc_ids=["KC-2"],
        target_lo_ids=["LO-1"],
        intent="practice",
        requested_content_type="practice_problem",
    )
    observations = [
        LearnerObservation.model_validate(
            {
                "observation_id": "obs-transfer-2",
                "student_id": str(student_id),
                "response_time_ms": 15000,
                "hints_used": 0,
                "error_count": 0,
                "pause_count": 0,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.78,
                "task_type": "practice",
                "support_level": "low",
                "expected_duration_ms": 18000,
                "learning_session_id": "session-transfer",
                "target_kc_ids": ["KC-2"],
                "target_lo_ids": ["LO-1"],
            }
        ),
        LearnerObservation.model_validate(
            {
                "observation_id": "obs-transfer-1",
                "student_id": str(student_id),
                "response_time_ms": 16000,
                "hints_used": 1,
                "error_count": 0,
                "pause_count": 0,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.74,
                "task_type": "practice",
                "support_level": "low",
                "expected_duration_ms": 18000,
                "learning_session_id": "session-transfer",
                "target_kc_ids": ["KC-2"],
                "target_lo_ids": ["LO-1"],
            }
        ),
    ]
    assessment_payloads = [
        {
            "learning_session_id": "session-transfer",
            "target_kc_ids": ["KC-2"],
            "target_lo_ids": ["LO-1"],
            "evidence_strength": "demonstrated",
            "evidence_score": 0.84,
            "inferred_mastery": 0.79,
        }
    ]

    decision = updater.evaluate_progression_evidence(
        request=request,
        observations=observations,
        assessment_payloads=assessment_payloads,
    )

    assert decision.decision == "attempt_transfer"
    assert decision.matched_observation_count == 2
    assert decision.matched_assessment_count == 1
    assert decision.confidence >= 0.7


def test_observation_profile_updater_holds_target_when_success_is_still_support_heavy():
    updater = ObservationProfileUpdater()
    student_id = uuid4()
    request = GenerationRequest(
        student_id=student_id,
        learning_session_id="session-hold",
        target_kc_ids=["KC-2"],
        intent="practice",
        requested_content_type="practice_problem",
    )
    observations = [
        LearnerObservation.model_validate(
            {
                "observation_id": "obs-hold-2",
                "student_id": str(student_id),
                "response_time_ms": 20000,
                "hints_used": 3,
                "error_count": 0,
                "pause_count": 1,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.64,
                "task_type": "practice",
                "support_level": "high",
                "expected_duration_ms": 18000,
                "learning_session_id": "session-hold",
                "target_kc_ids": ["KC-2"],
            }
        ),
        LearnerObservation.model_validate(
            {
                "observation_id": "obs-hold-1",
                "student_id": str(student_id),
                "response_time_ms": 22000,
                "hints_used": 2,
                "error_count": 1,
                "pause_count": 1,
                "modality_switches": 0,
                "completed": True,
                "confidence": 0.6,
                "task_type": "practice",
                "support_level": "high",
                "expected_duration_ms": 18000,
                "learning_session_id": "session-hold",
                "target_kc_ids": ["KC-2"],
            }
        ),
    ]

    decision = updater.evaluate_progression_evidence(
        request=request,
        observations=observations,
        assessment_payloads=[],
    )

    assert decision.decision == "hold_target"
    assert decision.matched_observation_count == 2
    assert decision.average_observed_mastery is not None
    assert decision.confidence >= 0.5
