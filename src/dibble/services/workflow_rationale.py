from __future__ import annotations

ACTION_TARGET_STAGE = {
    "hold_target": "target",
    "hold_target_before_assessment": "target",
    "hold_repair_target": "repair",
    "hold_repair_target_before_assessment": "repair",
    "hold_bridge_target": "bridge",
    "bridge_before_assessment": "bridge",
    "bridge_to_related_kc": "bridge",
    "rebuild_prerequisite_first": "repair",
    "rebuild_prerequisite_before_assessment": "repair",
    "attempt_transfer": "transfer",
    "complete": "transfer",
    "step_back": "repair",
}

ACTION_DECISION_CLAUSES = {
    "hold_target": "The backend is holding the current target instead of assigning transfer yet.",
    "hold_target_before_assessment": "The backend is holding the current target instead of assigning transfer yet.",
    "hold_repair_target": "The backend is holding repair instead of returning to the target yet.",
    "hold_repair_target_before_assessment": "The backend is holding repair instead of returning to the target yet.",
    "hold_bridge_target": "The backend is holding one guided bridge step instead of releasing transfer yet.",
    "bridge_before_assessment": "The backend is holding one guided bridge step instead of releasing transfer yet.",
    "bridge_to_related_kc": "The backend is bridging through a related KC instead of releasing transfer immediately.",
    "rebuild_prerequisite_first": "The backend is rebuilding the prerequisite instead of returning to the target yet.",
    "rebuild_prerequisite_before_assessment": "The backend is rebuilding the prerequisite instead of returning to the target yet.",
    "attempt_transfer": "The backend is testing transfer instead of adding another support step.",
    "complete": "The backend is ready to return to transfer instead of holding another remediation step.",
    "step_back": "The backend is stepping back to repair reasoning instead of pushing transfer yet.",
}

TARGET_STAGE_DECISION_CLAUSES = {
    "assessment": "The backend is gathering one more assessment signal instead of releasing into practice yet.",
    "target": "The backend is staying on target practice instead of assigning transfer yet.",
    "repair": "The backend is staying in repair instead of returning to the target yet.",
    "bridge": "The backend is holding one guided bridge step instead of releasing transfer yet.",
    "transfer": "The backend is testing transfer instead of adding another support step.",
}


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


def decision_grade_rationale(
    primary: str | None,
    *,
    action: str | None = None,
    target_stage: str | None = None,
    fallback: str | None = None,
    step_phase: str | None = None,
    step_instruction: str | None = None,
) -> str | None:
    rationale = combine_rationales(primary, fallback)
    semantics = decision_semantics_clause(action=action, target_stage=target_stage)
    if semantics is not None and not _has_decision_semantics(rationale):
        rationale = combine_rationales(rationale, semantics)
    step_context = current_step_context(phase=step_phase, instruction=step_instruction)
    if step_context is not None:
        rationale = combine_rationales(rationale, step_context)
    return rationale


def decision_semantics_clause(*, action: str | None = None, target_stage: str | None = None) -> str | None:
    if action is not None:
        clause = ACTION_DECISION_CLAUSES.get(str(action))
        if clause is not None:
            return clause
    if target_stage is not None:
        return TARGET_STAGE_DECISION_CLAUSES.get(str(target_stage))
    return None


def target_stage_for_action(action: str | None, *, fallback: str = "target") -> str:
    if action is None:
        return fallback
    return ACTION_TARGET_STAGE.get(str(action), fallback)


def target_stage_for_phase(phase: str | None, *, fallback: str = "repair") -> str:
    if phase == "bridge":
        return "bridge"
    if phase == "return":
        return "transfer"
    if phase == "assessment":
        return "assessment"
    if phase is None:
        return fallback
    return fallback


def current_step_context(*, phase: str | None, instruction: str | None) -> str | None:
    normalized_instruction = _normalize_rationale(instruction)
    if normalized_instruction is None:
        return None
    phase_label = (phase or "current").replace("_", " ")
    return f"Current {phase_label} step: {normalized_instruction}"


def _normalize_rationale(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split()).strip()
    if not text:
        return None
    if text[-1] not in ".!?":
        text = f"{text}."
    return text


def _has_decision_semantics(value: str | None) -> bool:
    normalized = _normalize_rationale(value)
    if normalized is None:
        return False
    lowered = normalized.lower()
    return (
        "instead of" in lowered
        or "before transfer" in lowered
        or "returning to the target" in lowered
        or "releasing transfer" in lowered
        or "releasing into practice" in lowered
    )
