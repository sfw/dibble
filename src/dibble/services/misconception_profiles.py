from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dibble.models.generation import MisconceptionSignal
from dibble.models.telemetry import AuditEvent
from dibble.services.protocols import AuditStore


@dataclass(slots=True)
class LearningMisconceptionProfileRecorder:
    audit_store: AuditStore
    recency_window_days: int = 21
    max_events: int = 1000

    def record_from_remediation_event(self, *, remediation_event: AuditEvent) -> list[AuditEvent]:
        if remediation_event.event_type != "remediation.trigger" or remediation_event.student_id is None:
            return []

        target_kc_id = remediation_event.payload.get("target_kc_id")
        misconception_signals = remediation_event.payload.get("misconception_signals")
        if not isinstance(target_kc_id, str) or not isinstance(misconception_signals, list):
            return []

        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, self.recency_window_days))
        all_events = self.audit_store.list(limit=self.max_events)
        remediation_events = [
            event
            for event in all_events
            if event.event_type == "remediation.trigger"
            and event.student_id == remediation_event.student_id
            and event.created_at >= recent_cutoff
            and event.payload.get("target_kc_id") == target_kc_id
        ]

        recorded: list[AuditEvent] = []
        for raw_signal in misconception_signals:
            if not isinstance(raw_signal, dict):
                continue
            signal_key = _signal_key(raw_signal)
            matched_signals = [
                candidate_signal
                for event in remediation_events
                for candidate_signal in _misconception_signals(event)
                if _signal_key(candidate_signal) == signal_key
            ]
            if not matched_signals:
                continue

            average_confidence = round(
                sum(float(item.get("confidence", 0.0)) for item in matched_signals) / len(matched_signals),
                2,
            )
            evidence_terms = sorted(
                {
                    str(term)
                    for item in matched_signals
                    for term in item.get("evidence_terms", [])
                    if term is not None
                }
            )
            recommended_kc_ids = sorted(
                {
                    str(kc_id)
                    for item in matched_signals
                    for kc_id in item.get("recommended_kc_ids", [])
                    if kc_id is not None
                }
            )
            profile_signal = "persistent" if len(matched_signals) >= 2 and average_confidence >= 0.6 else "tentative"
            recorded.append(
                self.audit_store.append(
                    event_type="learning.misconception.profile",
                    status="success",
                    student_id=str(remediation_event.student_id),
                    payload={
                        "target_kc_id": target_kc_id,
                        "kc_id": raw_signal.get("kc_id"),
                        "category": raw_signal.get("category"),
                        "misconception_id": raw_signal.get("misconception_id"),
                        "matched_signal_count": len(matched_signals),
                        "average_confidence": average_confidence,
                        "profile_signal": profile_signal,
                        "recommended_kc_ids": recommended_kc_ids,
                        "evidence_terms": evidence_terms,
                        "remediation_hint": raw_signal.get("remediation_hint"),
                    },
                )
            )
        return recorded


@dataclass(slots=True)
class LearningMisconceptionProfileResolver:
    recency_window_days: int = 21
    minimum_average_confidence: float = 0.45

    def matched_profile_signals(
        self,
        *,
        profile_events: list[AuditEvent],
        target_kc_id: str,
        evidence_terms: set[str],
    ) -> list[MisconceptionSignal]:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, self.recency_window_days))
        signals: list[MisconceptionSignal] = []
        for event in profile_events:
            if event.event_type != "learning.misconception.profile":
                continue
            if event.created_at < recent_cutoff:
                continue
            if event.payload.get("target_kc_id") != target_kc_id:
                continue

            average_confidence = float(event.payload.get("average_confidence", 0.0))
            if average_confidence < self.minimum_average_confidence:
                continue

            prior_terms = {str(term) for term in event.payload.get("evidence_terms", []) if term is not None}
            matched_terms = sorted(prior_terms.intersection(evidence_terms))
            if evidence_terms and not matched_terms and event.payload.get("profile_signal") != "persistent":
                continue

            matched_signal_count = max(1, int(event.payload.get("matched_signal_count", 1)))
            confidence = min(0.99, average_confidence + min(0.18, matched_signal_count * 0.05))
            signals.append(
                MisconceptionSignal(
                    kc_id=str(event.payload.get("kc_id") or target_kc_id),
                    category=str(event.payload.get("category") or "persistent_misconception"),
                    confidence=round(confidence, 2),
                    rationale=(
                        "Prior remediation runs repeatedly surfaced this misconception pattern"
                        + (f" with overlap on {', '.join(matched_terms)}." if matched_terms else ".")
                    ),
                    source="profile",
                    misconception_id=_string_or_none(event.payload.get("misconception_id")),
                    recommended_kc_ids=[
                        str(kc_id) for kc_id in event.payload.get("recommended_kc_ids", []) if kc_id is not None
                    ],
                    remediation_hint=_string_or_none(event.payload.get("remediation_hint")),
                    evidence_terms=matched_terms or sorted(prior_terms),
                )
            )
        return signals


def _misconception_signals(event: AuditEvent) -> list[dict[str, object]]:
    payload_signals = event.payload.get("misconception_signals")
    if not isinstance(payload_signals, list):
        return []
    return [signal for signal in payload_signals if isinstance(signal, dict)]


def _signal_key(signal: dict[str, object]) -> tuple[str, str, str | None]:
    return (
        str(signal.get("kc_id") or ""),
        str(signal.get("category") or ""),
        _string_or_none(signal.get("misconception_id")),
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
