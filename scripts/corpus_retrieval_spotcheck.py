#!/usr/bin/env python3
"""Corpus acceptance spot-check: retriever resolution of free-text queries.

Roadmap 1.1 acceptance: the retriever returns the correct resource for 25
hand-written free-text queries spanning the Grades 4-6 band. One query per
learning outcome, phrased the way a parent or learner would say it (not
copied from outcome titles).

Usage:
    uv run python scripts/corpus_retrieval_spotcheck.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dibble.models.corpus import CorpusDocument  # noqa: E402
from dibble.models.generation import (  # noqa: E402
    CurriculumContentRequest,
    RequestedContentType,
)
from dibble.services.outcome_store import SQLiteOutcomeStore  # noqa: E402
from dibble.services.rag_retriever import RAGRetriever  # noqa: E402
from dibble.services.sqlite_connection import create_connection  # noqa: E402
from dibble.storage import ensure_database  # noqa: E402

# (grade, free-text query, expected outcome_id) — one per LO in the corpus.
QUERIES: list[tuple[str, str, str]] = [
    # Grade 4
    ("4", "reading big numbers and writing them in expanded form", "g4-lo-place-value"),
    ("4", "subtraction with borrowing when the top digit is smaller", "g4-lo-add-sub"),
    (
        "4",
        "times tables and multiplying a big number by a single digit",
        "g4-lo-multiplication",
    ),
    ("4", "long division where there is a leftover amount", "g4-lo-division"),
    (
        "4",
        "why one half is the same as two fourths on a number line",
        "g4-lo-fraction-equivalence",
    ),
    (
        "4",
        "adding two fractions that have the same bottom number",
        "g4-lo-fraction-add-sub",
    ),
    (
        "4",
        "writing tenths and hundredths using a decimal point",
        "g4-lo-decimal-notation",
    ),
    (
        "4",
        "the distance around a rectangle versus the space inside it",
        "g4-lo-perimeter-area",
    ),
    # Grade 5
    (
        "5",
        "place value up to a million and multiplying by powers of ten",
        "g5-lo-place-value-millions",
    ),
    (
        "5",
        "multiplying two digit numbers using partial products",
        "g5-lo-multidigit-mult",
    ),
    ("5", "dividing a big number by a two digit divisor", "g5-lo-multidigit-div"),
    (
        "5",
        "order of operations with parentheses and what the equals sign means",
        "g5-lo-expressions-equality",
    ),
    (
        "5",
        "adding fractions with different bottom numbers using a common denominator",
        "g5-lo-fraction-add-unlike",
    ),
    (
        "5",
        "multiplying a fraction by a fraction to take a part of a part",
        "g5-lo-fraction-mult",
    ),
    (
        "5",
        "lining up the decimal point when adding and multiplying decimals",
        "g5-lo-decimal-operations",
    ),
    ("5", "how much space fits inside a box measured in unit cubes", "g5-lo-volume"),
    (
        "5",
        "plotting ordered pairs on a grid going across then up",
        "g5-lo-coordinate-plane",
    ),
    # Grade 6
    ("6", "scaling a recipe so the mixture tastes the same", "g6-lo-ratio-concepts"),
    (
        "6",
        "kilometres per hour as a rate and finding a percent of a number",
        "g6-lo-unit-rate-percent",
    ),
    (
        "6",
        "how many half pieces fit when you divide by a fraction",
        "g6-lo-fraction-division",
    ),
    (
        "6",
        "temperatures below zero and which negative number is smaller",
        "g6-lo-negative-numbers",
    ),
    (
        "6",
        "writing an expression with a letter standing for a number",
        "g6-lo-expressions",
    ),
    (
        "6",
        "solving for x by doing the same thing to both sides",
        "g6-lo-one-step-equations",
    ),
    (
        "6",
        "the area of a triangle as half of a parallelogram",
        "g6-lo-area-decomposition",
    ),
    (
        "6",
        "finding the mean by sharing equally and the median middle value",
        "g6-lo-data-distributions",
    ),
]


def main() -> int:
    corpus_dir = Path(__file__).resolve().parent.parent / "data" / "curriculum"
    db_path = "/tmp/dibble-corpus-spotcheck.db"
    Path(db_path).unlink(missing_ok=True)
    ensure_database(db_path)
    conn = create_connection(db_path)
    outcome_store = SQLiteOutcomeStore(conn)
    for path in sorted(corpus_dir.glob("*.json")):
        document = CorpusDocument.model_validate(json.loads(path.read_text()))
        for outcome in document.outcomes:
            outcome_store.upsert(outcome)

    retriever = RAGRetriever(outcome_store)
    top1_hits = 0
    top3_hits = 0
    failures: list[str] = []
    for grade, query, expected in QUERIES:
        request = CurriculumContentRequest(
            grade_level=grade,
            content_type=RequestedContentType.micro_explanation,
            curriculum_context=[query],
        )
        results = retriever.retrieve(request, limit=3)
        got = [item.outcome_id for item in results]
        if got and got[0] == expected:
            top1_hits += 1
            top3_hits += 1
            print(f"  PASS  [{grade}] {query!r} -> {got[0]}")
        elif expected in got:
            top3_hits += 1
            failures.append(
                f"top3-only [{grade}] {query!r}: expected {expected}, got {got}"
            )
            print(f"  WARN  [{grade}] {query!r} -> {got} (expected {expected} at top)")
        else:
            failures.append(
                f"miss      [{grade}] {query!r}: expected {expected}, got {got}"
            )
            print(f"  FAIL  [{grade}] {query!r} -> {got} (expected {expected})")

    total = len(QUERIES)
    print(f"\ntop-1: {top1_hits}/{total}   top-3: {top3_hits}/{total}")
    if failures:
        print("\nDivergences:")
        for failure in failures:
            print(f"  - {failure}")
    return 0 if top1_hits == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
