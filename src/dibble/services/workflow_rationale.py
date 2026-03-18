from __future__ import annotations


def combine_rationales(*parts: str | None) -> str | None:
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        normalized = _normalize_rationale(part)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    if not ordered:
        return None
    return " ".join(ordered)


def append_evidence_snapshot(rationale: str | None, *, fragments: list[str]) -> str | None:
    base = combine_rationales(rationale)
    filtered_fragments = [fragment.strip() for fragment in fragments if fragment and fragment.strip()]
    if not filtered_fragments:
        return base
    snapshot = f"{'; '.join(filtered_fragments)}."
    return combine_rationales(base, snapshot)


def _normalize_rationale(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split()).strip()
    if not text:
        return None
    if text[-1] not in ".!?":
        text = f"{text}."
    return text
