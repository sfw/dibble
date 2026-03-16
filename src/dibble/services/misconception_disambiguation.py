from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import MisconceptionSignal


@dataclass(slots=True)
class MisconceptionDisambiguationService:
    def annotate(self, signals: list[MisconceptionSignal]) -> list[MisconceptionSignal]:
        updates: dict[int, MisconceptionSignal] = {}
        candidates_by_kc: dict[str, list[MisconceptionSignal]] = {}
        for signal in signals:
            if not _is_disambiguation_candidate(signal):
                continue
            candidates_by_kc.setdefault(signal.kc_id, []).append(signal)

        for kc_id, candidates in candidates_by_kc.items():
            term_counts = _term_counts(candidates)
            ranked_candidates = sorted(
                candidates,
                key=lambda item: (
                    self._score(item, term_counts=term_counts),
                    item.confidence,
                    item.recurrence_session_count,
                    item.recurrence_count,
                    len(item.evidence_terms),
                ),
                reverse=True,
            )
            primary_signal = ranked_candidates[0]
            primary_score = self._score(primary_signal, term_counts=term_counts)
            for signal in ranked_candidates:
                score = self._score(signal, term_counts=term_counts)
                updates[id(signal)] = signal.model_copy(
                    update={
                        "primary_for_kc": signal is primary_signal,
                        "disambiguation_score": score,
                        "disambiguation_rationale": self._rationale(
                            kc_id=kc_id,
                            signal=signal,
                            primary_signal=primary_signal,
                            score_delta=round(primary_score - score, 2),
                        ),
                    }
                )
        return [updates.get(id(signal), signal) for signal in signals]

    def _score(self, signal: MisconceptionSignal, *, term_counts: dict[str, int]) -> float:
        source_bonus = {
            "profile": 16.0,
            "catalog": 8.0,
            "heuristic": 0.0,
        }.get(signal.source, 0.0)
        recurrence_bonus = min(
            30.0,
            (signal.recurrence_session_count * 7.0) + (signal.recurrence_count * 2.0),
        )
        evidence_bonus = min(18.0, len(signal.evidence_terms) * 4.0)
        repair_target_bonus = 3.0 if signal.recommended_kc_ids and signal.recommended_kc_ids != [signal.kc_id] else 0.0
        distinctive_bonus = min(
            16.0,
            sum(6.0 for term in signal.evidence_terms if term_counts.get(term, 0) == 1),
        )
        return round(
            (signal.confidence * 100.0)
            + source_bonus
            + recurrence_bonus
            + evidence_bonus
            + repair_target_bonus
            + distinctive_bonus,
            2,
        )

    def _rationale(
        self,
        *,
        kc_id: str,
        signal: MisconceptionSignal,
        primary_signal: MisconceptionSignal,
        score_delta: float,
    ) -> str:
        evidence_fragment = (
            f"{len(signal.evidence_terms)} matched evidence terms"
            if signal.evidence_terms
            else "limited direct evidence overlap"
        )
        recurrence_fragment = (
            f" with {signal.recurrence_session_count} prior sessions of recurrence"
            if signal.recurrence_session_count > 0
            else ""
        )
        if signal is primary_signal:
            return (
                f"Selected as the primary misconception for {kc_id} because it has {evidence_fragment}"
                f"{recurrence_fragment} and the strongest combined disambiguation score."
            )
        return (
            f"Ranked behind {primary_signal.misconception_id or primary_signal.category} for {kc_id} because it has"
            f" {evidence_fragment}{recurrence_fragment} and trails the primary signal by {score_delta:.2f} points."
        )


def _is_disambiguation_candidate(signal: MisconceptionSignal) -> bool:
    return signal.category == "known_misconception" and signal.misconception_id is not None


def _term_counts(signals: list[MisconceptionSignal]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for signal in signals:
        for term in signal.evidence_terms:
            counts[term] = counts.get(term, 0) + 1
    return counts
