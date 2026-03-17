from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import ContentWarmResult, GenerationRequest
from dibble.services.generation_engine import GenerationEngine
from dibble.services.generation_mode_calibration import GenerationModeCalibrator
from dibble.services.generation_request_hydrator import hydrate_target_kc_hints
from dibble.services.protocols import KnowledgeComponentStore, ProfileStore
from dibble.services.progression_ownership import ProgressionOwnershipService


@dataclass(slots=True)
class ContentWarmer:
    profile_store: ProfileStore
    generation_engine: GenerationEngine
    knowledge_component_store: KnowledgeComponentStore | None = None
    generation_mode_calibrator: GenerationModeCalibrator | None = None
    progression_ownership_service: ProgressionOwnershipService | None = None

    def warm(self, requests: list[GenerationRequest]) -> ContentWarmResult:
        generation_ids: list[str] = []
        cache_hits = 0
        cache_misses = 0

        for request in requests:
            profile = self.profile_store.get(request.student_id)
            if profile is None:
                continue
            resolved_request = (
                self.progression_ownership_service.resolve_request(
                    student_id=request.student_id,
                    request=request,
                ).request
                if self.progression_ownership_service is not None
                else request
            )
            enriched_request = hydrate_target_kc_hints(
                request=resolved_request,
                knowledge_component_store=self.knowledge_component_store,
            )
            calibrated_request = (
                self.generation_mode_calibrator.calibrate_request(request=enriched_request)
                if self.generation_mode_calibrator is not None
                else enriched_request
            )
            response = self.generation_engine.generate(profile, calibrated_request)
            if response.generation_id is not None:
                generation_ids.append(response.generation_id)
            if response.generation_metadata and response.generation_metadata.cache_hit:
                cache_hits += 1
            else:
                cache_misses += 1

        return ContentWarmResult(
            total_requests=len(generation_ids),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            generation_ids=generation_ids,
        )
