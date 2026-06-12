from __future__ import annotations

from dibble.models.generation import GeneratedBlock, GroundingReference
from dibble.services.validation.rules import (
    AccessibilityRule,
    CurriculumAlignmentRule,
    DiagramAccessibilityRule,
    GradeLevelReadabilityRule,
    GroundingRule,
    InstructionGroundingCoverageRule,
    InstructionBlockRule,
    LatexWellFormednessRule,
    LengthGuardrailRule,
    MathSanityRule,
    ModalityCompositionRule,
    NarrativeCoherenceRule,
    SafetyLanguageRule,
    ValidationRule,
)


class ContentValidator:
    def __init__(self, rules: list[ValidationRule] | None = None) -> None:
        self.rules = rules or [
            GroundingRule(),
            InstructionBlockRule(),
            LengthGuardrailRule(),
            CurriculumAlignmentRule(),
            InstructionGroundingCoverageRule(),
            GradeLevelReadabilityRule(),
            AccessibilityRule(),
            NarrativeCoherenceRule(),
            DiagramAccessibilityRule(),
            ModalityCompositionRule(),
            SafetyLanguageRule(),
            MathSanityRule(),
            LatexWellFormednessRule(),
        ]

    def validate(
        self,
        blocks: list[GeneratedBlock],
        grounding: list[GroundingReference],
    ) -> list[str]:
        issues: list[str] = []

        for rule in self.rules:
            issues.extend(rule.validate(blocks, grounding))

        return issues
