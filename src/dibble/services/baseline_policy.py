"""Shadow baseline policy for counterfactual decision logging.

Implements naive decisions at the points where the production adaptive stack
makes a judgment call, and records production-vs-baseline agreement as
``learning.baseline.decision`` audit events. Log-only: nothing here may alter
production behavior. Post-pilot analysis joins divergences against
``progression.outcome`` verdicts to score whether the calibration machinery
beats the naive policy.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from dibble.models.baseline import (
    BaselineAgreementSummary,
    BaselineDecisionPointSummary,
    BaselineDivergence,
)
from dibble.models.generation import AdaptiveRouteDecision, GenerationRequest
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import RouterPlugin
from dibble.services.progression_ownership import (
    ProgressionOwnershipDecision,
    ProgressionOwnershipService,
)
from dibble.services.protocols import (
    AuditStore,
    KnowledgeComponentStore,
    ProfileStore,
)

BASELINE_DECISION_EVENT_TYPE = "learning.baseline.decision"
_UNKNOWN_MASTERY = 0.5


@dataclass(slots=True)
class BaselinePolicyService:
    """Naive counterfactual decisions plus agreement logging and querying."""

    audit_store: AuditStore
    knowledge_component_store: KnowledgeComponentStore | None = None
    profile_store: ProfileStore | None = None
    mastery_threshold: float = 0.8
    reteach_threshold: float = 0.5

    # -- routing -----------------------------------------------------------

    def baseline_route(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> dict[str, object]:
        """Static-mapping router: mastery below 0.5 reteaches at high support,
        below the gate practices at medium support, at/above the gate advances
        at low support. No trend, quality, or signal adjustments."""
        mastery = self._average_target_mastery(
            profile=profile, target_kc_ids=request.target_kc_ids
        )
        if mastery < self.reteach_threshold:
            intervention, scaffolding = "reteach", "high"
        elif mastery < self.mastery_threshold:
            intervention, scaffolding = "targeted_practice", "medium"
        else:
            intervention, scaffolding = "stretch", "low"
        return {
            "intervention_type": intervention,
            "scaffolding_level": scaffolding,
            "delivery_mode": "generated",
            "average_target_mastery": round(mastery, 4),
        }

    def record_route_decision(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        production: AdaptiveRouteDecision,
    ) -> None:
        baseline = self.baseline_route(profile, request)
        production_payload: dict[str, object] = {
            "intervention_type": production.intervention_type.value,
            "scaffolding_level": production.scaffolding_level,
            "delivery_mode": production.delivery_mode.value,
        }
        agreed = (
            production_payload["intervention_type"] == baseline["intervention_type"]
            and production_payload["scaffolding_level"] == baseline["scaffolding_level"]
        )
        self._emit(
            decision_point="router.route",
            student_id=str(profile.student_id),
            production_decision=production_payload,
            baseline_decision=baseline,
            agreed=agreed,
            inputs={
                "student_id": str(profile.student_id),
                "target_kc_ids": list(request.target_kc_ids),
                "intent": request.intent.value,
                "kc_mastery": self._mastery_snapshot(
                    profile=profile, kc_ids=request.target_kc_ids
                ),
            },
        )

    # -- progression ---------------------------------------------------------

    def baseline_progression(
        self, *, student_id: UUID, request: GenerationRequest
    ) -> dict[str, object]:
        """Simple prerequisite-met check at a fixed threshold: any prerequisite
        below the gate steps back to it; otherwise stay on the requested
        target. No holds, bridges, or transfer logic."""
        profile = (
            self.profile_store.get(student_id)
            if self.profile_store is not None
            else None
        )
        kc_mastery = profile.knowledge_state.kc_mastery if profile is not None else {}
        unmet: list[str] = []
        for kc_id in request.target_kc_ids:
            component = (
                self.knowledge_component_store.get(kc_id)
                if self.knowledge_component_store is not None
                else None
            )
            if component is None:
                continue
            for prerequisite_kc_id in component.prerequisite_kc_ids:
                mastery = kc_mastery.get(prerequisite_kc_id, _UNKNOWN_MASTERY)
                if mastery < self.mastery_threshold and prerequisite_kc_id not in unmet:
                    unmet.append(prerequisite_kc_id)
        if unmet:
            return {
                "action": "rebuild_prerequisite_first",
                "applied_target_kc_ids": unmet[:1],
                "unmet_prerequisite_kc_ids": unmet,
            }
        return {
            "action": "stay_on_requested_target",
            "applied_target_kc_ids": list(request.target_kc_ids),
            "unmet_prerequisite_kc_ids": [],
        }

    def record_progression_decision(
        self,
        *,
        student_id: UUID,
        request: GenerationRequest,
        production: ProgressionOwnershipDecision,
    ) -> None:
        if not request.target_kc_ids:
            return
        baseline = self.baseline_progression(student_id=student_id, request=request)
        production_payload: dict[str, object] = {
            "action": production.action,
            "applied_target_kc_ids": list(production.applied_target_kc_ids),
            "target_stage": production.target_stage,
            "mastery_gate_applied": production.mastery_gate_applied,
        }
        agreed = production_payload["action"] == baseline["action"] and list(
            production.applied_target_kc_ids
        ) == list(baseline["applied_target_kc_ids"])
        profile = (
            self.profile_store.get(student_id)
            if self.profile_store is not None
            else None
        )
        self._emit(
            decision_point="progression.resolve",
            student_id=str(student_id),
            production_decision=production_payload,
            baseline_decision=baseline,
            agreed=agreed,
            inputs={
                "student_id": str(student_id),
                "target_kc_ids": list(request.target_kc_ids),
                "intent": request.intent.value,
                "kc_mastery": self._mastery_snapshot(
                    profile=profile,
                    kc_ids=[
                        *request.target_kc_ids,
                        *baseline.get("unmet_prerequisite_kc_ids", []),
                    ],
                ),
            },
        )

    # -- querying --------------------------------------------------------------

    def agreement_summary(
        self,
        *,
        student_id: str | None = None,
        limit: int = 2000,
        max_divergences: int = 50,
    ) -> BaselineAgreementSummary:
        events = [
            event
            for event in self.audit_store.list(limit=limit)
            if event.event_type == BASELINE_DECISION_EVENT_TYPE
            and (
                student_id is None
                or (
                    event.student_id is not None and str(event.student_id) == student_id
                )
            )
        ]
        by_point: dict[str, BaselineDecisionPointSummary] = {}
        divergences: list[BaselineDivergence] = []
        agreed_total = 0
        for event in events:
            payload = event.payload
            decision_point = str(payload.get("decision_point", "unknown"))
            summary = by_point.setdefault(
                decision_point,
                BaselineDecisionPointSummary(decision_point=decision_point),
            )
            summary.total_decisions += 1
            if event.status == "agreed":
                summary.agreed_decisions += 1
                agreed_total += 1
            elif len(divergences) < max_divergences:
                divergences.append(
                    BaselineDivergence(
                        decision_point=decision_point,
                        student_id=(
                            str(event.student_id)
                            if event.student_id is not None
                            else None
                        ),
                        production_decision=dict(
                            payload.get("production_decision", {})  # type: ignore[arg-type]
                        ),
                        baseline_decision=dict(
                            payload.get("baseline_decision", {})  # type: ignore[arg-type]
                        ),
                        inputs_digest=(
                            str(payload.get("inputs_digest"))
                            if payload.get("inputs_digest") is not None
                            else None
                        ),
                        created_at=event.created_at,
                    )
                )
        for summary in by_point.values():
            if summary.total_decisions > 0:
                summary.agreement_rate = round(
                    summary.agreed_decisions / summary.total_decisions, 4
                )
        total = len(events)
        return BaselineAgreementSummary(
            total_decisions=total,
            agreed_decisions=agreed_total,
            agreement_rate=round(agreed_total / total, 4) if total else None,
            decision_points=sorted(
                by_point.values(), key=lambda item: item.decision_point
            ),
            divergences=divergences,
        )

    # -- internals --------------------------------------------------------------

    def _average_target_mastery(
        self, *, profile: LearnerProfile, target_kc_ids: list[str]
    ) -> float:
        if not target_kc_ids:
            return _UNKNOWN_MASTERY
        kc_mastery = profile.knowledge_state.kc_mastery
        values = [kc_mastery.get(kc_id, _UNKNOWN_MASTERY) for kc_id in target_kc_ids]
        return sum(values) / len(values)

    def _mastery_snapshot(
        self, *, profile: LearnerProfile | None, kc_ids: list[str] | list[object]
    ) -> dict[str, float]:
        if profile is None:
            return {}
        kc_mastery = profile.knowledge_state.kc_mastery
        return {
            str(kc_id): kc_mastery.get(str(kc_id), _UNKNOWN_MASTERY) for kc_id in kc_ids
        }

    def _emit(
        self,
        *,
        decision_point: str,
        student_id: str,
        production_decision: dict[str, object],
        baseline_decision: dict[str, object],
        agreed: bool,
        inputs: dict[str, object],
    ) -> None:
        digest = hashlib.sha256(
            json.dumps(inputs, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        self.audit_store.append(
            event_type=BASELINE_DECISION_EVENT_TYPE,
            status="agreed" if agreed else "diverged",
            student_id=student_id,
            payload={
                "decision_point": decision_point,
                "production_decision": production_decision,
                "baseline_decision": baseline_decision,
                "agreed": agreed,
                "inputs_digest": digest,
            },
        )


@dataclass(slots=True)
class BaselineShadowedRouter:
    """Log-only wrapper around the production router. Delegates the real
    decision unchanged; shadow-logging failures are swallowed so they can
    never affect routing."""

    inner: RouterPlugin
    baseline_policy: BaselinePolicyService

    def route(
        self, profile: LearnerProfile, request: GenerationRequest
    ) -> AdaptiveRouteDecision:
        decision = self.inner.route(profile, request)
        try:
            self.baseline_policy.record_route_decision(
                profile=profile, request=request, production=decision
            )
        except Exception:  # noqa: BLE001 - shadow logging must never break routing
            pass
        return decision

    def __getattr__(self, name: str) -> object:
        return getattr(self.inner, name)


@dataclass(slots=True)
class BaselineShadowedProgressionOwnership:
    """Log-only wrapper around ProgressionOwnershipService.resolve_request."""

    inner: ProgressionOwnershipService
    baseline_policy: BaselinePolicyService

    def resolve_request(
        self, *, student_id: UUID, request: GenerationRequest
    ) -> ProgressionOwnershipDecision:
        decision = self.inner.resolve_request(student_id=student_id, request=request)
        try:
            self.baseline_policy.record_progression_decision(
                student_id=student_id, request=request, production=decision
            )
        except Exception:  # noqa: BLE001 - shadow logging must never break progression
            pass
        return decision

    def __getattr__(self, name: str) -> object:
        return getattr(self.inner, name)
