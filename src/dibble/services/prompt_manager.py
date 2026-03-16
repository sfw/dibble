from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from dibble.config import Settings
from dibble.models.generation import GenerationModeCalibration, RequestedContentType
from dibble.services.generation_prompt_selector import GenerationPromptSelector
from dibble.services.socratic_prompt_selector import SocraticPromptSelector


@dataclass(frozen=True, slots=True)
class PromptSelection:
    template_name: str
    template_version: str
    template_variant: str
    system_directives: str
    user_directives: str


@dataclass(slots=True)
class PromptManager:
    library_version: str = "1.0"
    experiment_enabled: bool = False
    adaptive_selection_enabled: bool = False
    variant_override: str | None = None
    generation_prompt_selector: GenerationPromptSelector | None = None
    socratic_prompt_selector: SocraticPromptSelector | None = None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        generation_prompt_selector: GenerationPromptSelector | None = None,
        socratic_prompt_selector: SocraticPromptSelector | None = None,
    ) -> "PromptManager":
        return cls(
            library_version=settings.prompt_library_version,
            experiment_enabled=settings.prompt_experiment_enabled,
            adaptive_selection_enabled=settings.prompt_adaptive_selection_enabled,
            variant_override=settings.prompt_variant_override,
            generation_prompt_selector=generation_prompt_selector,
            socratic_prompt_selector=socratic_prompt_selector,
        )

    def select(
        self,
        *,
        student_id: UUID,
        content_type: RequestedContentType,
        mode_calibration: GenerationModeCalibration | None = None,
    ) -> PromptSelection:
        variant = self.variant_override or self._variant_for(student_id=student_id, content_type=content_type)
        if (
            self.adaptive_selection_enabled
            and content_type in {
                RequestedContentType.micro_explanation,
                RequestedContentType.worked_example,
                RequestedContentType.practice_problem,
            }
            and self.generation_prompt_selector is not None
        ):
            variant = self.generation_prompt_selector.select_variant(
                content_type=content_type,
                fallback_variant=variant,
                mode_calibration=mode_calibration,
            )
        if (
            self.adaptive_selection_enabled
            and content_type == RequestedContentType.assessment_probe
            and self.socratic_prompt_selector is not None
        ):
            variant = self.socratic_prompt_selector.select_variant(fallback_variant=variant)
        template_name = f"{content_type.value}.{variant}"
        return PromptSelection(
            template_name=template_name,
            template_version=self.library_version,
            template_variant=variant,
            system_directives=self._system_directives(content_type=content_type, variant=variant),
            user_directives=self._user_directives(content_type=content_type, variant=variant),
        )

    def _variant_for(self, *, student_id: UUID, content_type: RequestedContentType) -> str:
        if not self.experiment_enabled:
            return "baseline"
        variants = self._variants_for(content_type)
        if len(variants) == 1:
            return "baseline"
        key = f"{student_id}:{content_type.value}:{self.library_version}"
        bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % len(variants)
        return variants[bucket]

    def _variants_for(self, content_type: RequestedContentType) -> tuple[str, ...]:
        variant_map = {
            RequestedContentType.micro_explanation: ("baseline", "guided_reflection"),
            RequestedContentType.worked_example: ("baseline", "guided_reflection"),
            RequestedContentType.practice_problem: ("baseline", "guided_reflection"),
            RequestedContentType.assessment_probe: ("baseline", "causal_probe"),
        }
        return variant_map.get(content_type, ("baseline",))

    def _system_directives(self, *, content_type: RequestedContentType, variant: str) -> str:
        if content_type == RequestedContentType.worked_example:
            return (
                "Include at least one worked_example block before the instruction block. "
                "Make the modeled reasoning explicit and concise, and keep the fade plan aligned to named step roles rather than unlabeled step counts."
            )
        if content_type == RequestedContentType.practice_problem:
            return (
                "Include at least one practice block, keep the answer-check guidance lightweight, and make any distractor contrast purposeful rather than random."
            )
        if content_type == RequestedContentType.assessment_probe:
            if variant == "causal_probe":
                return (
                    "Ask for causal reasoning, justification, or a counterexample rather than simple recall. "
                    "Keep the probe short and discussion-ready."
                )
            return "Ask one concise reasoning probe that surfaces the learner's current understanding."
        if variant == "guided_reflection":
            return (
                "End the instructional sequence with a brief reflection or check-for-understanding prompt."
            )
        return "Keep the structure simple, grounded, and ready for student delivery."

    def _user_directives(self, *, content_type: RequestedContentType, variant: str) -> str:
        if content_type == RequestedContentType.worked_example:
            return "Show the learner how and why each visible step works, then clearly name the remaining learner-owned step."
        if content_type == RequestedContentType.practice_problem:
            return "Use one concrete problem, one short cue, and distractors that reveal specific reasoning choices rather than superficial traps."
        if content_type == RequestedContentType.assessment_probe:
            if variant == "causal_probe":
                return "Favor why/how wording and nearby contrasts so the learner has to explain reasoning, not just answer."
            return "Use one open-ended question that elicits a short explanation of the learner's thinking."
        if variant == "guided_reflection":
            return "Add one short reflection question that helps the learner explain their reasoning."
        return "Keep the next step actionable and specific."
