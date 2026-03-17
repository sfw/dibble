from __future__ import annotations

from fastapi import APIRouter, status

from dibble.api.common import ApiContext, api_error
from dibble.models.curriculum import (
    CurriculumResource,
    CurriculumResourceUpsert,
    KnowledgeComponent,
    KnowledgeComponentUpsert,
)


def build_curriculum_router(context: ApiContext) -> APIRouter:
    router = APIRouter(prefix="/api")
    services = context.services

    @router.put(
        "/curriculum/resources/{resource_id}",
        response_model=CurriculumResource,
        dependencies=context.deps("editor"),
    )
    def upsert_curriculum_resource(resource_id: str, resource: CurriculumResourceUpsert) -> CurriculumResource:
        if resource_id != resource.resource_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path resource_id must match the resource payload resource_id.",
                code="curriculum_resource_id_mismatch",
            )
        return services.curriculum_store.upsert(resource)

    @router.get("/curriculum/resources", response_model=list[CurriculumResource], dependencies=context.deps("viewer"))
    def list_curriculum_resources() -> list[CurriculumResource]:
        return services.curriculum_store.list()

    @router.put(
        "/knowledge-components/{kc_id}",
        response_model=KnowledgeComponent,
        dependencies=context.deps("editor"),
    )
    def upsert_knowledge_component(kc_id: str, component: KnowledgeComponentUpsert) -> KnowledgeComponent:
        if kc_id != component.kc_id:
            raise api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path kc_id must match the knowledge component payload kc_id.",
                code="knowledge_component_id_mismatch",
            )
        return services.knowledge_component_store.upsert(component)

    @router.get("/knowledge-components", response_model=list[KnowledgeComponent], dependencies=context.deps("viewer"))
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
