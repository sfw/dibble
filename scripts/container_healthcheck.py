from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any

DEFAULT_READINESS_URL = "http://127.0.0.1:8000/ready"
DEFAULT_ALLOWED_STATUSES = frozenset({"ready"})


def readiness_status(payload: dict[str, Any]) -> str | None:
    status = payload.get("status")
    return status if isinstance(status, str) else None


def readiness_is_acceptable(
    payload: dict[str, Any],
    *,
    allowed_statuses: set[str] | frozenset[str] = DEFAULT_ALLOWED_STATUSES,
) -> bool:
    return readiness_status(payload) in allowed_statuses


def _allowed_statuses_from_env() -> frozenset[str]:
    raw = os.getenv("DIBBLE_HEALTHCHECK_ALLOWED_STATUSES")
    if raw is None:
        return DEFAULT_ALLOWED_STATUSES
    parsed = frozenset(item.strip() for item in raw.split(",") if item.strip())
    return parsed or DEFAULT_ALLOWED_STATUSES


def main() -> int:
    url = os.getenv("DIBBLE_HEALTHCHECK_URL", DEFAULT_READINESS_URL)
    allowed_statuses = _allowed_statuses_from_env()
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status != 200:
                print(f"readiness HTTP status was {response.status}", file=sys.stderr)
                return 1
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"readiness probe failed: {exc}", file=sys.stderr)
        return 1

    status = readiness_status(payload)
    if status not in allowed_statuses:
        allowed = ", ".join(sorted(allowed_statuses))
        print(
            f"readiness status {status!r} is not acceptable; expected one of: {allowed}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
