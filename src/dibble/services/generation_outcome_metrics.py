from __future__ import annotations

from dibble.models.telemetry import AuditEvent


def signal_score(value: object, *, positive: bool) -> float:
    mapping = {
        "none": 0.0,
        "low": 0.33,
        "medium": 0.66,
        "high": 1.0,
    }
    score = mapping.get(str(value), 0.5)
    return score if positive else (1.0 - score)


def score_observation_event(observation_event: AuditEvent) -> float:
    payload = observation_event.payload
    engagement_score = signal_score(payload.get("engagement"), positive=True)
    frustration_score = signal_score(payload.get("frustration"), positive=False)
    load_score = 1.0 - min(max(float(payload.get("total_load", 0.5)), 0.0), 1.0)
    confidence_score = min(max(float(payload.get("confidence_calibration", 0.5)), 0.0), 1.0)
    help_seeking_score = signal_score(payload.get("help_seeking"), positive=False)
    return (
        (engagement_score * 0.22)
        + (frustration_score * 0.22)
        + (load_score * 0.18)
        + (confidence_score * 0.22)
        + (help_seeking_score * 0.16)
    )


def score_assessment_event(assessment_event: AuditEvent) -> float:
    payload = assessment_event.payload
    evidence_score = min(max(float(payload.get("evidence_score", 0.0)), 0.0), 1.0)
    profile_update_score = 1.0 if bool(payload.get("profile_update_applied")) else 0.0
    strength_score = {
        "insufficient": 0.2,
        "emerging": 0.6,
        "demonstrated": 1.0,
    }.get(str(payload.get("evidence_strength")), 0.5)
    return (evidence_score * 0.55) + (strength_score * 0.3) + (profile_update_score * 0.15)
