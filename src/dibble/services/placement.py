"""Cold-start diagnostic placement.

Adaptive walk over the KC prerequisite graph: start at the grade band's
anchor KCs, probe dependents after a correct answer and prerequisites after
an incorrect one, stop at a question budget or graph-frontier convergence.
Probes use the verified generation path (1.3), so a learner never places
against an unverified item. On completion the mastery profile is seeded with
moderate values — direct evidence on probed KCs, graph-propagated estimates
on their neighbours — so live observations dominate quickly.
(POC roadmap 2.1)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from dibble.models.corpus import ANCHOR_TAG
from dibble.models.curriculum import KnowledgeComponent
from dibble.models.generation import (
    ContentIntent,
    GenerationRequest,
    RequestedContentType,
)
from dibble.models.placement import (
    PlacementItemView,
    PlacementKcSummary,
    PlacementProbe,
    PlacementReport,
    PlacementSession,
    PlacementStateResponse,
)
from dibble.models.profile import LearnerProfile
from dibble.services.placement_session_store import SQLitePlacementSessionStore
from dibble.services.protocols import (
    AuditStore,
    KnowledgeComponentStore,
    ProfileStore,
)

logger = logging.getLogger(__name__)

PLACEMENT_STARTED_EVENT_TYPE = "placement.started"
PLACEMENT_COMPLETED_EVENT_TYPE = "placement.completed"

# Seeded mastery values stay near the 0.5 prior so live observations
# dominate quickly.
_SEED_DEMONSTRATED = 0.7
_SEED_PREREQUISITE_OF_DEMONSTRATED = 0.62
_SEED_GAP = 0.3
_SEED_DEPENDENT_OF_GAP = 0.38


class PlacementError(ValueError):
    pass


@dataclass(slots=True)
class PlacementService:
    knowledge_component_store: KnowledgeComponentStore
    profile_store: ProfileStore
    generation_engine: object  # GenerationEngine (duck-typed: .generate)
    session_store: SQLitePlacementSessionStore
    audit_store: AuditStore | None = None
    _dependents_cache: dict[str, list[str]] = field(default_factory=dict)

    # -- public API ---------------------------------------------------------

    def start(
        self,
        *,
        student_id: UUID,
        grade_band: str,
        question_budget: int = 15,
    ) -> PlacementStateResponse:
        anchors = self._anchor_kcs(grade_band)
        if not anchors:
            raise PlacementError(
                f"No anchor KCs found for grade band {grade_band!r}; "
                f"ingest a corpus with '{ANCHOR_TAG}'-tagged KCs first."
            )
        session = PlacementSession(
            session_id=str(uuid4()),
            student_id=str(student_id),
            grade_band=grade_band,
            question_budget=question_budget,
            queued_kc_ids=[kc.kc_id for kc in anchors],
        )
        self._emit(
            PLACEMENT_STARTED_EVENT_TYPE,
            student_id=str(student_id),
            payload={
                "session_id": session.session_id,
                "grade_band": grade_band,
                "anchor_kc_ids": list(session.queued_kc_ids),
                "question_budget": question_budget,
            },
        )
        self._advance_to_next_item(session)
        if self._pending_probe(session) is None:
            # No probeable item could be produced — complete immediately so
            # the session never strands in an unanswerable active state.
            self._complete(session)
        self.session_store.upsert(session)
        return self._state(session)

    def respond(
        self,
        *,
        student_id: UUID,
        session_id: str,
        selected_option_id: str | None = None,
        correct: bool | None = None,
    ) -> PlacementStateResponse:
        session = self.session_store.get(session_id)
        if session is None or session.student_id != str(student_id):
            raise PlacementError("Placement session not found for this learner.")
        if session.status != "active":
            raise PlacementError("Placement session is already completed.")
        probe = self._pending_probe(session)
        if probe is None:
            raise PlacementError("Placement session has no pending question.")

        probe.correct = self._grade(
            probe=probe, selected_option_id=selected_option_id, correct=correct
        )
        probe.responded_at = datetime.now(timezone.utc)
        if probe.correct:
            session.demonstrated_kc_ids.append(probe.kc_id)
            self._enqueue(session, self._dependents_of(probe.kc_id))
        else:
            session.gap_kc_ids.append(probe.kc_id)
            component = self.knowledge_component_store.get(probe.kc_id)
            if component is not None:
                self._enqueue(session, component.prerequisite_kc_ids)

        if len(session.probes) >= session.question_budget or not session.queued_kc_ids:
            self._complete(session)
        else:
            self._advance_to_next_item(session)
            if self._pending_probe(session) is None:
                self._complete(session)

        session.updated_at = datetime.now(timezone.utc)
        self.session_store.upsert(session)
        return self._state(session)

    def get_state(self, *, student_id: UUID, session_id: str) -> PlacementStateResponse:
        session = self.session_store.get(session_id)
        if session is None or session.student_id != str(student_id):
            raise PlacementError("Placement session not found for this learner.")
        return self._state(session)

    def latest_report(self, *, student_id: UUID) -> PlacementReport | None:
        for session in self.session_store.list_for_student(student_id=str(student_id)):
            if session.status == "completed":
                return self._build_report(session)
        return None

    # -- graph walk ----------------------------------------------------------

    def _anchor_kcs(self, grade_band: str) -> list[KnowledgeComponent]:
        return [
            kc
            for kc in self.knowledge_component_store.list()
            if kc.grade_level == grade_band and ANCHOR_TAG in kc.tags
        ]

    def _dependents_of(self, kc_id: str) -> list[str]:
        if not self._dependents_cache:
            for component in self.knowledge_component_store.list():
                for prerequisite_id in component.prerequisite_kc_ids:
                    self._dependents_cache.setdefault(prerequisite_id, []).append(
                        component.kc_id
                    )
        return self._dependents_cache.get(kc_id, [])

    def _enqueue(self, session: PlacementSession, kc_ids: list[str]) -> None:
        seen = set(session.probed_kc_ids) | set(session.queued_kc_ids)
        for kc_id in kc_ids:
            if kc_id in seen:
                continue
            if self.knowledge_component_store.get(kc_id) is None:
                continue
            # Walk-driven probes take priority over remaining anchors so the
            # binary search descends a chain before sampling a new region.
            session.queued_kc_ids.insert(0, kc_id)
            seen.add(kc_id)

    def _advance_to_next_item(self, session: PlacementSession) -> None:
        while session.queued_kc_ids:
            kc_id = session.queued_kc_ids.pop(0)
            component = self.knowledge_component_store.get(kc_id)
            if component is None:
                continue
            probe = PlacementProbe(kc_id=kc_id, kc_name=component.name)
            try:
                response = self.generation_engine.generate(  # type: ignore[attr-defined]
                    self._profile_for(session),
                    GenerationRequest(
                        student_id=UUID(session.student_id),
                        target_kc_ids=[kc_id],
                        target_lo_ids=[component.outcome_id],
                        intent=ContentIntent.practice,
                        requested_content_type=RequestedContentType.practice_problem,
                        learning_session_id=f"placement-{session.session_id}",
                        curriculum_context=[component.name],
                    ),
                )
            except Exception:  # noqa: BLE001 - skip unprobeable KCs, keep placing
                logger.warning(
                    "Placement item generation failed for %s", kc_id, exc_info=True
                )
                continue
            block = next(
                (
                    candidate
                    for candidate in response.blocks
                    if candidate.interaction is not None
                ),
                response.blocks[0] if response.blocks else None,
            )
            if block is None:
                continue
            probe.generation_id = response.generation_id
            probe.block = block
            session.probes.append(probe)
            session.probed_kc_ids.append(kc_id)
            return

    def _pending_probe(self, session: PlacementSession) -> PlacementProbe | None:
        if session.probes and session.probes[-1].correct is None:
            return session.probes[-1]
        return None

    def _grade(
        self,
        *,
        probe: PlacementProbe,
        selected_option_id: str | None,
        correct: bool | None,
    ) -> bool:
        interaction = probe.block.interaction if probe.block is not None else None
        if interaction is not None and selected_option_id is not None:
            return selected_option_id == interaction.correct_option_id
        if correct is not None:
            return correct
        raise PlacementError(
            "Response must include selected_option_id (for choice items) or correct."
        )

    # -- completion ----------------------------------------------------------

    def _complete(self, session: PlacementSession) -> None:
        # Drop an unanswered trailing probe so the report reflects evidence.
        if session.probes and session.probes[-1].correct is None:
            dangling = session.probes.pop()
            if dangling.kc_id in session.probed_kc_ids:
                session.probed_kc_ids.remove(dangling.kc_id)
        session.status = "completed"
        self._seed_profile(session)
        report = self._build_report(session)
        self._emit(
            PLACEMENT_COMPLETED_EVENT_TYPE,
            student_id=session.student_id,
            payload={
                "session_id": session.session_id,
                "grade_band": session.grade_band,
                "probed_count": len(session.probes),
                "demonstrated_kc_ids": list(session.demonstrated_kc_ids),
                "gap_kc_ids": list(session.gap_kc_ids),
                "starting_kc_ids": [kc.kc_id for kc in report.starting_kcs],
            },
        )

    def _seed_profile(self, session: PlacementSession) -> None:
        profile = self._profile_for(session)
        kc_mastery = dict(profile.knowledge_state.kc_mastery)

        def raise_to(kc_id: str, value: float) -> None:
            kc_mastery[kc_id] = max(kc_mastery.get(kc_id, 0.0), value)

        def lower_to(kc_id: str, value: float) -> None:
            kc_mastery[kc_id] = min(kc_mastery.get(kc_id, 1.0), value)

        for kc_id in session.demonstrated_kc_ids:
            raise_to(kc_id, _SEED_DEMONSTRATED)
            component = self.knowledge_component_store.get(kc_id)
            for prerequisite_id in component.prerequisite_kc_ids if component else []:
                if prerequisite_id not in session.gap_kc_ids:
                    raise_to(prerequisite_id, _SEED_PREREQUISITE_OF_DEMONSTRATED)
        for kc_id in session.gap_kc_ids:
            lower_to(kc_id, _SEED_GAP)
            for dependent_id in self._dependents_of(kc_id):
                if dependent_id not in session.demonstrated_kc_ids:
                    lower_to(dependent_id, _SEED_DEPENDENT_OF_GAP)

        profile.knowledge_state.kc_mastery = kc_mastery
        profile.knowledge_state.last_updated = datetime.now(timezone.utc)
        self.profile_store.upsert(profile)

    def _build_report(self, session: PlacementSession) -> PlacementReport:
        def summaries(kc_ids: list[str]) -> list[PlacementKcSummary]:
            items: list[PlacementKcSummary] = []
            for kc_id in kc_ids:
                component = self.knowledge_component_store.get(kc_id)
                items.append(
                    PlacementKcSummary(
                        kc_id=kc_id,
                        name=component.name if component else kc_id,
                    )
                )
            return items

        gap_set = set(session.gap_kc_ids)
        # Start where the learner can succeed next: gaps whose prerequisites
        # are not themselves gaps (the deepest unmet KCs), else the frontier
        # past what was demonstrated, else the band's anchors.
        starting_ids: list[str] = []
        for kc_id in session.gap_kc_ids:
            component = self.knowledge_component_store.get(kc_id)
            prerequisite_gaps = [
                prerequisite_id
                for prerequisite_id in (
                    component.prerequisite_kc_ids if component else []
                )
                if prerequisite_id in gap_set
            ]
            if not prerequisite_gaps:
                starting_ids.append(kc_id)
        if not starting_ids and session.demonstrated_kc_ids:
            for kc_id in session.demonstrated_kc_ids:
                for dependent_id in self._dependents_of(kc_id):
                    if (
                        dependent_id not in session.demonstrated_kc_ids
                        and dependent_id not in starting_ids
                    ):
                        starting_ids.append(dependent_id)
        if not starting_ids:
            starting_ids = [kc.kc_id for kc in self._anchor_kcs(session.grade_band)]

        strong = summaries(session.demonstrated_kc_ids)
        gaps = summaries(session.gap_kc_ids)
        starting = summaries(starting_ids[:3])
        return PlacementReport(
            grade_band=session.grade_band,
            probed_count=len(session.probes),
            strong_kcs=strong,
            gap_kcs=gaps,
            starting_kcs=starting,
            display_summary=self._display_summary(
                strong=strong, gaps=gaps, starting=starting
            ),
        )

    def _display_summary(
        self,
        *,
        strong: list[PlacementKcSummary],
        gaps: list[PlacementKcSummary],
        starting: list[PlacementKcSummary],
    ) -> str:
        parts: list[str] = []
        if strong:
            parts.append(
                "Strong on " + ", ".join(item.name for item in strong[:3]) + "."
            )
        if gaps:
            parts.append(
                "Needs more time with "
                + ", ".join(item.name for item in gaps[:3])
                + "."
            )
        if starting:
            parts.append(
                "We'll start with " + ", ".join(item.name for item in starting) + "."
            )
        if not parts:
            parts.append(
                "We could not gather enough evidence yet; daily sessions will "
                "start at grade level."
            )
        return " ".join(parts)

    # -- helpers --------------------------------------------------------------

    def _profile_for(self, session: PlacementSession) -> LearnerProfile:
        profile = self.profile_store.get(UUID(session.student_id))
        if profile is None:
            profile = LearnerProfile(
                student_id=UUID(session.student_id),
                grade_level=session.grade_band,
            )
            self.profile_store.upsert(profile)
        return profile

    def _state(self, session: PlacementSession) -> PlacementStateResponse:
        pending = self._pending_probe(session)
        return PlacementStateResponse(
            session_id=session.session_id,
            student_id=session.student_id,
            status=session.status,
            grade_band=session.grade_band,
            probe_index=len(session.probes),
            question_budget=session.question_budget,
            current_item=(
                PlacementItemView(kc_id=pending.kc_id, block=pending.block)
                if pending is not None and pending.block is not None
                else None
            ),
            report=(
                self._build_report(session) if session.status == "completed" else None
            ),
        )

    def _emit(
        self, event_type: str, *, student_id: str, payload: dict[str, object]
    ) -> None:
        if self.audit_store is None:
            return
        try:
            self.audit_store.append(
                event_type=event_type,
                status="success",
                student_id=student_id,
                payload=payload,
            )
        except Exception:  # noqa: BLE001 - telemetry must not break placement
            logger.warning("Failed to record placement audit event", exc_info=True)
