#!/usr/bin/env python3
"""Ingest a curriculum corpus document into the Dibble database.

The corpus is structured JSON (see src/dibble/models/corpus.py and
data/curriculum/*.json). The pipeline validates the document — orphan KCs,
prerequisite cycles, outcomes without grounding text, anchor coverage — and
then idempotently upserts it. Re-running on the same file is safe.

Usage:
    uv run python scripts/ingest_curriculum.py data/curriculum/grade5_math.json
    uv run python scripts/ingest_curriculum.py data/curriculum/*.json --db dibble.db
    uv run python scripts/ingest_curriculum.py data/curriculum/*.json --validate-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dibble.models.corpus import CorpusDocument  # noqa: E402
from dibble.services.course_store import SQLiteCourseStore  # noqa: E402
from dibble.services.curriculum_ingestion import (  # noqa: E402
    CurriculumIngestionService,
    validate_corpus,
)
from dibble.services.knowledge_component_store import (  # noqa: E402
    SQLiteKnowledgeComponentStore,
)
from dibble.services.outcome_store import SQLiteOutcomeStore  # noqa: E402
from dibble.services.sqlite_connection import create_connection  # noqa: E402
from dibble.services.strand_store import SQLiteStrandStore  # noqa: E402
from dibble.storage import ensure_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_files", nargs="+", help="Corpus JSON file(s)")
    parser.add_argument("--db", default="dibble.db", help="SQLite database path")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run the validation pass without writing anything",
    )
    args = parser.parse_args()

    documents: list[tuple[str, CorpusDocument]] = []
    for path in args.corpus_files:
        raw = json.loads(Path(path).read_text())
        documents.append((path, CorpusDocument.model_validate(raw)))

    failed = False
    for path, document in documents:
        report = validate_corpus(document)
        print(f"\n=== {path} ===")
        print(
            f"  outcomes={report.outcome_count} "
            f"kcs={report.knowledge_component_count} "
            f"anchors={report.anchor_kc_count} "
            f"misconceptions={report.misconception_count}"
        )
        for issue in report.issues:
            print(f"  [{issue.severity}] {issue.code}: {issue.message}")
        if not report.ok:
            failed = True

    # Cross-document check: every external prerequisite must resolve somewhere
    # in the full set being ingested.
    all_kc_ids = {
        kc.kc_id for _, document in documents for kc in document.knowledge_components
    }
    for path, document in documents:
        for kc in document.knowledge_components:
            for prerequisite_id in kc.prerequisite_kc_ids:
                if prerequisite_id not in all_kc_ids:
                    print(
                        f"[error] unresolved_prerequisite: {path}: KC {kc.kc_id} "
                        f"prerequisite {prerequisite_id} not found in any document."
                    )
                    failed = True

    if failed:
        print("\nValidation failed; nothing was written.")
        return 1
    if args.validate_only:
        print("\nValidation passed.")
        return 0

    ensure_database(args.db)
    conn = create_connection(args.db)
    service = CurriculumIngestionService(
        course_store=SQLiteCourseStore(conn),
        strand_store=SQLiteStrandStore(conn),
        outcome_store=SQLiteOutcomeStore(conn),
        knowledge_component_store=SQLiteKnowledgeComponentStore(conn),
    )
    for path, document in documents:
        result = service.ingest(document)
        print(
            f"Ingested {result.course_id}: "
            f"{result.strands_upserted} strands, "
            f"{result.outcomes_upserted} outcomes, "
            f"{result.knowledge_components_upserted} KCs"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
