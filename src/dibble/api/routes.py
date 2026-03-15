from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from dibble.models.curriculum import CurriculumResource, CurriculumResourceUpsert
from dibble.models.generation import AdaptiveRouteDecision, GenerationRequest, GenerationResponse
from dibble.models.profile import LearnerProfile, ProfileSummary
from dibble.plugins.contracts import RouterPlugin
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.profile_store import SQLiteProfileStore


def build_router(
    profile_store: SQLiteProfileStore,
    curriculum_store: SQLiteCurriculumStore,
    router_service: RouterPlugin,
    generation_engine: GenerationEngine,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @router.put("/api/v1/profiles/{student_id}", response_model=LearnerProfile)
    def upsert_profile(student_id: UUID, profile: LearnerProfile) -> LearnerProfile:
        if student_id != profile.student_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path student_id must match the profile payload student_id.",
            )
        return profile_store.upsert(profile)

    @router.get("/api/v1/profiles/{student_id}", response_model=LearnerProfile)
    def get_profile(student_id: UUID) -> LearnerProfile:
        profile = profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return profile

    @router.get("/api/v1/profiles", response_model=list[str])
    def list_profiles() -> list[str]:
        return profile_store.list_ids()

    @router.get("/api/v1/profiles/{student_id}/summary", response_model=ProfileSummary)
    def get_profile_summary(student_id: UUID) -> ProfileSummary:
        profile = profile_store.get(student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return ProfileSummary.from_profile(profile)

    @router.put("/api/v1/curriculum/resources/{resource_id}", response_model=CurriculumResource)
    def upsert_curriculum_resource(
        resource_id: str,
        resource: CurriculumResourceUpsert,
    ) -> CurriculumResource:
        if resource_id != resource.resource_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path resource_id must match the resource payload resource_id.",
            )
        return curriculum_store.upsert(resource)

    @router.get("/api/v1/curriculum/resources", response_model=list[CurriculumResource])
    def list_curriculum_resources() -> list[CurriculumResource]:
        return curriculum_store.list()

    @router.post("/api/v1/adaptive/decide", response_model=AdaptiveRouteDecision)
    def decide_adaptive_route(request: GenerationRequest) -> AdaptiveRouteDecision:
        profile = profile_store.get(request.student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")
        return router_service.route(profile, request)

    @router.post("/api/v1/adaptive/generate", response_model=GenerationResponse)
    def generate_adaptive_content(request: GenerationRequest) -> GenerationResponse:
        profile = profile_store.get(request.student_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner profile not found.")

        return generation_engine.generate(profile, request)

    return router
