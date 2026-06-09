from __future__ import annotations

import json
from pathlib import Path

from dibble.models.content_eval import (
    ContentQualityEvalCase,
    ContentQualityEvalCaseResult,
    ContentQualityEvalCorpus,
    ContentQualityEvalReport,
)
from dibble.services.content_validator import ContentValidator
from dibble.services.llm_prompting import build_generation_prompts


class ContentQualityEvalHarness:
    def __init__(self, *, validator: ContentValidator | None = None) -> None:
        self.validator = validator or ContentValidator()

    def load_corpus(self, path: str | Path) -> ContentQualityEvalCorpus:
        raw = json.loads(Path(path).read_text())
        return ContentQualityEvalCorpus.model_validate(raw)

    def run_case(self, case: ContentQualityEvalCase) -> ContentQualityEvalCaseResult:
        prompts = build_generation_prompts(
            case.request,
            case.route,
            case.grounding,
        )
        validation_issues = self.validator.validate(case.blocks, case.grounding)
        failures: list[str] = []
        expectations = case.expectations

        for substring in expectations.expected_issue_substrings:
            if not any(substring in issue for issue in validation_issues):
                failures.append(f"Missing expected validation issue substring: {substring}")
        for substring in expectations.forbidden_issue_substrings:
            if any(substring in issue for issue in validation_issues):
                failures.append(
                    f"Unexpected validation issue substring present: {substring}"
                )
        for substring in expectations.required_prompt_substrings:
            if substring not in prompts.user_prompt and substring not in prompts.system_prompt:
                failures.append(f"Missing required prompt substring: {substring}")
        for substring in expectations.forbidden_prompt_substrings:
            if substring in prompts.user_prompt or substring in prompts.system_prompt:
                failures.append(f"Forbidden prompt substring present: {substring}")
        if (
            expectations.expected_template_name_prefix is not None
            and not prompts.template_name.startswith(
                expectations.expected_template_name_prefix
            )
        ):
            failures.append(
                "Prompt template name mismatch: expected prefix "
                f"{expectations.expected_template_name_prefix}, got {prompts.template_name}"
            )

        return ContentQualityEvalCaseResult(
            case_id=case.case_id,
            title=case.title,
            passed=not failures,
            validation_issues=validation_issues,
            failures=failures,
            prompt_template_name=prompts.template_name,
            prompt_template_version=prompts.template_version,
            prompt_template_variant=prompts.template_variant,
        )

    def run_corpus(self, corpus: ContentQualityEvalCorpus) -> ContentQualityEvalReport:
        results = [self.run_case(case) for case in corpus.cases]
        passed_count = sum(1 for result in results if result.passed)
        return ContentQualityEvalReport(
            version=corpus.version,
            case_count=len(results),
            passed_case_count=passed_count,
            failed_case_count=len(results) - passed_count,
            results=results,
        )
