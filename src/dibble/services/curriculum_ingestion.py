"""Curriculum corpus ingestion: validate then idempotently load.

The pipeline is corpus-as-data: structured JSON documents (CorpusDocument)
are validated — orphan KC references, prerequisite cycles, outcomes without
KCs, missing grounding excerpts, anchor coverage — and then upserted into the
SQLite stores. Re-running on the same document is a no-op beyond refreshing
timestamps, so corpus authoring can iterate throughout the pilot.
(POC roadmap 1.1)
"""

from __future__ import annotations

from dataclasses import dataclass

from dibble.models.corpus import (
    ANCHOR_TAG,
    CorpusDocument,
    CorpusIngestionResult,
    CorpusValidationIssue,
    CorpusValidationReport,
)
from dibble.services.protocols import (
    CourseStore,
    KnowledgeComponentStore,
    OutcomeStore,
    StrandStore,
)

# Outcome descriptions are the grounding body text; the retriever extracts
# excerpts from them. Anything shorter than this can't ground generation.
MINIMUM_EXCERPT_CHARS = 80
MINIMUM_ANCHOR_KCS = 3


def validate_corpus(document: CorpusDocument) -> CorpusValidationReport:
    issues: list[CorpusValidationIssue] = []
    strand_ids = {strand.strand_id for strand in document.strands}
    outcome_ids = {outcome.outcome_id for outcome in document.outcomes}
    kc_ids = {kc.kc_id for kc in document.knowledge_components}
    kcs_by_outcome: dict[str, list[str]] = {}
    for kc in document.knowledge_components:
        kcs_by_outcome.setdefault(kc.outcome_id, []).append(kc.kc_id)

    def error(code: str, message: str) -> None:
        issues.append(
            CorpusValidationIssue(severity="error", code=code, message=message)
        )

    def warning(code: str, message: str) -> None:
        issues.append(
            CorpusValidationIssue(severity="warning", code=code, message=message)
        )

    for strand in document.strands:
        if strand.course_id != document.course.course_id:
            error(
                "strand_course_mismatch",
                f"Strand {strand.strand_id} references course {strand.course_id}, "
                f"not {document.course.course_id}.",
            )

    for outcome in document.outcomes:
        if outcome.strand_id not in strand_ids:
            error(
                "outcome_orphan_strand",
                f"Outcome {outcome.outcome_id} references unknown strand "
                f"{outcome.strand_id}.",
            )
        if len(outcome.description.strip()) < MINIMUM_EXCERPT_CHARS:
            error(
                "outcome_missing_excerpt",
                f"Outcome {outcome.outcome_id} has a description shorter than "
                f"{MINIMUM_EXCERPT_CHARS} characters; the grounding pipeline "
                f"needs body text to extract excerpts.",
            )
        if not kcs_by_outcome.get(outcome.outcome_id):
            error(
                "outcome_without_kcs",
                f"Outcome {outcome.outcome_id} has no knowledge components.",
            )
        for kc_id in outcome.knowledge_component_ids:
            if kc_id not in kc_ids:
                error(
                    "outcome_unknown_kc",
                    f"Outcome {outcome.outcome_id} lists unknown KC {kc_id}.",
                )

    misconception_count = 0
    anchor_count = 0
    for kc in document.knowledge_components:
        if kc.outcome_id not in outcome_ids:
            error(
                "kc_orphan_outcome",
                f"KC {kc.kc_id} references unknown outcome {kc.outcome_id}.",
            )
        for prerequisite_id in kc.prerequisite_kc_ids:
            if prerequisite_id == kc.kc_id:
                error(
                    "kc_self_prerequisite",
                    f"KC {kc.kc_id} lists itself as a prerequisite.",
                )
            elif prerequisite_id not in kc_ids:
                warning(
                    "kc_external_prerequisite",
                    f"KC {kc.kc_id} prerequisite {prerequisite_id} is not in this "
                    f"document (acceptable only if loaded by another corpus).",
                )
        for nearby_id in kc.nearby_kc_ids:
            if nearby_id not in kc_ids:
                warning(
                    "kc_unknown_nearby",
                    f"KC {kc.kc_id} nearby KC {nearby_id} is not in this document.",
                )
        if ANCHOR_TAG in kc.tags:
            anchor_count += 1
        misconception_count += len(kc.common_misconceptions)
        if not kc.common_misconceptions:
            warning(
                "kc_without_misconceptions",
                f"KC {kc.kc_id} has no misconception catalog; the misconception "
                f"detector and distractor generation are inert for it.",
            )
        seen_misconception_ids: set[str] = set()
        for misconception in kc.common_misconceptions:
            if misconception.misconception_id in seen_misconception_ids:
                error(
                    "duplicate_misconception_id",
                    f"KC {kc.kc_id} repeats misconception id "
                    f"{misconception.misconception_id}.",
                )
            seen_misconception_ids.add(misconception.misconception_id)

    cycle = _find_prerequisite_cycle(document)
    if cycle:
        error(
            "prerequisite_cycle",
            "Prerequisite graph contains a cycle: " + " -> ".join(cycle),
        )

    if anchor_count < MINIMUM_ANCHOR_KCS:
        warning(
            "insufficient_anchor_kcs",
            f"Only {anchor_count} KC(s) tagged '{ANCHOR_TAG}'; placement needs "
            f"at least {MINIMUM_ANCHOR_KCS} anchor KCs per band.",
        )

    duplicate_kc_ids = _duplicates([kc.kc_id for kc in document.knowledge_components])
    for kc_id in duplicate_kc_ids:
        error("duplicate_kc_id", f"KC id {kc_id} appears more than once.")
    duplicate_outcome_ids = _duplicates(
        [outcome.outcome_id for outcome in document.outcomes]
    )
    for outcome_id in duplicate_outcome_ids:
        error(
            "duplicate_outcome_id", f"Outcome id {outcome_id} appears more than once."
        )

    return CorpusValidationReport(
        issues=issues,
        outcome_count=len(document.outcomes),
        knowledge_component_count=len(document.knowledge_components),
        anchor_kc_count=anchor_count,
        misconception_count=misconception_count,
    )


def _find_prerequisite_cycle(document: CorpusDocument) -> list[str] | None:
    graph = {
        kc.kc_id: [
            prerequisite
            for prerequisite in kc.prerequisite_kc_ids
            if prerequisite != kc.kc_id
        ]
        for kc in document.knowledge_components
    }
    WHITE, GRAY, BLACK = 0, 1, 2
    colors = dict.fromkeys(graph, WHITE)
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        colors[node] = GRAY
        stack.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in graph:
                continue
            if colors[neighbor] == GRAY:
                cycle_start = stack.index(neighbor)
                return [*stack[cycle_start:], neighbor]
            if colors[neighbor] == WHITE:
                found = visit(neighbor)
                if found:
                    return found
        colors[node] = BLACK
        stack.pop()
        return None

    for node in graph:
        if colors[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicated: list[str] = []
    for value in values:
        if value in seen and value not in duplicated:
            duplicated.append(value)
        seen.add(value)
    return duplicated


class CorpusValidationError(ValueError):
    def __init__(self, report: CorpusValidationReport) -> None:
        self.report = report
        super().__init__(
            "Corpus validation failed: "
            + "; ".join(issue.message for issue in report.errors)
        )


@dataclass(slots=True)
class CurriculumIngestionService:
    course_store: CourseStore
    strand_store: StrandStore
    outcome_store: OutcomeStore
    knowledge_component_store: KnowledgeComponentStore

    def ingest(
        self, document: CorpusDocument, *, require_valid: bool = True
    ) -> CorpusIngestionResult:
        report = validate_corpus(document)
        if require_valid and not report.ok:
            raise CorpusValidationError(report)

        self.course_store.upsert(document.course)
        for strand in document.strands:
            self.strand_store.upsert(strand)
        # Outcomes must know their KC ids even when the author leaves
        # knowledge_component_ids empty in the source document.
        kcs_by_outcome: dict[str, list[str]] = {}
        for kc in document.knowledge_components:
            kcs_by_outcome.setdefault(kc.outcome_id, []).append(kc.kc_id)
        for outcome in document.outcomes:
            resolved = outcome
            if not outcome.knowledge_component_ids:
                resolved = outcome.model_copy(
                    update={
                        "knowledge_component_ids": kcs_by_outcome.get(
                            outcome.outcome_id, []
                        )
                    }
                )
            self.outcome_store.upsert(resolved)
        for kc in document.knowledge_components:
            self.knowledge_component_store.upsert(kc)

        return CorpusIngestionResult(
            course_id=document.course.course_id,
            strands_upserted=len(document.strands),
            outcomes_upserted=len(document.outcomes),
            knowledge_components_upserted=len(document.knowledge_components),
        )
