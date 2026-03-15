from __future__ import annotations

import json


def parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for record in body.strip().split("\n\n"):
        if not record.strip():
            continue
        event_name = ""
        data = ""
        for line in record.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            if line.startswith("data: "):
                data = line.removeprefix("data: ")
        events.append({"event": event_name, "data": json.loads(data)})
    return events
