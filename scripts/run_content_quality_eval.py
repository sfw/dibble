#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dibble.services.content_quality_eval import ContentQualityEvalHarness


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Dibble's offline content-quality golden corpus."
    )
    parser.add_argument(
        "--corpus",
        default="evals/content_quality_golden_corpus.json",
        help="Path to the golden corpus JSON file.",
    )
    parser.add_argument(
        "--json-out",
        help="Optional path to write the machine-readable report.",
    )
    args = parser.parse_args()

    harness = ContentQualityEvalHarness()
    corpus = harness.load_corpus(args.corpus)
    report = harness.run_corpus(corpus)

    print(
        f"Content quality eval: {report.passed_case_count}/{report.case_count} passed"
    )
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        print(f"- [{status}] {result.case_id}: {result.title}")
        for failure in result.failures:
            print(f"  - {failure}")

    if args.json_out:
        Path(args.json_out).write_text(report.model_dump_json(indent=2))

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
