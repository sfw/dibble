from __future__ import annotations

import json
from dataclasses import dataclass, field

from dibble.models.generation import (
    AdaptiveRouteDecision,
    AdaptiveScoreComponent,
    GenerationRequest,
    ModalityCandidateScore,
    ModalityRoutingInspection,
    ModalityRoutingPrior,
    RoutingPriorScope,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import ModalityPlugins, RouterPlugin
from dibble.services.protocols import AuditStore, ModalityRoutingPriorStore

_GLOBAL_CONTEXT_KEY = "__global__"


@dataclass(frozen=True, slots=True)
class ModalityDirective:
    modality: str
    plugin_id: str
    composition_mode: str
    plugin_ids: tuple[str, ...] = ("text",)


@dataclass(frozen=True, slots=True)
class TextModalityDirective(ModalityDirective):
    modality: str = "text"
    plugin_id: str = "text"
    composition_mode: str = "single"
    plugin_ids: tuple[str, ...] = ("text",)


@dataclass(frozen=True, slots=True)
class ModalityRoutingPlan:
    route: AdaptiveRouteDecision
    pedagogical_move: str
    context_key: str = _GLOBAL_CONTEXT_KEY
    directive: ModalityDirective = field(default_factory=TextModalityDirective)
    theme_family: str | None = None
    locale: str | None = None
    accessibility_requirements: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    inspection: ModalityRoutingInspection | None = None


@dataclass(slots=True)
class ModalityRoutingHarness:
    router: RouterPlugin
    modality_plugins: ModalityPlugins
    prior_store: ModalityRoutingPriorStore | None = None
    audit_store: AuditStore | None = None

    def plan(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
    ) -> ModalityRoutingPlan:
        route = self.router.route(profile, request)
        inspection = self.inspect(profile=profile, request=request, route=route)
        plugin = self.modality_plugins.plugins[inspection.selected_plugin_id]
        directive = ModalityDirective(
            modality=plugin.modality,
            plugin_id=plugin.plugin_id,
            composition_mode=plugin.composition_mode,
            plugin_ids=tuple(
                item.plugin_id
                for item in self.modality_plugins.chain_for(plugin.plugin_id)
            ),
        )
        return ModalityRoutingPlan(
            route=route,
            pedagogical_move=route.intervention_type.value,
            context_key=inspection.context_key,
            directive=directive,
            theme_family=(
                profile.learning_preferences.example_domain_preferences[0]
                if profile.learning_preferences.example_domain_preferences
                else None
            ),
            accessibility_requirements=list(profile.accommodations),
            rationale=list(route.reasons)
            + [f"modality:{directive.plugin_id}"]
            + _selected_rationale(inspection=inspection),
            inspection=inspection,
        )

    def inspect(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision | None = None,
    ) -> ModalityRoutingInspection:
        resolved_route = route or self.router.route(profile, request)
        context_key = self.context_key_for(request=request, route=resolved_route)
        explicit_signals = self._explicit_signals_for(request=request)
        candidate_scores: list[ModalityCandidateScore] = []
        priors: list[ModalityRoutingPrior] = []
        heuristic_winner_id = "text"
        heuristic_winner_score = -1.0
        recent_streaks = self._recent_modality_streaks(student_id=profile.student_id)
        for plugin_id, plugin in self.modality_plugins.plugins.items():
            composition_key = "+".join(
                item.plugin_id for item in self.modality_plugins.chain_for(plugin_id)
            )
            plugin_prior, composition_prior = self._resolved_priors(
                learner_id=profile.student_id,
                plugin_id=plugin_id,
                composition_key=composition_key,
                context_key=context_key,
            )
            priors.extend(
                prior
                for prior in (plugin_prior, composition_prior)
                if prior is not None
            )
            base_score = self._heuristic_score(
                profile=profile,
                request=request,
                route=resolved_route,
                plugin_id=plugin_id,
                explicit_signals=explicit_signals,
            )
            if base_score > heuristic_winner_score:
                heuristic_winner_id = plugin_id
                heuristic_winner_score = base_score
            prior_score = self._prior_score(plugin_prior=plugin_prior)
            composition_score = self._prior_score(plugin_prior=composition_prior)
            outcome_delta = (
                plugin_prior.recent_outcome_delta if plugin_prior is not None else 0.0
            )
            engagement_delta = (
                plugin_prior.recent_engagement_delta
                if plugin_prior is not None
                else 0.0
            )
            progress_delta = (
                plugin_prior.recent_progress_delta if plugin_prior is not None else 0.0
            )
            repetition_penalty = self._repetition_penalty(
                plugin_id=plugin_id,
                recent_streaks=recent_streaks,
                plugin_prior=plugin_prior,
            )
            recovery_bonus = self._recovery_bonus(plugin_prior=plugin_prior)
            total_score = max(
                0.0,
                min(
                    1.0,
                    round(
                        base_score
                        + (prior_score * 0.28)
                        + (composition_score * 0.10)
                        + (outcome_delta * 0.10)
                        + (engagement_delta * 0.06)
                        + (progress_delta * 0.08)
                        + recovery_bonus
                        - repetition_penalty,
                        2,
                    ),
                ),
            )
            candidate_scores.append(
                ModalityCandidateScore(
                    plugin_id=plugin_id,
                    modality=plugin.modality,
                    composition_key=composition_key,
                    total_score=total_score,
                    evidence_count=plugin_prior.evidence_count if plugin_prior else 0,
                    score_components=[
                        AdaptiveScoreComponent(
                            label="heuristic_fit",
                            value=round(base_score - 0.5, 2),
                            detail=(
                                "Current pedagogical move, request cues, and known learner"
                                " modality affinities still anchor the decision."
                            ),
                        ),
                        AdaptiveScoreComponent(
                            label="outcome_prior",
                            value=round(prior_score * 0.28, 2),
                            detail=_prior_detail(prior=plugin_prior),
                        ),
                        AdaptiveScoreComponent(
                            label="composition_prior",
                            value=round(composition_score * 0.10, 2),
                            detail=_prior_detail(prior=composition_prior),
                        ),
                        AdaptiveScoreComponent(
                            label="engagement_delta",
                            value=round(engagement_delta * 0.06, 2),
                            detail="Recent engagement changes are bounded so weak evidence stays conservative.",
                        ),
                        AdaptiveScoreComponent(
                            label="progress_delta",
                            value=round(progress_delta * 0.08, 2),
                            detail="Recent progress changes can tilt the choice without overwhelming pedagogy.",
                        ),
                        AdaptiveScoreComponent(
                            label="repetition_penalty",
                            value=round(-repetition_penalty, 2),
                            detail="Repeated recent use is mildly penalized unless the modality is clearly recovering.",
                        ),
                        AdaptiveScoreComponent(
                            label="recovery_bonus",
                            value=round(recovery_bonus, 2),
                            detail="Successful rebounds after weak runs earn a small recovery credit.",
                        ),
                    ],
                    rationale=[
                        f"heuristic={base_score:.2f}",
                        f"prior={prior_score:.2f}",
                        f"composition={composition_score:.2f}",
                        f"streak={recent_streaks.get(plugin_id, 0)}",
                    ],
                )
            )
        deduped_priors = _dedupe_priors(priors=priors)
        candidate_scores.sort(
            key=lambda item: (item.total_score, item.evidence_count, item.plugin_id),
            reverse=True,
        )
        selected = candidate_scores[0]
        weak_evidence_fallback_applied = False
        if (
            selected.plugin_id != heuristic_winner_id
            and selected.evidence_count < 2
            and len(candidate_scores) > 1
            and abs(selected.total_score - heuristic_winner_score) < 0.12
        ):
            selected = next(
                item for item in candidate_scores if item.plugin_id == heuristic_winner_id
            )
            weak_evidence_fallback_applied = True
        return ModalityRoutingInspection(
            learner_id=profile.student_id,
            context_key=context_key,
            selected_plugin_id=selected.plugin_id,
            selected_modality=selected.modality,
            weak_evidence_fallback_applied=weak_evidence_fallback_applied,
            candidate_scores=candidate_scores,
            priors=deduped_priors,
        )

    def context_key_for(
        self,
        *,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
    ) -> str:
        payload = {
            "intent": request.intent.value,
            "requested_content_type": (
                request.requested_content_type.value
                if request.requested_content_type is not None
                else None
            ),
            "target_kc_ids": sorted(request.target_kc_ids),
            "target_lo_ids": sorted(request.target_lo_ids),
            "intervention_type": route.intervention_type.value,
            "scaffolding_level": route.scaffolding_level,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _explicit_signals_for(self, *, request: GenerationRequest) -> dict[str, bool]:
        request_text = " ".join(request.curriculum_context + [request.learner_prompt or ""]).lower()
        return {
            "visual": any(
                token in request_text
                for token in ("diagram", "visual", "model", "graph", "chart")
            ),
            "narrative": any(
                token in request_text
                for token in ("narrative", "story", "storytelling", "tell a story")
            ),
        }

    def _heuristic_score(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
        plugin_id: str,
        explicit_signals: dict[str, bool],
    ) -> float:
        affinities = profile.learning_preferences.modality_affinity
        textual_affinity = float(affinities.get("textual", 0.8))
        visual_affinity = float(affinities.get("visual", 0.6))
        requested_content_type = (
            request.requested_content_type.value
            if request.requested_content_type is not None
            else None
        )
        if plugin_id == "diagram":
            score = 0.42 + (visual_affinity * 0.18)
            if requested_content_type == "worked_example":
                score += 0.10
            if explicit_signals["visual"]:
                score += 0.14
            if profile.cognitive_load.total_load >= 0.86:
                score -= 0.05
            return round(min(score, 0.95), 2)
        if plugin_id == "narrative":
            score = 0.40 + (textual_affinity * 0.14)
            if explicit_signals["narrative"]:
                score += 0.14
            if route.intervention_type.value in {"reteach", "step_back"}:
                score += 0.04
            if requested_content_type == "micro_explanation":
                score += 0.06
            if requested_content_type == "remedial_micro_module":
                score -= 0.04
            if profile.cognitive_load.total_load >= 0.84:
                score -= 0.04
            return round(min(score, 0.92), 2)
        score = 0.48 + (textual_affinity * 0.16)
        if requested_content_type == "practice_problem":
            score += 0.04
        if route.intervention_type.value == "stretch":
            score += 0.02
        return round(min(score, 0.94), 2)

    def _resolved_priors(
        self,
        *,
        learner_id,
        plugin_id: str,
        composition_key: str,
        context_key: str,
    ) -> tuple[ModalityRoutingPrior | None, ModalityRoutingPrior | None]:
        if self.prior_store is None:
            return None, None
        plugin_prior = self.prior_store.get(
            learner_id=learner_id,
            scope=RoutingPriorScope.plugin.value,
            prior_key=plugin_id,
            context_key=context_key,
        ) or self.prior_store.get(
            learner_id=learner_id,
            scope=RoutingPriorScope.plugin.value,
            prior_key=plugin_id,
            context_key=_GLOBAL_CONTEXT_KEY,
        )
        composition_prior = self.prior_store.get(
            learner_id=learner_id,
            scope=RoutingPriorScope.composition.value,
            prior_key=composition_key,
            context_key=context_key,
        ) or self.prior_store.get(
            learner_id=learner_id,
            scope=RoutingPriorScope.composition.value,
            prior_key=composition_key,
            context_key=_GLOBAL_CONTEXT_KEY,
        )
        return plugin_prior, composition_prior

    def _prior_score(self, *, plugin_prior: ModalityRoutingPrior | None) -> float:
        if plugin_prior is None:
            return 0.0
        evidence_weight = min(plugin_prior.evidence_count / 3.0, 1.0)
        return round(
            ((plugin_prior.average_outcome_score - 0.5) * evidence_weight),
            2,
        )

    def _recent_modality_streaks(self, *, student_id) -> dict[str, int]:
        if self.audit_store is None:
            return {}
        events = [
            event
            for event in self.audit_store.list(limit=12)
            if event.event_type == "content.generate" and event.student_id == student_id
        ]
        streaks: dict[str, int] = {}
        for event in events:
            plugin_id = str(event.payload.get("modality_plugin_id", "text"))
            if plugin_id not in streaks:
                streaks[plugin_id] = 0
            streaks[plugin_id] += 1
            if streaks[plugin_id] >= 3:
                break
        return streaks

    def _repetition_penalty(
        self,
        *,
        plugin_id: str,
        recent_streaks: dict[str, int],
        plugin_prior: ModalityRoutingPrior | None,
    ) -> float:
        streak = recent_streaks.get(plugin_id, 0)
        if streak <= 1:
            return 0.0
        penalty = min(0.04 * streak, 0.12)
        if plugin_prior is not None and plugin_prior.recovery_rate >= 0.5:
            penalty *= 0.5
        return round(penalty, 2)

    def _recovery_bonus(self, *, plugin_prior: ModalityRoutingPrior | None) -> float:
        if plugin_prior is None or plugin_prior.recovery_rate <= 0.0:
            return 0.0
        if plugin_prior.average_outcome_score < 0.6:
            return 0.0
        return round(min(plugin_prior.recovery_rate * 0.05, 0.05), 2)


def _prior_detail(prior: ModalityRoutingPrior | None) -> str:
    if prior is None:
        return "No durable evidence yet, so the router stays close to the heuristic baseline."
    return (
        f"{prior.evidence_count} evidence sample(s); avg outcome "
        f"{prior.average_outcome_score:.2f}; recovery rate {prior.recovery_rate:.2f}."
    )


def _selected_rationale(
    *,
    inspection: ModalityRoutingInspection,
) -> list[str]:
    selected = next(
        (
            item
            for item in inspection.candidate_scores
            if item.plugin_id == inspection.selected_plugin_id
        ),
        None,
    )
    if selected is None:
        return []
    lines = [f"modality_score:{selected.total_score:.2f}"]
    if inspection.weak_evidence_fallback_applied:
        lines.append("weak_evidence_fallback:text_first")
    return lines


def _dedupe_priors(
    *,
    priors: list[ModalityRoutingPrior],
) -> list[ModalityRoutingPrior]:
    deduped: dict[tuple[str, str, str], ModalityRoutingPrior] = {}
    for prior in priors:
        deduped[(prior.scope.value, prior.prior_key, prior.context_key)] = prior
    return list(deduped.values())
