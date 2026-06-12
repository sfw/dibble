#!/usr/bin/env python3
"""Hard-delete a learner's data across every table.

Honors a withdrawal request from the pilot consent document: removes the
learner profile, observations, sessions, generated content, audit events,
mastery snapshots, placement sessions, login account, and section
memberships. Irreversible — export first if the family wants their data:

    GET /api/admin/learners/{id}/export

Usage:
    uv run python scripts/hard_delete_learner.py <student_id> [--db dibble.db] [--yes]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dibble.services.data_rights import LearnerDataRightsService  # noqa: E402
from dibble.services.sqlite_connection import create_connection  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student_id", help="Learner student_id (UUID)")
    parser.add_argument("--db", default="dibble.db", help="SQLite database path")
    parser.add_argument(
        "--yes", action="store_true", help="Skip the interactive confirmation"
    )
    args = parser.parse_args()

    student_id = UUID(args.student_id)
    if not Path(args.db).exists():
        print(f"Database not found: {args.db}", file=sys.stderr)
        return 1

    if not args.yes:
        answer = input(
            f"Hard-delete ALL data for learner {student_id} in {args.db}? "
            f"This cannot be undone. Type 'delete' to confirm: "
        )
        if answer.strip().lower() != "delete":
            print("Aborted.")
            return 1

    service = LearnerDataRightsService(connection=create_connection(args.db))
    report = service.hard_delete(student_id=student_id)
    if not report.deleted_rows_by_table:
        print(f"No data found for learner {student_id}.")
        return 0
    for table, count in sorted(report.deleted_rows_by_table.items()):
        print(f"  {table}: {count} row(s) deleted")
    if report.deleted_user_ids:
        print(f"  login accounts removed: {', '.join(report.deleted_user_ids)}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
