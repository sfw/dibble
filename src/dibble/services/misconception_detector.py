from __future__ import annotations

import re

from dibble.models.curriculum import KnowledgeComponent, KnowledgeComponentMisconception
from dibble.models.generation import MisconceptionSignal
from dibble.models.profile import LearnerProfile
from dibble.services.misconception_profiles import LearningMisconceptionProfileResolver
from dibble.services.protocols import AuditStore, KnowledgeComponentStore


_WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")
_STOPWORDS = {
    "and",
    "for",
    "from",
    "into",
    "like",
    "same",
    "that",
    "the",
    "their",
    "they",
    "while",
    "with",
}


def _normalize_terms(value: str) -> set[str]:
    return {
        word.lower()
        for word in _WORD_PATTERN.findall(value)
        if len(word) >= 3 and word.lower() not in _STOPWORDS
    }


class MisconceptionDetector:
    def __init__(
        self,
        knowledge_component_store: KnowledgeComponentStore,
        *,
        audit_store: AuditStore | None = None,
        misconception_profile_resolver: LearningMisconceptionProfileResolver | None = None,
    ) -> None:
        self.knowledge_component_store = knowledge_component_store
        self.audit_store = audit_store
        self.misconception_profile_resolver = misconception_profile_resolver

    def detect(
        self,
        profile: LearnerProfile,
        *,
        target_kc_id: str,
        misconception_description: str,
        curriculum_context: list[str],
    ) -> list[MisconceptionSignal]:
        evidence_terms = _normalize_terms(misconception_description)
        for item in curriculum_context:
            evidence_terms.update(_normalize_terms(item))

        target_component = self.knowledge_component_store.get(target_kc_id)
        prerequisite_components = self.knowledge_component_store.list_prerequisites(target_kc_id)
        signals: list[MisconceptionSignal] = []

        if self.audit_store is not None and self.misconception_profile_resolver is not None:
            profile_events = [
                event
                for event in self.audit_store.list(limit=500)
                if event.event_type == "learning.misconception.profile" and event.student_id == profile.student_id
            ]
            signals.extend(
                self.misconception_profile_resolver.matched_profile_signals(
                    profile_events=profile_events,
                    target_kc_id=target_kc_id,
                    evidence_terms=evidence_terms,
                )
            )

        for component in [*prerequisite_components, target_component]:
            if component is None:
                continue
            signals.extend(self._catalog_signals(component=component, profile=profile, evidence_terms=evidence_terms))

        for component in prerequisite_components:
            mastery = profile.knowledge_state.kc_mastery.get(component.kc_id, 0.0)
            overlap_terms = self._overlap_terms(component.name, component.tags, evidence_terms)
            mastery_gap = max(0.75 - mastery, 0.0)
            if mastery_gap <= 0 and not overlap_terms:
                continue

            confidence = min(0.95, 0.45 + (mastery_gap * 0.6) + (len(overlap_terms) * 0.08))
            rationale = (
                f"{component.name} looks like a prerequisite gap because mastery is {mastery:.2f}"
                + (f" and the misconception language overlaps on {', '.join(overlap_terms)}." if overlap_terms else ".")
            )
            signals.append(
                MisconceptionSignal(
                    kc_id=component.kc_id,
                    category="prerequisite_gap",
                    confidence=round(confidence, 2),
                    rationale=rationale,
                    source="heuristic",
                    recommended_kc_ids=[component.kc_id],
                    evidence_terms=overlap_terms,
                )
            )

        target_mastery = profile.knowledge_state.kc_mastery.get(target_kc_id, 0.0)
        target_overlap = self._overlap_terms(
            target_component.name if target_component is not None else target_kc_id,
            target_component.tags if target_component is not None else [],
            evidence_terms,
        )
        if target_mastery < 0.85 or target_overlap:
            confidence = min(0.9, 0.4 + max(0.85 - target_mastery, 0.0) * 0.5 + len(target_overlap) * 0.05)
            target_name = target_component.name if target_component is not None else target_kc_id
            signals.append(
                MisconceptionSignal(
                    kc_id=target_kc_id,
                    category="target_concept_confusion",
                    confidence=round(confidence, 2),
                    rationale=(
                        f"{target_name} still appears fragile with mastery {target_mastery:.2f}"
                        + (f" and overlap on {', '.join(target_overlap)}." if target_overlap else ".")
                    ),
                    source="heuristic",
                    recommended_kc_ids=[target_kc_id],
                    evidence_terms=target_overlap,
                )
            )

        signals = _deduplicate_signals(signals)
        source_priority = {"profile": 0, "catalog": 1, "heuristic": 2}
        signals.sort(
            key=lambda item: (
                -item.confidence,
                source_priority.get(item.source, 3),
                item.kc_id,
                item.category,
            )
        )
        return signals

    def _overlap_terms(self, name: str, tags: list[str], evidence_terms: set[str]) -> list[str]:
        component_terms = _normalize_terms(name)
        for tag in tags:
            component_terms.update(_normalize_terms(tag))
        return sorted(component_terms.intersection(evidence_terms))

    def _catalog_signals(
        self,
        *,
        component: KnowledgeComponent,
        profile: LearnerProfile,
        evidence_terms: set[str],
    ) -> list[MisconceptionSignal]:
        signals: list[MisconceptionSignal] = []
        mastery = profile.knowledge_state.kc_mastery.get(component.kc_id, 0.0)
        mastery_gap = max(0.85 - mastery, 0.0)
        for misconception in component.common_misconceptions:
            trigger_terms = set()
            for term in misconception.trigger_terms:
                trigger_terms.update(_normalize_terms(term))
            trigger_terms.update(_normalize_terms(misconception.label))
            trigger_terms.update(_normalize_terms(misconception.description))
            matched_terms = sorted(trigger_terms.intersection(evidence_terms))
            if not matched_terms:
                continue
            overlap_ratio = len(matched_terms) / max(1, len(trigger_terms))
            confidence = min(0.98, 0.55 + (overlap_ratio * 0.25) + (mastery_gap * 0.25))
            signals.append(
                MisconceptionSignal(
                    kc_id=component.kc_id,
                    category="known_misconception",
                    confidence=round(confidence, 2),
                    rationale=(
                        f"{component.name} matches the misconception pattern '{misconception.label}'"
                        f" based on {', '.join(matched_terms)}."
                    ),
                    source="catalog",
                    misconception_id=misconception.misconception_id,
                    recommended_kc_ids=misconception.prerequisite_kc_ids or [component.kc_id],
                    remediation_hint=misconception.remediation_hint,
                    evidence_terms=matched_terms,
                )
            )
        return signals


def _deduplicate_signals(signals: list[MisconceptionSignal]) -> list[MisconceptionSignal]:
    best_by_key: dict[tuple[str, str, str | None], MisconceptionSignal] = {}
    source_priority = {"profile": 0, "catalog": 1, "heuristic": 2}
    for signal in signals:
        key = (signal.kc_id, signal.category, signal.misconception_id)
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = signal
            continue
        if (signal.confidence, -source_priority.get(signal.source, 3)) > (
            current.confidence,
            -source_priority.get(current.source, 3),
        ):
            best_by_key[key] = signal
    return list(best_by_key.values())
