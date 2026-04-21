from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import (
    AdaptiveRouteDecision,
    CurriculumContentKey,
    CurriculumLibraryEntry,
    CurriculumContentRequest,
    GeneratedContent,
    GenerationRequest,
)
from dibble.models.profile import LearnerProfile
from dibble.plugins.contracts import RouterPlugin
from dibble.services.harness.content_library import CurriculumContentLibrary
from dibble.services.harness.policy import (
    HarnessAuthoringPolicy,
    HarnessAuthoringPolicyBuilder,
)
from dibble.services.harness.request_adapter import CurriculumContentRequestAdapter


@dataclass(frozen=True, slots=True)
class PreparedAuthoringRequest:
    policy: HarnessAuthoringPolicy
    curriculum_request: CurriculumContentRequest


@dataclass(slots=True)
class RoutingHarnessFacade:
    router: RouterPlugin

    def decide_route(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
    ) -> AdaptiveRouteDecision:
        return self.router.route(profile, request)


@dataclass(slots=True)
class AuthoringHarnessFacade:
    policy_builder: HarnessAuthoringPolicyBuilder
    request_adapter: CurriculumContentRequestAdapter

    def authoring_policy_for(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
    ) -> HarnessAuthoringPolicy:
        return self.policy_builder.build(
            profile=profile,
            request=request,
            route=route,
        )

    def curriculum_request_for(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
    ) -> CurriculumContentRequest:
        return self.prepare_request_for(
            profile=profile,
            request=request,
            route=route,
        ).curriculum_request

    def prepare_request_for(
        self,
        *,
        profile: LearnerProfile,
        request: GenerationRequest,
        route: AdaptiveRouteDecision,
    ) -> PreparedAuthoringRequest:
        policy = self.authoring_policy_for(
            profile=profile,
            request=request,
            route=route,
        )
        return PreparedAuthoringRequest(
            policy=policy,
            curriculum_request=self.request_adapter.adapt(
                grade_level=profile.grade_level,
                request=request,
                policy=policy,
            ),
        )


@dataclass(slots=True)
class ContentLibraryHarnessFacade:
    library: CurriculumContentLibrary | None = None

    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None:
        if self.library is None:
            return None
        return self.library.get_fresh_entry(key=key)

    def get_fresh(self, *, key: CurriculumContentKey) -> GeneratedContent | None:
        if self.library is None:
            return None
        return self.library.get_fresh(key=key)

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry | None:
        if self.library is None:
            return None
        return self.library.upsert_entry(entry=entry)

    def upsert(
        self,
        *,
        key: CurriculumContentKey,
        content: GeneratedContent,
    ) -> GeneratedContent | None:
        if self.library is None:
            return None
        return self.library.upsert(key=key, content=content)


@dataclass(slots=True)
class GenerationHarnessFacades:
    routing: RoutingHarnessFacade
    authoring: AuthoringHarnessFacade
    content_library: ContentLibraryHarnessFacade
