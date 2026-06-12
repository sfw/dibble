from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from dibble.models.curriculum import CurriculumVersionReference
from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContentIntent(str, Enum):
    explanation = "explanation"
    practice = "practice"
    remediation = "remediation"
    assessment = "assessment"


class RequestedContentType(str, Enum):
    micro_explanation = "micro_explanation"
    worked_example = "worked_example"
    practice_problem = "practice_problem"
    remedial_micro_module = "remedial_micro_module"
    assessment_probe = "assessment_probe"


class WorkedExampleFading(str, Enum):
    full = "full"
    completion = "completion"
    independent = "independent"


class PracticeDifficultyBand(str, Enum):
    support = "support"
    on_grade = "on_grade"
    stretch = "stretch"


class InterventionType(str, Enum):
    step_back = "step_back"
    targeted_practice = "targeted_practice"
    reteach = "reteach"
    stretch = "stretch"


class DeliveryMode(str, Enum):
    generated = "generated"
    blended = "blended"
    static_fallback = "static_fallback"


class GenerationRequest(BaseModel):
    student_id: UUID
    learning_session_id: str | None = None
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    curriculum_provenance: CurriculumVersionReference | None = None
    intent: ContentIntent = ContentIntent.explanation
    requested_content_type: RequestedContentType | None = None
    learner_prompt: str | None = None
    curriculum_context: list[str] = Field(default_factory=list)
    predictive_warm: bool = False
    warm_reason: str | None = None
    source_generation_id: str | None = None
    target_kc_hints: list["TargetKcGenerationHint"] = Field(default_factory=list)
    mode_calibration: "GenerationModeCalibration | None" = None


class CurriculumContentRequest(BaseModel):
    grade_level: str
    intent: ContentIntent = ContentIntent.explanation
    content_type: RequestedContentType
    target_kc_ids: list[str] = Field(default_factory=list)
    target_lo_ids: list[str] = Field(default_factory=list)
    curriculum_provenance: CurriculumVersionReference | None = None
    curriculum_context: list[str] = Field(default_factory=list)
    target_kc_hints: list["TargetKcGenerationHint"] = Field(default_factory=list)
    delivery_tone: str = "Keep the tone calm, specific, and encouraging."
    prompt_guidance: str = ""
    generation_constraints: dict[str, object] = Field(default_factory=dict)
    adaptive_variant_hint: str | None = None

    def prompt_selection_key(self) -> str:
        payload = {
            "grade_level": self.grade_level,
            "intent": self.intent.value,
            "content_type": self.content_type.value,
            "target_kc_ids": sorted(self.target_kc_ids),
            "target_lo_ids": sorted(self.target_lo_ids),
            "curriculum_provenance": (
                self.curriculum_provenance.model_dump(mode="json")
                if self.curriculum_provenance is not None
                else None
            ),
            "curriculum_context": sorted(self.curriculum_context),
            "target_kc_hints": sorted(
                hint.model_dump_json() for hint in self.target_kc_hints
            ),
            "adaptive_variant_hint": self.adaptive_variant_hint,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()

    def cache_identity_payload(self) -> dict[str, object]:
        return {
            "grade_level": self.grade_level,
            "intent": self.intent.value,
            "content_type": self.content_type.value,
            "target_kc_ids": sorted(self.target_kc_ids),
            "target_lo_ids": sorted(self.target_lo_ids),
            "curriculum_provenance": (
                self.curriculum_provenance.model_dump(mode="json")
                if self.curriculum_provenance is not None
                else None
            ),
            "curriculum_context": sorted(self.curriculum_context),
            "target_kc_hints": sorted(
                hint.model_dump_json() for hint in self.target_kc_hints
            ),
            "provider_safe_guidance": {
                "delivery_tone": self.delivery_tone,
                "adaptive_variant_hint": self.adaptive_variant_hint,
                "generation_constraints": _cache_safe_generation_constraints(
                    self.generation_constraints
                ),
            },
        }


class GenerationModeCalibration(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_run_count: int = Field(default=0, ge=0)
    average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    progress_signal: str = "insufficient"
    progress_delta: float = 0.0
    support_bias: int = Field(default=0, ge=-1, le=1)
    strategy_signal: str = "insufficient"
    strategy_recovery_focus: str = "monitor"
    strategy_trajectory_state: str = "insufficient"
    strategy_recommended_next_action: str = "monitor"
    strategy_volatility_index: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_relapse_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    strategy_source: str = "insufficient"
    strategy_rationale: str | None = None
    state_profile_signal: str = "insufficient"
    state_profile_source: str = "insufficient"
    state_profile_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_total_load: float = Field(default=0.4, ge=0.0, le=1.0)
    state_profile_confidence_calibration: float = Field(default=0.5, ge=0.0, le=1.0)
    state_profile_help_seeking: str = "low"
    state_profile_affective_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_load_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_recovery_stability: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_overload_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    state_profile_metacognitive_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_signal: str = "insufficient"
    trait_profile_source: str = "insufficient"
    trait_profile_trait_stability: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_challenge_tolerance: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_challenge_evidence_strength: float = Field(
        default=0.0, ge=0.0, le=1.0
    )
    trait_profile_processing_speed_reliability: float = Field(
        default=0.0, ge=0.0, le=1.0
    )
    trait_profile_working_memory_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    trait_profile_spatial_reasoning_reliability: float = Field(
        default=0.0, ge=0.0, le=1.0
    )
    strategy_sequence_action: str = "monitor"
    strategy_sequence_primary_kc_id: str | None = None
    strategy_sequence_kc_ids: list[str] = Field(default_factory=list)
    strategy_sequence_deferred_kc_ids: list[str] = Field(default_factory=list)
    strategy_sequence_rationale: str | None = None
    sequence_action: str = "monitor"
    sequence_primary_kc_id: str | None = None
    sequence_kc_ids: list[str] = Field(default_factory=list)
    sequence_deferred_kc_ids: list[str] = Field(default_factory=list)
    sequence_source: str = "insufficient"
    sequence_rationale: str | None = None
    session_signal: str = "insufficient"
    session_source: str = "insufficient"
    session_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    session_support_bias: int = Field(default=0, ge=-1, le=1)
    session_sequence_action: str = "monitor"
    session_primary_kc_id: str | None = None
    session_observation_count: int = Field(default=0, ge=0)
    session_assessment_count: int = Field(default=0, ge=0)
    session_phase: str = "monitor"
    session_recovery_intent: str = "monitor"
    session_support_step_budget: int = Field(default=0, ge=0)
    session_support_steps_remaining: int = Field(default=0, ge=0)
    session_stuck_loop_risk: str = "low"
    session_arc_action: str = "steady"
    session_generated_step_count: int = Field(default=0, ge=0)
    session_positive_streak: int = Field(default=0, ge=0)
    session_negative_streak: int = Field(default=0, ge=0)
    current_evidence_signal: str = "steady"
    current_evidence_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    current_evidence_rationale: str | None = None
    session_latest_prompt_style: str | None = None
    session_latest_next_action: str = "monitor"
    session_latest_evidence_strength: str = "insufficient"
    socratic_steering_action: str = "steady"
    socratic_profile_signal: str = "insufficient"
    socratic_profile_source: str = "insufficient"
    socratic_profile_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    socratic_profile_dominant_action: str = "steady"
    socratic_profile_transfer_readiness: float = Field(default=0.0, ge=0.0, le=1.0)
    socratic_profile_loop_break_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    socratic_profile_rationale: str | None = None
    session_rationale: str | None = None
    rationale: str | None = None


class RouteCalibrationSummary(BaseModel):
    signal: str = "insufficient"
    source: str = "insufficient"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    average_run_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    matched_run_count: int = Field(default=0, ge=0)
    positive_run_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    negative_run_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    progress_signal: str = "insufficient"
    progress_delta: float = 0.0


class RoutingPriorScope(str, Enum):
    plugin = "plugin"
    composition = "composition"


class AdaptiveScoreComponent(BaseModel):
    label: str
    value: float = Field(default=0.0, ge=-1.0, le=1.0)
    detail: str


class ModalityRoutingPrior(BaseModel):
    learner_id: UUID
    scope: RoutingPriorScope
    prior_key: str
    context_key: str = "__global__"
    evidence_count: int = Field(default=0, ge=0)
    average_outcome_score: float = Field(default=0.5, ge=0.0, le=1.0)
    average_engagement_score: float = Field(default=0.5, ge=0.0, le=1.0)
    average_progress_score: float = Field(default=0.5, ge=0.0, le=1.0)
    recent_outcome_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    recent_engagement_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    recent_progress_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    positive_outcome_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    recovery_attempt_count: int = Field(default=0, ge=0)
    recovery_success_count: int = Field(default=0, ge=0)
    last_outcome_score: float | None = Field(default=None, ge=0.0, le=1.0)
    last_selected_at: datetime | None = None
    last_outcome_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def recovery_rate(self) -> float:
        if self.recovery_attempt_count <= 0:
            return 0.0
        return round(
            self.recovery_success_count / self.recovery_attempt_count,
            2,
        )


class ModalityCandidateScore(BaseModel):
    plugin_id: str
    modality: str
    composition_key: str
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)
    score_components: list[AdaptiveScoreComponent] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class ModalityRoutingInspection(BaseModel):
    learner_id: UUID
    context_key: str
    selected_plugin_id: str
    selected_modality: str
    effective_plugin_id: str | None = None
    effective_modality: str | None = None
    rollout_bucket_id: str | None = None
    policy_fallback_applied: bool = False
    policy_reason: str | None = None
    weak_evidence_fallback_applied: bool = False
    candidate_scores: list[ModalityCandidateScore] = Field(default_factory=list)
    priors: list[ModalityRoutingPrior] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def populate_effective_selection(self) -> "ModalityRoutingInspection":
        if self.effective_plugin_id is None:
            self.effective_plugin_id = self.selected_plugin_id
        if self.effective_modality is None:
            self.effective_modality = self.selected_modality
        return self


class AdaptiveRouteDecision(BaseModel):
    intervention_type: InterventionType
    delivery_mode: DeliveryMode
    scaffolding_level: str
    reasons: list[str]
    calibration: RouteCalibrationSummary | None = None


class GroundingReference(BaseModel):
    outcome_id: str
    title: str
    grade_level: str
    subject: str | None = None
    curriculum_provenance: CurriculumVersionReference | None = None
    score: float = Field(ge=0.0)
    matched_terms: list[str] = Field(default_factory=list)
    excerpt: str | None = None

    def cache_identity_payload(self) -> dict[str, object]:
        return {
            "outcome_id": self.outcome_id,
            "grade_level": self.grade_level,
            "subject": self.subject,
            "curriculum_provenance": (
                self.curriculum_provenance.model_dump(mode="json")
                if self.curriculum_provenance is not None
                else None
            ),
        }


class CurriculumContentKey(BaseModel):
    request: CurriculumContentRequest
    route: "AdaptiveRouteDecision"
    grounding: list[GroundingReference] = Field(default_factory=list)

    def selection_key(self) -> str:
        payload = {
            "request": {
                "grade_level": self.request.grade_level,
                "intent": self.request.intent.value,
                "content_type": self.request.content_type.value,
                "target_kc_ids": sorted(self.request.target_kc_ids),
                "target_lo_ids": sorted(self.request.target_lo_ids),
                "curriculum_context": sorted(self.request.curriculum_context),
                "target_kc_hints": sorted(
                    hint.model_dump_json() for hint in self.request.target_kc_hints
                ),
            },
            "route": {
                "intervention_type": self.route.intervention_type.value,
                "scaffolding_level": self.route.scaffolding_level,
            },
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()

    def cache_key(self) -> str:
        payload = {
            "request": self.request.cache_identity_payload(),
            "route": {
                "intervention_type": self.route.intervention_type.value,
                "delivery_mode": self.route.delivery_mode.value,
                "scaffolding_level": self.route.scaffolding_level,
            },
            "grounding": sorted(
                [
                    (
                        item.cache_identity_payload()
                        if isinstance(item, GroundingReference)
                        else GroundingReference.model_validate(
                            item
                        ).cache_identity_payload()
                    )
                    for item in self.grounding
                ],
                key=lambda item: (
                    str(item.get("outcome_id", "")),
                    str(item.get("grade_level", "")),
                    str(item.get("subject", "")),
                ),
            ),
        }
        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(serialized.encode("utf-8")).hexdigest()


class CurriculumLibraryStorageScope(str, Enum):
    local_only = "local_only"
    shared_ready = "shared_ready"


def _cache_safe_generation_constraints(
    generation_constraints: dict[str, object],
) -> dict[str, object]:
    safe_items: dict[str, object] = {}
    for key, value in generation_constraints.items():
        if key.endswith("_rationale") or key == "mode_calibration_applied":
            continue
        safe_items[key] = value
    return safe_items


def _svg_aria_label(svg: str | None) -> str | None:
    if not svg:
        return None
    match = re.search(r"aria-label=['\"]([^'\"]+)['\"]", svg)
    return match.group(1) if match is not None else None


class BlockVerification(BaseModel):
    """Machine-checkable answer contract emitted alongside practice items.

    ``answer_expression`` is the computation that produces the key (e.g.
    ``"3/4 + 1/8"``); ``answer_value`` is the claimed key (e.g. ``"7/8"``).
    ``distractor_values`` are the wrong-answer options, each of which must NOT
    equal the key. ``coverage`` is ``partial`` for word problems where only the
    embedded computation can be checked."""

    answer_expression: str | None = None
    answer_value: str | None = None
    distractor_values: list[str] = Field(default_factory=list)
    solution_path_expression: str | None = None
    coverage: Literal["full", "partial"] = "full"


class GeneratedBlock(BaseModel):
    block_id: str | None = None
    kind: str
    title: str
    body: str
    interaction: "MultipleChoiceInteraction | None" = None
    verification: BlockVerification | None = None


class MultipleChoiceOption(BaseModel):
    option_id: str
    label: str
    body: str
    rationale: str | None = None


class DeferredTextReveal(BaseModel):
    trigger: Literal["after_selection"] = "after_selection"
    prompt: str
    support: str | None = None
    placeholder: str | None = None


class MultipleChoiceInteraction(BaseModel):
    type: Literal["multiple_choice"] = "multiple_choice"
    prompt: str
    options: list[MultipleChoiceOption] = Field(default_factory=list)
    correct_option_id: str
    reveal: DeferredTextReveal | None = None
    allow_retry: bool = False


class GeneratedBlockChunk(BaseModel):
    block_index: int
    kind: str = ""
    title: str = ""
    body_delta: str = ""
    block: GeneratedBlock | None = None
    done: bool = False

    @model_validator(mode="after")
    def populate_legacy_fields(self) -> "GeneratedBlockChunk":
        if self.block is not None:
            if not self.kind:
                self.kind = self.block.kind
            if not self.title:
                self.title = self.block.title
        return self


class GeneratedTextArtifact(BaseModel):
    artifact_id: str
    artifact_type: Literal["text"] = "text"
    sequence_index: int = Field(default=0, ge=0)
    role: str
    title: str
    mime_type: str = "text/plain"
    text: str
    accessibility: "ArtifactAccessibility" = Field(
        default_factory=lambda: ArtifactAccessibility()
    )
    provenance: "ArtifactProvenance" = Field(
        default_factory=lambda: ArtifactProvenance(
            modality="text",
            plugin_id="text",
        )
    )


class ArtifactAccessibility(BaseModel):
    alt_text: str | None = None
    text_equivalent: str | None = None
    supports_screen_reader: bool = True


class ArtifactProvenance(BaseModel):
    modality: str
    plugin_id: str
    source_block_kind: str | None = None
    generated_by: str = "modality_plugin"


class GeneratedNarrativeArtifact(BaseModel):
    artifact_id: str
    artifact_type: Literal["narrative"] = "narrative"
    sequence_index: int = Field(default=0, ge=0)
    role: str
    title: str
    mime_type: str = "text/plain"
    text: str
    narrator_style: str = "guided_story"
    accessibility: ArtifactAccessibility = Field(default_factory=ArtifactAccessibility)
    provenance: ArtifactProvenance = Field(
        default_factory=lambda: ArtifactProvenance(
            modality="narrative",
            plugin_id="narrative",
        )
    )


class GeneratedDiagramArtifact(BaseModel):
    artifact_id: str
    artifact_type: Literal["diagram"] = "diagram"
    sequence_index: int = Field(default=0, ge=0)
    title: str
    mime_type: str = "image/svg+xml"
    svg: str | None = None
    caption: str | None = None
    accessibility: ArtifactAccessibility = Field(default_factory=ArtifactAccessibility)
    provenance: ArtifactProvenance = Field(
        default_factory=lambda: ArtifactProvenance(
            modality="diagram",
            plugin_id="diagram",
        )
    )


GeneratedArtifact = (
    GeneratedTextArtifact | GeneratedNarrativeArtifact | GeneratedDiagramArtifact
)


def build_generated_artifacts(
    blocks: list["GeneratedBlock"],
) -> list[GeneratedArtifact]:
    artifacts: list[GeneratedArtifact] = []
    for index, block in enumerate(blocks):
        body = block.body or (block.interaction.prompt if block.interaction else "")
        accessibility = ArtifactAccessibility(
            alt_text=block.title or None,
            text_equivalent=body or block.title or None,
        )
        if block.kind in {"narrative", "story_scene"}:
            artifacts.append(
                GeneratedNarrativeArtifact(
                    artifact_id=f"narrative-{index}",
                    sequence_index=index,
                    role=block.kind,
                    title=block.title,
                    text=body,
                    accessibility=accessibility,
                    provenance=ArtifactProvenance(
                        modality="narrative",
                        plugin_id="narrative",
                        source_block_kind=block.kind,
                    ),
                )
            )
            continue
        if block.kind in {"diagram", "visual_representation"}:
            svg = body if body.strip().startswith("<svg") else None
            aria_label = _svg_aria_label(svg)
            artifacts.append(
                GeneratedDiagramArtifact(
                    artifact_id=f"diagram-{index}",
                    sequence_index=index,
                    title=block.title,
                    svg=svg,
                    caption=None if svg else body,
                    accessibility=accessibility.model_copy(
                        update={
                            "alt_text": aria_label or block.title or body,
                            "text_equivalent": aria_label or block.title or body,
                        }
                    ),
                    provenance=ArtifactProvenance(
                        modality="diagram",
                        plugin_id="diagram",
                        source_block_kind=block.kind,
                    ),
                )
            )
            continue
        artifacts.append(
            GeneratedTextArtifact(
                artifact_id=f"text-{index}",
                sequence_index=index,
                role=block.kind,
                title=block.title,
                text=body,
                accessibility=accessibility,
                provenance=ArtifactProvenance(
                    modality="text",
                    plugin_id="text",
                    source_block_kind=block.kind,
                ),
            )
        )
    return artifacts


class MisconceptionSignal(BaseModel):
    kc_id: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    source: str = "heuristic"
    misconception_id: str | None = None
    recommended_kc_ids: list[str] = Field(default_factory=list)
    remediation_hint: str | None = None
    evidence_terms: list[str] = Field(default_factory=list)
    recurrence_count: int = Field(default=0, ge=0)
    recurrence_session_count: int = Field(default=0, ge=0)
    recurrence_signal: str = "none"
    last_seen_at: datetime | None = None
    primary_for_kc: bool = False
    disambiguation_score: float = Field(default=0.0, ge=0.0)
    disambiguation_rationale: str | None = None


class TargetKcGenerationHint(BaseModel):
    kc_id: str
    kc_name: str
    concept_family: str | None = None
    taxonomy_cluster_id: str | None = None
    nearby_kc_names: list[str] = Field(default_factory=list)
    misconception_ids: list[str] = Field(default_factory=list)
    misconception_labels: list[str] = Field(default_factory=list)
    misconception_descriptions: list[str] = Field(default_factory=list)
    remediation_hints: list[str] = Field(default_factory=list)


class ModerationMatch(BaseModel):
    category: str
    matched_terms: list[str] = Field(default_factory=list)
    reason: str
    severity: str = "block"


class ModerationResult(BaseModel):
    status: str = "clear"
    stage: str = "none"
    severity: str = "none"
    decision: str = "allow"
    categories: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    matches: list[ModerationMatch] = Field(default_factory=list)
    blocked: bool = False
    request_blocked: bool = False
    response_rewritten: bool = False
    fallback_applied: bool = False
    fallback_kind: str | None = None
    stream_action: str = "none"
    provider_invoked: bool = False
    stream_buffered: bool = False
    original_block_count: int = Field(default=0, ge=0)
    replacement_block_count: int = Field(default=0, ge=0)
    audit_message: str | None = None
    llm_verdict: str = "skipped"
    llm_categories: list[str] = Field(default_factory=list)
    llm_reason: str | None = None


class GenerationMetadata(BaseModel):
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    validation_passed: bool = True
    validation_issue_count: int = Field(default=0, ge=0)
    grounding_count: int = Field(default=0, ge=0)
    provider_name: str | None = None
    model_used: str | None = None
    prompt_template_name: str | None = None
    prompt_template_version: str | None = None
    prompt_template_variant: str | None = None
    generation_latency_ms: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    cache_hit: bool = False
    verification_status: str = "skipped"
    verification_issue_count: int = Field(default=0, ge=0)
    verification_attempts: int = Field(default=0, ge=0)
    moderation: ModerationResult = Field(default_factory=ModerationResult)


class GenerationWorkflowSummary(BaseModel):
    status: str = "delivered"
    flow_type: str = "lesson"
    learning_session_id: str | None = None
    goal_id: str | None = None
    trajectory_id: str | None = None
    trajectory_node_id: str | None = None
    trajectory_checkpoint_id: str | None = None
    delivered_phase: str = "target"
    delivered_content_type: str | None = None
    progression_action: str = "stay_on_requested_target"
    target_stage: str = "target"
    active_target_kc_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None
    next_step: LearnerFlowNextStep = Field(default_factory=LearnerFlowNextStep)
    continue_action: LearnerContinueAction = Field(
        default_factory=LearnerContinueAction
    )


class GenerationResponse(BaseModel):
    student_id: UUID
    generated_at: datetime = Field(default_factory=utc_now)
    route: AdaptiveRouteDecision
    blocks: list[GeneratedBlock]
    artifacts: list[GeneratedArtifact] = Field(default_factory=list)
    curriculum_context: list[str]
    grounding: list[GroundingReference] = Field(default_factory=list)
    safety_notes: list[str]
    validation_issues: list[str] = Field(default_factory=list)
    generation_id: str | None = None
    generation_metadata: GenerationMetadata | None = None

    @model_validator(mode="after")
    def populate_artifacts_from_blocks(self) -> "GenerationResponse":
        if not self.artifacts:
            self.artifacts = build_generated_artifacts(self.blocks)
        return self


class GeneratedContent(BaseModel):
    generation_id: str
    student_id: UUID
    content_type: str
    request_context: dict[str, object] = Field(default_factory=dict)
    workflow_summary: GenerationWorkflowSummary | None = None
    response: GenerationResponse
    quality: GenerationMetadata
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None


class CurriculumLibraryEntry(BaseModel):
    content_key: CurriculumContentKey
    content: GeneratedContent
    cache_key: str | None = None
    provenance: "CurriculumLibraryProvenance | None" = None
    storage_scope: CurriculumLibraryStorageScope = (
        CurriculumLibraryStorageScope.local_only
    )
    source_generation_id: str | None = None

    @model_validator(mode="after")
    def populate_library_metadata(self) -> "CurriculumLibraryEntry":
        if self.cache_key is None:
            self.cache_key = self.content_key.cache_key()
        if self.source_generation_id is None:
            self.source_generation_id = self.content.generation_id
        if self.provenance is None:
            curriculum_provenance = self.content_key.request.curriculum_provenance
            if curriculum_provenance is None:
                for reference in self.content_key.grounding:
                    if reference.curriculum_provenance is not None:
                        curriculum_provenance = reference.curriculum_provenance
                        break
            self.provenance = CurriculumLibraryProvenance(
                source_generation_id=self.content.generation_id,
                provider_name=self.content.quality.provider_name,
                curriculum_provenance=curriculum_provenance,
                validator_passed=self.content.quality.validation_passed,
                validation_issues=list(self.content.response.validation_issues),
                moderation_status=self.content.quality.moderation.status,
                quality_score=self.content.quality.quality_score,
                modalities=[
                    artifact.provenance.modality
                    for artifact in self.content.response.artifacts
                ],
                artifact_outcome_summary=CurriculumArtifactOutcomeSummary(
                    intent=self.content_key.request.intent.value,
                    content_type=self.content_key.request.content_type.value,
                    delivered_phase=(
                        self.content.workflow_summary.delivered_phase
                        if self.content.workflow_summary is not None
                        else None
                    ),
                    prompt_template_name=self.content.quality.prompt_template_name,
                    prompt_template_variant=self.content.quality.prompt_template_variant,
                    pattern_key=":".join(
                        str(item)
                        for item in [
                            (
                                self.content.workflow_summary.delivered_phase
                                if self.content.workflow_summary is not None
                                else None
                            ),
                            self.content_key.request.intent.value,
                            self.content_key.request.content_type.value,
                            self.content.quality.prompt_template_variant,
                        ]
                        if item
                    )
                    or None,
                ),
            )
        return self


class CurriculumLibraryProvenance(BaseModel):
    source_generation_id: str
    provider_name: str | None = None
    curriculum_provenance: CurriculumVersionReference | None = None
    validator_passed: bool = True
    validation_issues: list[str] = Field(default_factory=list)
    moderation_status: str = "clear"
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    modalities: list[str] = Field(default_factory=list)
    stored_via: str = "cloud_library_client"
    lookup_status: str = "local_only"
    publish_status: str = "local_only"
    degraded_mode: bool = False
    degraded_reason: str | None = None
    remote_endpoint: str | None = None
    outcome_sample_count: int = Field(default=0, ge=0)
    average_outcome_score: float = Field(default=0.5, ge=0.0, le=1.0)
    average_engagement_score: float = Field(default=0.5, ge=0.0, le=1.0)
    average_progress_score: float = Field(default=0.5, ge=0.0, le=1.0)
    historical_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    last_outcome_at: datetime | None = None
    artifact_outcome_summary: "CurriculumArtifactOutcomeSummary | None" = None


class CurriculumArtifactOutcomeSummary(BaseModel):
    evidence_strength: str = "weak"
    sample_count: int = Field(default=0, ge=0)
    average_outcome_score: float = Field(default=0.5, ge=0.0, le=1.0)
    average_engagement_score: float = Field(default=0.5, ge=0.0, le=1.0)
    average_progress_score: float = Field(default=0.5, ge=0.0, le=1.0)
    historical_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    intent: str | None = None
    content_type: str | None = None
    delivered_phase: str | None = None
    prompt_template_name: str | None = None
    prompt_template_variant: str | None = None
    pattern_key: str | None = None
    last_outcome_at: datetime | None = None


class CurriculumLibraryCandidateRanking(BaseModel):
    cache_key: str
    source_generation_id: str | None = None
    selected: bool = False
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)
    outcome_sample_count: int = Field(default=0, ge=0)
    score_components: list[AdaptiveScoreComponent] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class CurriculumLibrarySelectionTrace(BaseModel):
    selection_key: str
    requested_modality: str | None = None
    selected_cache_key: str | None = None
    candidates: list[CurriculumLibraryCandidateRanking] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class CurriculumLibraryPrivacyAuditEntry(BaseModel):
    cache_key: str
    storage_scope: CurriculumLibraryStorageScope
    source_generation_id: str | None = None
    content_student_id: UUID
    response_student_id: UUID
    request_context_keys: list[str] = Field(default_factory=list)
    curriculum_key_fields: list[str] = Field(default_factory=list)
    provenance_status: str | None = None
    forbidden_field_hits: list[str] = Field(default_factory=list)


class CurriculumLibraryPrivacyAudit(BaseModel):
    entry_count: int = Field(default=0, ge=0)
    forbidden_field_hits: list[str] = Field(default_factory=list)
    entries: list[CurriculumLibraryPrivacyAuditEntry] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class GenerationStreamEvent(BaseModel):
    event: str
    student_id: UUID
    route: AdaptiveRouteDecision | None = None
    grounding: list[GroundingReference] = Field(default_factory=list)
    chunk: GeneratedBlockChunk | None = None
    moderation: ModerationResult | None = None
    validation_issues: list[str] = Field(default_factory=list)
    workflow_summary: GenerationWorkflowSummary | None = None
    response: GenerationResponse | None = None


class RemedialTriggerRequest(BaseModel):
    student_id: UUID
    target_kc_id: str
    misconception_description: str
    learner_prompt: str | None = None
    curriculum_context: list[str] = Field(default_factory=list)


class ContentWarmRequest(BaseModel):
    requests: list[GenerationRequest] = Field(default_factory=list)


class ContentWarmResult(BaseModel):
    total_requests: int = Field(default=0, ge=0)
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)
    generation_ids: list[str] = Field(default_factory=list)
    warmed_at: datetime = Field(default_factory=utc_now)


class PredictiveWarmTask(BaseModel):
    task_id: str
    student_id: UUID
    request: GenerationRequest
    request_fingerprint: str
    status: str = "pending"
    priority_score: float = Field(default=0.0, ge=0.0)
    priority_class: str = "routine"
    attempt_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    claim_owner: str | None = None
    claim_mode: str | None = None
    claim_reason: str | None = None
    claimed_at: datetime | None = None
    stale_recovered: bool = False


class PredictiveWarmProcessRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class PredictiveWarmProcessResult(BaseModel):
    attempted_tasks: int = Field(default=0, ge=0)
    claimed_tasks: int = Field(default=0, ge=0)
    supplemental_tasks: int = Field(default=0, ge=0)
    worker_id: str | None = None
    execution_mode: str = "idle"
    targeted_tasks: int = Field(default=0, ge=0)
    autonomous_tasks: int = Field(default=0, ge=0)
    stale_recovered_tasks: int = Field(default=0, ge=0)
    completed_tasks: int = Field(default=0, ge=0)
    failed_tasks: int = Field(default=0, ge=0)
    retried_tasks: int = Field(default=0, ge=0)
    requeued_tasks: int = Field(default=0, ge=0)
    expired_tasks: int = Field(default=0, ge=0)
    deferred_tasks: int = Field(default=0, ge=0)
    dropped_tasks: int = Field(default=0, ge=0)
    skipped_tasks: int = Field(default=0, ge=0)
    pending_tasks: int = Field(default=0, ge=0)
    eligible_tasks: int = Field(default=0, ge=0)
    blocked_tasks: int = Field(default=0, ge=0)
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)
    generation_ids: list[str] = Field(default_factory=list)
    claim_details: list["PredictiveWarmClaimDetail"] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=utc_now)


class PredictiveWarmSweepResult(BaseModel):
    requeued_tasks: int = Field(default=0, ge=0)
    expired_tasks: int = Field(default=0, ge=0)
    requeued_task_ids: list[str] = Field(default_factory=list)


class PredictiveWarmClaimDetail(BaseModel):
    task_id: str
    requested_content_type: str | None = None
    priority_class: str = "routine"
    claim_owner: str | None = None
    claim_mode: str | None = None
    claim_reason: str | None = None
    source_generation_id: str | None = None
    stale_recovered: bool = False
    wait_seconds: int = Field(default=0, ge=0)


PredictiveWarmProcessResult.model_rebuild()
