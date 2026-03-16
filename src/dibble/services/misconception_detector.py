from __future__ import annotations

import re

from dibble.models.curriculum import KnowledgeComponent
from dibble.models.generation import MisconceptionSignal
from dibble.models.profile import LearnerProfile
from dibble.services.knowledge_component_graph import KnowledgeComponentGraph
from dibble.services.misconception_disambiguation import MisconceptionDisambiguationService
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
_TERM_ALIASES = {
    "top": {"numerator"},
    "bottom": {"denominator"},
    "numerator": {"top"},
    "denominator": {"bottom"},
    "swap": {"interchangeable", "swaps", "swapping"},
    "swaps": {"swap", "interchangeable"},
    "swapping": {"swap", "interchangeable"},
    "interchangeable": {"swap"},
    "separate": {"separately"},
    "separately": {"separate"},
    "whole": {"whole_number"},
    "numbers": {"number"},
    "number": {"numbers"},
}


def _normalize_terms(value: str) -> set[str]:
    normalized = {
        word.lower()
        for word in _WORD_PATTERN.findall(value)
        if len(word) >= 3 and word.lower() not in _STOPWORDS
    }
    expanded = set(normalized)
    for term in normalized:
        expanded.update(_TERM_ALIASES.get(term, set()))
    return expanded


class MisconceptionDetector:
    def __init__(
        self,
        knowledge_component_store: KnowledgeComponentStore,
        *,
        audit_store: AuditStore | None = None,
        misconception_profile_resolver: LearningMisconceptionProfileResolver | None = None,
        misconception_disambiguation_service: MisconceptionDisambiguationService | None = None,
    ) -> None:
        self.knowledge_component_store = knowledge_component_store
        self.audit_store = audit_store
        self.misconception_profile_resolver = misconception_profile_resolver
        self.misconception_disambiguation_service = (
            misconception_disambiguation_service or MisconceptionDisambiguationService()
        )

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
        all_components = self.knowledge_component_store.list()
        graph = KnowledgeComponentGraph(all_components)
        prerequisite_relations = graph.prerequisites_for(target_kc_id)
        prerequisite_components = [relation.component for relation in prerequisite_relations]
        prerequisite_relations_by_id = {relation.component.kc_id: relation for relation in prerequisite_relations}
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
            relation = prerequisite_relations_by_id.get(component.kc_id)
            relation_bonus = 0.0
            if relation is not None:
                relation_bonus = max(0.0, (relation.path_weight * 0.18) - ((relation.depth - 1) * 0.05))

            confidence = min(0.95, 0.42 + (mastery_gap * 0.55) + (len(overlap_terms) * 0.08) + relation_bonus)
            rationale = (
                f"{component.name} looks like a prerequisite gap because mastery is {mastery:.2f}"
                + (f" and the misconception language overlaps on {', '.join(overlap_terms)}." if overlap_terms else ".")
                + (
                    f" It is a depth-{relation.depth} prerequisite with path weight {relation.path_weight:.2f}."
                    if relation is not None
                    else ""
                )
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
        signals = self.misconception_disambiguation_service.annotate(signals)
        source_priority = {"profile": 0, "catalog": 1, "heuristic": 2}
        recurrence_priority = {"relapsing": 0, "recurring": 1, "repeated": 2, "tentative": 3, "none": 4}
        signals.sort(
            key=lambda item: (
                -int(item.primary_for_kc),
                -item.confidence,
                -item.recurrence_session_count,
                -item.recurrence_count,
                -max(0, 4 - recurrence_priority.get(item.recurrence_signal, 4)),
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
        component_terms = _normalize_terms(component.name)
        for tag in component.tags:
            component_terms.update(_normalize_terms(tag))
        for misconception in component.common_misconceptions:
            trigger_terms = set()
            for term in misconception.trigger_terms:
                trigger_terms.update(_normalize_terms(term))
            trigger_terms.update(_normalize_terms(misconception.label))
            trigger_terms.update(_normalize_terms(misconception.description))
            matched_terms = sorted(trigger_terms.intersection(evidence_terms))
            if not matched_terms:
                continue
            distinctive_terms = sorted(term for term in matched_terms if term not in component_terms)
            overlap_ratio = len(matched_terms) / max(1, len(trigger_terms))
            distinctive_ratio = len(distinctive_terms) / max(1, len(matched_terms))
            repair_target_bonus = 0.06 if misconception.prerequisite_kc_ids else 0.0
            confidence = min(
                0.98,
                0.5
                + (overlap_ratio * 0.2)
                + (distinctive_ratio * 0.12)
                + (mastery_gap * 0.22)
                + repair_target_bonus,
            )
            signals.append(
                MisconceptionSignal(
                    kc_id=component.kc_id,
                    category="known_misconception",
                    confidence=round(confidence, 2),
                    rationale=(
                        f"{component.name} matches the misconception pattern '{misconception.label}'"
                        f" based on {', '.join(distinctive_terms or matched_terms)}."
                    ),
                    source="catalog",
                    misconception_id=misconception.misconception_id,
                    recommended_kc_ids=misconception.prerequisite_kc_ids or [component.kc_id],
                    remediation_hint=misconception.remediation_hint,
                    evidence_terms=distinctive_terms or matched_terms,
                )
            )
        return signals


def _deduplicate_signals(signals: list[MisconceptionSignal]) -> list[MisconceptionSignal]:
    best_by_key: dict[tuple[str, str, str | None], MisconceptionSignal] = {}
    source_priority = {"profile": 0, "catalog": 1, "heuristic": 2}
    recurrence_priority = {"relapsing": 0, "recurring": 1, "repeated": 2, "tentative": 3, "none": 4}
    for signal in signals:
        key = (signal.kc_id, signal.category, signal.misconception_id)
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = signal
            continue

        preferred = _preferred_signal(
            current=current,
            candidate=signal,
            source_priority=source_priority,
            recurrence_priority=recurrence_priority,
        )
        secondary = signal if preferred is current else current
        best_by_key[key] = preferred.model_copy(
            update={
                "confidence": round(max(current.confidence, signal.confidence), 2),
                "recommended_kc_ids": _unique_items(
                    [*preferred.recommended_kc_ids, *secondary.recommended_kc_ids]
                ),
                "remediation_hint": preferred.remediation_hint or secondary.remediation_hint,
                "evidence_terms": _unique_items([*preferred.evidence_terms, *secondary.evidence_terms]),
                "recurrence_count": max(current.recurrence_count, signal.recurrence_count),
                "recurrence_session_count": max(
                    current.recurrence_session_count,
                    signal.recurrence_session_count,
                ),
                "recurrence_signal": _stronger_recurrence_signal(
                    current.recurrence_signal,
                    signal.recurrence_signal,
                    recurrence_priority=recurrence_priority,
                ),
                "last_seen_at": _later_timestamp(current.last_seen_at, signal.last_seen_at),
            }
        )
    return list(best_by_key.values())


def _preferred_signal(
    *,
    current: MisconceptionSignal,
    candidate: MisconceptionSignal,
    source_priority: dict[str, int],
    recurrence_priority: dict[str, int],
) -> MisconceptionSignal:
    current_key = (
        -current.recurrence_session_count,
        -current.recurrence_count,
        recurrence_priority.get(current.recurrence_signal, 4),
        -current.confidence,
        source_priority.get(current.source, 3),
    )
    candidate_key = (
        -candidate.recurrence_session_count,
        -candidate.recurrence_count,
        recurrence_priority.get(candidate.recurrence_signal, 4),
        -candidate.confidence,
        source_priority.get(candidate.source, 3),
    )
    return current if current_key <= candidate_key else candidate


def _stronger_recurrence_signal(
    left: str,
    right: str,
    *,
    recurrence_priority: dict[str, int],
) -> str:
    return left if recurrence_priority.get(left, 4) <= recurrence_priority.get(right, 4) else right


def _later_timestamp(left, right):
    if left is None:
        return right
    if right is None:
        return left
    return left if left >= right else right


def _unique_items(values: list[str]) -> list[str]:
    deduplicated: list[str] = []
    for value in values:
        if value not in deduplicated:
            deduplicated.append(value)
    return deduplicated
