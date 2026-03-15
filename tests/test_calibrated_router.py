from __future__ import annotations

from uuid import uuid4

from dibble.models.generation import AdaptiveRouteDecision, DeliveryMode, GenerationRequest, InterventionType
from dibble.models.profile import LearnerProfile
from dibble.services.adaptive_router import AdaptiveRouter
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.calibrated_router import CalibratedRouter
from dibble.services.router_calibration_signals import RouterCalibrationSignalService
from dibble.storage import ensure_database
from tests.support import build_profile


class AlwaysReteachRouter:
    def route(self, profile, request):
        return AdaptiveRouteDecision(
            intervention_type=InterventionType.reteach,
            delivery_mode=DeliveryMode.generated,
            scaffolding_level="medium",
            reasons=["Base router chose reteach."],
        )


def test_calibrated_router_holds_back_stretch_after_negative_run_signal(tmp_path):
    database_path = str(tmp_path / "calibrated-router-negative.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.95},
            engagement="high",
            confidence_calibration=0.82,
            help_seeking="low",
        )
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="explanation")
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(profile.student_id),
        payload={
            "intent": "explanation",
            "generation_id": "gen-1",
            "target_kc_ids": ["KC-1"],
            "content_type": "micro_explanation",
            "prompt_template_name": "micro_explanation.baseline",
            "prompt_template_variant": "baseline",
            "quality_score": 0.86,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(profile.student_id),
        payload={
            "generation_id": "gen-1",
            "observed_content_type": "micro_explanation",
            "task_type": "explanation",
            "target_kc_ids": ["KC-1"],
            "engagement": "low",
            "frustration": "high",
            "total_load": 0.86,
            "confidence_calibration": 0.26,
            "help_seeking": "high",
        },
    )

    router = CalibratedRouter(
        base_router=AdaptiveRouter(),
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
    )

    decision = router.route(profile, request)

    assert decision.intervention_type == InterventionType.reteach
    assert decision.delivery_mode == DeliveryMode.generated
    assert decision.scaffolding_level == "medium"
    assert decision.calibration is not None
    assert decision.calibration.signal == "negative"


def test_calibrated_router_relaxes_scaffolding_after_positive_run_signal(tmp_path):
    database_path = str(tmp_path / "calibrated-router-positive.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    profile = LearnerProfile.model_validate(
        build_profile(
            uuid4(),
            frustration="low",
            total_load=0.2,
            kc_mastery={"KC-1": 0.88},
            engagement="high",
            confidence_calibration=0.35,
            help_seeking="high",
        )
    )
    request = GenerationRequest(student_id=profile.student_id, target_kc_ids=["KC-1"], intent="explanation")
    audit_store.append(
        event_type="content.generate",
        status="success",
        student_id=str(profile.student_id),
        payload={
            "intent": "explanation",
            "generation_id": "gen-2",
            "target_kc_ids": ["KC-1"],
            "content_type": "worked_example",
            "prompt_template_name": "worked_example.guided_reflection",
            "prompt_template_variant": "guided_reflection",
            "quality_score": 0.78,
            "validation_passed": True,
            "grounding_count": 1,
        },
    )
    audit_store.append(
        event_type="learner.observe",
        status="success",
        student_id=str(profile.student_id),
        payload={
            "generation_id": "gen-2",
            "observed_content_type": "worked_example",
            "task_type": "worked_example",
            "target_kc_ids": ["KC-1"],
            "engagement": "high",
            "frustration": "low",
            "total_load": 0.22,
            "confidence_calibration": 0.84,
            "help_seeking": "low",
        },
    )

    router = CalibratedRouter(
        base_router=AlwaysReteachRouter(),
        calibration_signal_service=RouterCalibrationSignalService(audit_store=audit_store),
    )

    decision = router.route(profile, request)

    assert decision.intervention_type == InterventionType.reteach
    assert decision.scaffolding_level == "low"
    assert decision.calibration is not None
    assert decision.calibration.signal == "positive"
