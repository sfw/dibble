from __future__ import annotations

from dibble.models.assignment import Assignment, AssignmentStatus
from dibble.services.assignment_store import SQLiteAssignmentStore
from dibble.services.sqlite_connection import create_connection
from dibble.storage import ensure_database


def _make_store(tmp_path) -> SQLiteAssignmentStore:
    db = str(tmp_path / "test.db")
    ensure_database(db)
    conn = create_connection(db)
    return SQLiteAssignmentStore(conn)


def _make_assignment(**overrides) -> Assignment:
    defaults = {
        "assignment_id": "asgn-1",
        "student_id": "student-1",
        "teacher_id": "teacher-1",
        "section_id": "cls-1",
        "title": "Practice fractions",
    }
    return Assignment(**{**defaults, **overrides})


def test_upsert_and_get(tmp_path):
    store = _make_store(tmp_path)
    assignment = _make_assignment()
    store.upsert(assignment)

    loaded = store.get("asgn-1")
    assert loaded is not None
    assert loaded.assignment_id == "asgn-1"
    assert loaded.title == "Practice fractions"
    assert loaded.status == AssignmentStatus.assigned


def test_get_missing_returns_none(tmp_path):
    store = _make_store(tmp_path)
    assert store.get("nonexistent") is None


def test_upsert_updates_existing(tmp_path):
    store = _make_store(tmp_path)
    assignment = _make_assignment()
    store.upsert(assignment)

    assignment.status = AssignmentStatus.in_progress
    store.upsert(assignment)

    loaded = store.get("asgn-1")
    assert loaded is not None
    assert loaded.status == AssignmentStatus.in_progress


def test_list_for_student(tmp_path):
    store = _make_store(tmp_path)
    store.upsert(_make_assignment(assignment_id="asgn-1", student_id="s1"))
    store.upsert(_make_assignment(assignment_id="asgn-2", student_id="s1"))
    store.upsert(_make_assignment(assignment_id="asgn-3", student_id="s2"))

    s1_assignments = store.list_for_student(student_id="s1")
    assert len(s1_assignments) == 2

    s2_assignments = store.list_for_student(student_id="s2")
    assert len(s2_assignments) == 1


def test_list_for_student_pagination(tmp_path):
    store = _make_store(tmp_path)
    for i in range(5):
        store.upsert(_make_assignment(assignment_id=f"asgn-{i}", student_id="s1"))

    page1 = store.list_for_student(student_id="s1", limit=2, offset=0)
    assert len(page1) == 2

    page2 = store.list_for_student(student_id="s1", limit=2, offset=2)
    assert len(page2) == 2

    page3 = store.list_for_student(student_id="s1", limit=2, offset=4)
    assert len(page3) == 1


def test_count_for_student(tmp_path):
    store = _make_store(tmp_path)
    store.upsert(_make_assignment(assignment_id="asgn-1", student_id="s1"))
    store.upsert(_make_assignment(assignment_id="asgn-2", student_id="s1"))

    assert store.count_for_student(student_id="s1") == 2
    assert store.count_for_student(student_id="s2") == 0


def test_list_for_section(tmp_path):
    store = _make_store(tmp_path)
    store.upsert(_make_assignment(assignment_id="asgn-1", section_id="cls-a"))
    store.upsert(_make_assignment(assignment_id="asgn-2", section_id="cls-a"))
    store.upsert(_make_assignment(assignment_id="asgn-3", section_id="cls-b"))

    cls_a = store.list_for_section(section_id="cls-a")
    assert len(cls_a) == 2


def test_list_for_teacher(tmp_path):
    store = _make_store(tmp_path)
    store.upsert(_make_assignment(assignment_id="asgn-1", teacher_id="t1"))
    store.upsert(_make_assignment(assignment_id="asgn-2", teacher_id="t1"))
    store.upsert(_make_assignment(assignment_id="asgn-3", teacher_id="t2"))

    t1 = store.list_for_teacher(teacher_id="t1")
    assert len(t1) == 2
