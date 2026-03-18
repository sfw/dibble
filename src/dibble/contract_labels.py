from __future__ import annotations


def triage_section_for(*, attention_level: str, proposal_status: str) -> str:
    if proposal_status == "available":
        return "teacher_action"
    if attention_level in {"high", "medium"}:
        return "needs_attention"
    return "on_track"


def continue_action_display_label(kind: str) -> str | None:
    labels = {
        "idle": "All caught up",
        "generate_follow_up": "Continue your lesson",
        "advance_remediation": "Keep practicing",
        "continue_socratic": "Check your understanding",
    }
    return labels.get(kind)


def stage_display_label(stage: str) -> str | None:
    labels = {
        "idle": "Learning",
        "repair": "Building foundations",
        "bridge": "Connecting ideas",
        "target": "Learning new skills",
        "transfer": "Applying what you know",
        "mastered": "Mastered",
    }
    return labels.get(stage)


def remediation_phase_display_label(phase: str) -> str | None:
    labels = {
        "step_back": "Step back support",
        "repair": "Building foundations",
        "bridge": "Connecting ideas",
        "return": "Trying it yourself",
    }
    return labels.get(phase)


def affective_support_message(
    *, frustration: str, engagement: str
) -> dict[str, str] | None:
    if frustration == "high":
        return {
            "kind": "break_suggestion",
            "title": "It's okay to take a break",
            "detail": "If this feels tough, try re-reading the last step or ask for a hint. You've got this.",
        }
    if frustration == "medium":
        return {
            "kind": "nudge",
            "title": "Need a different approach?",
            "detail": "Sometimes seeing an idea from another angle helps. Check the hints if you're stuck.",
        }
    if engagement == "high":
        return {
            "kind": "encouragement",
            "title": "You're on a roll!",
            "detail": "Keep going — your focus is paying off.",
        }
    return None
