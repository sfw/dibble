from __future__ import annotations

from dibble.models.generation import GeneratedBlock, GroundingReference
from dibble.services.validation.rules import (
    AccessibilityRule,
    CurriculumAlignmentRule,
    GradeLevelReadabilityRule,
    GroundingRule,
    InstructionGroundingCoverageRule,
    InstructionBlockRule,
    LengthGuardrailRule,
    MathSanityRule,
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
            SafetyLanguageRule(),
            MathSanityRule(),
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
