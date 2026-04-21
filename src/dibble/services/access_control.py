from __future__ import annotations

from collections.abc import Iterable


ROLE_IMPLICATIONS: dict[str, set[str]] = {
    "learner": {"learner", "viewer"},
    "viewer": {"viewer"},
    "teacher": {"teacher", "editor", "learner", "viewer"},
    "editor": {"editor", "viewer", "teacher", "learner"},
    "parent": {"parent", "viewer"},
    "household_admin": {"household_admin", "parent", "viewer"},
    "admin": {
        "admin",
        "editor",
        "viewer",
        "teacher",
        "learner",
        "parent",
        "household_admin",
    },
}


def allows_role(role: str, allowed_roles: Iterable[str]) -> bool:
    implied_roles = ROLE_IMPLICATIONS.get(role, {role})
    return any(candidate in implied_roles for candidate in allowed_roles)
