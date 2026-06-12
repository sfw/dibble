from __future__ import annotations

import json
from pathlib import Path

import pytest

from dibble.models.corpus import CorpusDocument
from dibble.models.course import CourseUpsert
from dibble.models.curriculum import (
    KnowledgeComponentMisconception,
    KnowledgeComponentUpsert,
    OutcomeUpsert,
    StrandUpsert,
)
from dibble.services.course_store import SQLiteCourseStore
from dibble.services.curriculum_ingestion import (
    CorpusValidationError,
    CurriculumIngestionService,
    validate_corpus,
)
from dibble.services.knowledge_component_store import SQLiteKnowledgeComponentStore
from dibble.services.outcome_store import SQLiteOutcomeStore
from dibble.services.sqlite_connection import create_connection
from dibble.services.strand_store import SQLiteStrandStore
from dibble.storage import ensure_database

LONG_DESCRIPTION = (
    "Students use visual fraction models such as number lines, area models, and "
    "fraction strips to explain why two fractions name the same amount of the same whole."
)


def _document(
    *,
    kcs: list[KnowledgeComponentUpsert] | None = None,
    outcomes: list[OutcomeUpsert] | None = None,
) -> CorpusDocument:
    return CorpusDocument(
        course=CourseUpsert(
            course_id="math-test", title="Test Math", subject="mathematics"
        ),
        strands=[
            StrandUpsert(
                strand_id="s-1",
                course_id="math-test",
                title="Numbers",
                description="Number strand",
            )
        ],
        outcomes=outcomes
        if outcomes is not None
        else [
            OutcomeUpsert(
                outcome_id="lo-1",
                title="Fractions",
                strand_id="s-1",
                grade_level="5",
                subject="mathematics",
                description=LONG_DESCRIPTION,
            )
        ],
        knowledge_components=kcs
        if kcs is not None
        else [
            KnowledgeComponentUpsert(
                kc_id="kc-1",
                name="Equivalent fractions",
                outcome_id="lo-1",
                grade_level="5",
                subject="mathematics",
                tags=["anchor"],
                common_misconceptions=[
                    KnowledgeComponentMisconception(
                        misconception_id="mc-1",
                        label="Adds denominators",
                        description="Adds tops and bottoms separately.",
                    )
                ],
            ),
            KnowledgeComponentUpsert(
                kc_id="kc-2",
                name="Compare fractions",
                outcome_id="lo-1",
                grade_level="5",
                subject="mathematics",
                prerequisite_kc_ids=["kc-1"],
                tags=["anchor"],
                common_misconceptions=[
                    KnowledgeComponentMisconception(
                        misconception_id="mc-2",
                        label="Bigger denominator bigger fraction",
                        description="Whole-number ordering applied to denominators.",
                    )
                ],
            ),
            KnowledgeComponentUpsert(
                kc_id="kc-3",
                name="Order fractions",
                outcome_id="lo-1",
                grade_level="5",
                subject="mathematics",
                prerequisite_kc_ids=["kc-2"],
                tags=["anchor"],
                common_misconceptions=[
                    KnowledgeComponentMisconception(
                        misconception_id="mc-3",
                        label="Orders by numerator only",
                        description="Ignores denominators when ordering.",
                    )
                ],
            ),
        ],
    )


def test_valid_document_passes() -> None:
    report = validate_corpus(_document())

    assert report.ok
    assert report.knowledge_component_count == 3
    assert report.anchor_kc_count == 3
    assert report.misconception_count == 3


def test_orphan_kc_outcome_is_error() -> None:
    document = _document()
    document.knowledge_components[0].outcome_id = "lo-missing"

    report = validate_corpus(document)

    assert not report.ok
    assert any(issue.code == "kc_orphan_outcome" for issue in report.errors)


def test_prerequisite_cycle_is_detected() -> None:
    document = _document()
    document.knowledge_components[0].prerequisite_kc_ids = ["kc-3"]

    report = validate_corpus(document)

    assert not report.ok
    assert any(issue.code == "prerequisite_cycle" for issue in report.errors)


def test_short_description_is_error() -> None:
    document = _document(
        outcomes=[
            OutcomeUpsert(
                outcome_id="lo-1",
                title="Fractions",
                strand_id="s-1",
                grade_level="5",
                subject="mathematics",
                description="Too short.",
            )
        ]
    )

    report = validate_corpus(document)

    assert any(issue.code == "outcome_missing_excerpt" for issue in report.errors)


def test_outcome_without_kcs_is_error() -> None:
    document = _document(kcs=[])

    report = validate_corpus(document)

    assert any(issue.code == "outcome_without_kcs" for issue in report.errors)


def test_missing_misconceptions_is_warning_only() -> None:
    document = _document()
    document.knowledge_components[0].common_misconceptions = []

    report = validate_corpus(document)

    assert report.ok
    assert any(issue.code == "kc_without_misconceptions" for issue in report.warnings)


def test_ingest_is_idempotent(tmp_path) -> None:
    db_path = str(tmp_path / "corpus.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    kc_store = SQLiteKnowledgeComponentStore(conn)
    service = CurriculumIngestionService(
        course_store=SQLiteCourseStore(conn),
        strand_store=SQLiteStrandStore(conn),
        outcome_store=SQLiteOutcomeStore(conn),
        knowledge_component_store=kc_store,
    )
    document = _document()

    first = service.ingest(document)
    second = service.ingest(document)

    assert first.knowledge_components_upserted == 3
    assert second.knowledge_components_upserted == 3
    assert len(kc_store.list()) == 3
    stored = kc_store.get("kc-1")
    assert stored is not None
    assert stored.common_misconceptions[0].misconception_id == "mc-1"


def test_ingest_backfills_outcome_kc_ids(tmp_path) -> None:
    db_path = str(tmp_path / "corpus.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    outcome_store = SQLiteOutcomeStore(conn)
    service = CurriculumIngestionService(
        course_store=SQLiteCourseStore(conn),
        strand_store=SQLiteStrandStore(conn),
        outcome_store=outcome_store,
        knowledge_component_store=SQLiteKnowledgeComponentStore(conn),
    )

    service.ingest(_document())

    outcome = outcome_store.get("lo-1")
    assert outcome is not None
    assert set(outcome.knowledge_component_ids) == {"kc-1", "kc-2", "kc-3"}


def test_ingest_rejects_invalid_document(tmp_path) -> None:
    db_path = str(tmp_path / "corpus.db")
    ensure_database(db_path)
    conn = create_connection(db_path)
    service = CurriculumIngestionService(
        course_store=SQLiteCourseStore(conn),
        strand_store=SQLiteStrandStore(conn),
        outcome_store=SQLiteOutcomeStore(conn),
        knowledge_component_store=SQLiteKnowledgeComponentStore(conn),
    )
    document = _document()
    document.knowledge_components[0].outcome_id = "lo-missing"

    with pytest.raises(CorpusValidationError):
        service.ingest(document)


def test_starter_corpus_files_are_valid() -> None:
    corpus_dir = Path(__file__).resolve().parent.parent / "data" / "curriculum"
    documents = [
        CorpusDocument.model_validate(json.loads(path.read_text()))
        for path in sorted(corpus_dir.glob("*.json"))
    ]

    assert len(documents) == 3
    all_kc_ids = {
        kc.kc_id for document in documents for kc in document.knowledge_components
    }
    for document in documents:
        report = validate_corpus(document)
        assert report.ok, [issue.message for issue in report.errors]
        assert report.anchor_kc_count >= 3
        for kc in document.knowledge_components:
            for prerequisite_id in kc.prerequisite_kc_ids:
                assert prerequisite_id in all_kc_ids, (
                    f"{kc.kc_id} prerequisite {prerequisite_id} unresolved"
                )
