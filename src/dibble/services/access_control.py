from __future__ import annotations

from collections.abc import Iterable


ROLE_RANKS = {
    "viewer": 1,
    "editor": 2,
    "admin": 3,
}


def allows_role(role: str, allowed_roles: Iterable[str]) -> bool:
    subject_rank = ROLE_RANKS.get(role, 0)
    return any(subject_rank >= ROLE_RANKS.get(candidate, 0) for candidate in allowed_roles)
