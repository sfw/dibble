from __future__ import annotations

from dataclasses import dataclass

from dibble.models.generation import ContentWarmResult, GenerationRequest
from dibble.services.generation_engine import GenerationEngine
from dibble.services.generation_mode_calibration import GenerationModeCalibrator
from dibble.services.protocols import ProfileStore


@dataclass(slots=True)
class ContentWarmer:
    profile_store: ProfileStore
    generation_engine: GenerationEngine
    generation_mode_calibrator: GenerationModeCalibrator | None = None

    def warm(self, requests: list[GenerationRequest]) -> ContentWarmResult:
        generation_ids: list[str] = []
        cache_hits = 0
        cache_misses = 0

        for request in requests:
            profile = self.profile_store.get(request.student_id)
            if profile is None:
                continue
            calibrated_request = (
                self.generation_mode_calibrator.calibrate_request(request=request)
                if self.generation_mode_calibrator is not None
                else request
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
