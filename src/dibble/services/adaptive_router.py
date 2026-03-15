from __future__ import annotations

import hashlib
import random

from dibble.models.generation import (
    AdaptiveRouteDecision,
    ContentIntent,
    DeliveryMode,
    GenerationRequest,
    InterventionType,
)
from dibble.models.profile import LearnerProfile, SignalLevel


class AdaptiveRouter:
    def route(self, profile: LearnerProfile, request: GenerationRequest) -> AdaptiveRouteDecision:
        target_mastery = self._average_target_mastery(profile, request)

        if (
            profile.affective_state.frustration in {SignalLevel.medium, SignalLevel.high}
            or profile.cognitive_load.total_load >= 0.8
        ):
            return AdaptiveRouteDecision(
                intervention_type=InterventionType.step_back,
                delivery_mode=DeliveryMode.generated,
                scaffolding_level="high",
                reasons=[
                    "High frustration or cognitive load triggered the router's safety constraint for a step-back intervention.",
                    "Constraint handling runs before Thompson sampling for high-risk learner states.",
                ],
            )

        if request.intent == ContentIntent.practice and target_mastery < 0.45:
            return AdaptiveRouteDecision(
                intervention_type=InterventionType.targeted_practice,
                delivery_mode=DeliveryMode.generated,
                scaffolding_level="medium",
                reasons=[
                    f"Target mastery is {target_mastery:.2f}, so the router selected targeted practice as the safest high-yield action.",
                    "This low-mastery practice path is treated as a deterministic curriculum guardrail.",
                ],
            )

        if (
            target_mastery >= 0.8
            and profile.affective_state.engagement == SignalLevel.high
            and profile.cognitive_load.total_load < 0.6
        ):
            return AdaptiveRouteDecision(
                intervention_type=InterventionType.stretch,
                delivery_mode=DeliveryMode.blended,
                scaffolding_level="low",
                reasons=[
                    "High mastery and strong engagement cleared the router's stretch-readiness constraint.",
                    "Constraint handling bypassed Thompson sampling because the learner is ready for extension work.",
                ],
            )

        scores = self._build_action_priors(profile, request, target_mastery)
        rng = random.Random(self._seed_for(profile, request))

        chosen_action = max(
            scores,
            key=lambda action: rng.betavariate(scores[action][0], scores[action][1]),
        )

        alpha, beta = scores[chosen_action]
        reasons = [self._reason_for(chosen_action, target_mastery, profile)]
        reasons.append(f"Thompson prior alpha={alpha:.2f}, beta={beta:.2f} selected the highest sampled action.")

        return AdaptiveRouteDecision(
            intervention_type=chosen_action,
            delivery_mode=self._delivery_mode_for(chosen_action),
            scaffolding_level=self._scaffolding_for(chosen_action),
            reasons=reasons,
        )

    def _average_target_mastery(self, profile: LearnerProfile, request: GenerationRequest) -> float:
        if request.target_kc_ids:
            values = [
                profile.knowledge_state.kc_mastery.get(kc_id, 0.0)
                for kc_id in request.target_kc_ids
            ]
        elif request.target_lo_ids:
            values = [
                profile.knowledge_state.lo_mastery.get(lo_id, 0.0)
                for lo_id in request.target_lo_ids
            ]
        else:
            values = list(profile.knowledge_state.kc_mastery.values()) or [0.5]

        return sum(values) / len(values)

    def _build_action_priors(
        self,
        profile: LearnerProfile,
        request: GenerationRequest,
        target_mastery: float,
    ) -> dict[InterventionType, tuple[float, float]]:
        frustration = profile.affective_state.frustration
        engagement = profile.affective_state.engagement
        load = profile.cognitive_load.total_load

        priors = {
            InterventionType.step_back: (
                1.0 + (2.5 if frustration in {SignalLevel.medium, SignalLevel.high} else 0.3) + (2.0 if load >= 0.8 else 0.1),
                1.0 + max(target_mastery - 0.4, 0.0),
            ),
            InterventionType.targeted_practice: (
                1.0 + (2.2 if request.intent == ContentIntent.practice else 0.4) + max(0.6 - target_mastery, 0.0) * 3,
                1.0 + max(target_mastery - 0.5, 0.0) * 2,
            ),
            InterventionType.reteach: (
                1.0 + (1.6 if 0.45 <= target_mastery < 0.8 else 0.6),
                1.0 + (1.0 if frustration == SignalLevel.high else 0.4),
            ),
            InterventionType.stretch: (
                1.0 + max(target_mastery - 0.75, 0.0) * 6 + (1.0 if engagement == SignalLevel.high else 0.1),
                1.0 + (2.0 if frustration in {SignalLevel.medium, SignalLevel.high} else 0.2) + (1.5 if load >= 0.7 else 0.2),
            ),
        }

        return priors

    def _seed_for(self, profile: LearnerProfile, request: GenerationRequest) -> int:
        key = "|".join(
            [
                str(profile.student_id),
                request.intent.value,
                ",".join(sorted(request.target_kc_ids)),
                ",".join(sorted(request.target_lo_ids)),
                ",".join(sorted(request.curriculum_context)),
            ]
        )
        return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)

    def _reason_for(
        self,
        intervention_type: InterventionType,
        target_mastery: float,
        profile: LearnerProfile,
    ) -> str:
        if intervention_type == InterventionType.step_back:
            return "High frustration or cognitive load shifted the bandit toward a step-back intervention."
        if intervention_type == InterventionType.targeted_practice:
            return f"Target mastery is {target_mastery:.2f}, so targeted practice has the strongest near-term learning reward."
        if intervention_type == InterventionType.stretch:
            return "High mastery and strong engagement made stretch work the best sampled action."
        return "The learner is between novice and mastery, so reteaching is the strongest grounded explanation path."

    def _delivery_mode_for(self, intervention_type: InterventionType) -> DeliveryMode:
        if intervention_type == InterventionType.stretch:
            return DeliveryMode.blended
        return DeliveryMode.generated

    def _scaffolding_for(self, intervention_type: InterventionType) -> str:
        mapping = {
            InterventionType.step_back: "high",
            InterventionType.targeted_practice: "medium",
            InterventionType.reteach: "medium",
            InterventionType.stretch: "low",
        }
        return mapping[intervention_type]
