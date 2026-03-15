from __future__ import annotations

import re

from dibble.models.generation import MisconceptionSignal
from dibble.models.profile import LearnerProfile
from dibble.services.protocols import KnowledgeComponentStore


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
    def __init__(self, knowledge_component_store: KnowledgeComponentStore) -> None:
        self.knowledge_component_store = knowledge_component_store

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
                    evidence_terms=target_overlap,
                )
            )

        signals.sort(key=lambda item: (-item.confidence, item.kc_id))
        return signals

    def _overlap_terms(self, name: str, tags: list[str], evidence_terms: set[str]) -> list[str]:
        component_terms = _normalize_terms(name)
        for tag in tags:
            component_terms.update(_normalize_terms(tag))
        return sorted(component_terms.intersection(evidence_terms))
