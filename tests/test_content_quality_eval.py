from pathlib import Path

from dibble.services.content_quality_eval import ContentQualityEvalHarness


def test_content_quality_eval_harness_passes_shipped_golden_corpus():
    corpus_path = Path("evals/content_quality_golden_corpus.json")
    harness = ContentQualityEvalHarness()

    report = harness.run_corpus(harness.load_corpus(corpus_path))

    assert report.case_count == 5
    assert report.failed_case_count == 0
    assert report.passed is True
    assert {result.case_id for result in report.results} == {
        "fractions_text_micro_explanation_pass",
        "fractions_practice_problem_math_fail",
        "algebra_symbolic_identity_pass",
        "narrative_reflective_pass",
        "diagram_accessibility_fail",
    }
