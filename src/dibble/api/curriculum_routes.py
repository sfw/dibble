from __future__ import annotations

from fastapi import APIRouter, status

from dibble.api.common import ApiContext, api_error
from dibble.models.curriculum import (
    KnowledgeComponent,
    KnowledgeComponentUpsert,
    Outcome,
    OutcomeUpsert,
    Strand,
    StrandUpsert,
)


def build_curriculum_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    # ------------------------------------------------------------------
    # Strand endpoints
    # ------------------------------------------------------------------

    @router.put(
        "/curriculum/strands/{strand_id}",
        response_model=Strand,
        dependencies=context.deps("editor"),
    )
    def upsert_strand(strand_id: str, strand: StrandUpsert) -> Strand:
        if strand_id != strand.strand_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path strand_id must match the strand payload strand_id.",
                code="strand_id_mismatch",
            )
        return services.strand_store.upsert(strand)

    @router.get(
        "/curriculum/strands/{strand_id}",
        response_model=Strand,
        dependencies=context.deps("viewer"),
    )
    def get_strand(strand_id: str) -> Strand:
        strand = services.strand_store.get(strand_id)
        if strand is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Strand not found.",
                code="strand_not_found",
            )
        return strand

    @router.get(
        "/curriculum/strands/",
        response_model=list[Strand],
        dependencies=context.deps("viewer"),
    )
    def list_strands() -> list[Strand]:
        return services.strand_store.list()

    @router.get(
        "/curriculum/strands/course/{course_id}",
        response_model=list[Strand],
        dependencies=context.deps("viewer"),
    )
    def list_strands_for_course(course_id: str) -> list[Strand]:
        return services.strand_store.list_for_course(course_id)

    # ------------------------------------------------------------------
    # Outcome endpoints
    # ------------------------------------------------------------------

    @router.put(
        "/curriculum/outcomes/{outcome_id}",
        response_model=Outcome,
        dependencies=context.deps("editor"),
    )
    def upsert_outcome(outcome_id: str, outcome: OutcomeUpsert) -> Outcome:
        if outcome_id != outcome.outcome_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path outcome_id must match the outcome payload outcome_id.",
                code="outcome_id_mismatch",
            )
        return services.outcome_store.upsert(outcome)

    @router.get(
        "/curriculum/outcomes",
        response_model=list[Outcome],
        dependencies=context.deps("viewer"),
    )
    def list_outcomes() -> list[Outcome]:
        return services.outcome_store.list()

    # ------------------------------------------------------------------
    # Knowledge component endpoints
    # ------------------------------------------------------------------

    @router.put(
        "/knowledge-components/{kc_id}",
        response_model=KnowledgeComponent,
        dependencies=context.deps("editor"),
    )
    def upsert_knowledge_component(
        kc_id: str, component: KnowledgeComponentUpsert
    ) -> KnowledgeComponent:
        if kc_id != component.kc_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path kc_id must match the knowledge component payload kc_id.",
                code="knowledge_component_id_mismatch",
            )
        return services.knowledge_component_store.upsert(component)

    @router.get(
        "/knowledge-components",
        response_model=list[KnowledgeComponent],
        dependencies=context.deps("viewer"),
    )
    def list_knowledge_components() -> list[KnowledgeComponent]:
        return services.knowledge_component_store.list()

    @router.get(
        "/knowledge-components/{kc_id}/prerequisites",
        response_model=list[KnowledgeComponent],
        dependencies=context.deps("viewer"),
    )
    def list_knowledge_component_prerequisites(kc_id: str) -> list[KnowledgeComponent]:
        component = services.knowledge_component_store.get(kc_id)
        if component is None:
            raise api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge component not found.",
                code="knowledge_component_not_found",
            )
        return services.knowledge_component_store.list_prerequisites(kc_id)

    return router
