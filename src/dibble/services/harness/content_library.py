from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from dibble.models.generation import (
    CurriculumContentKey,
    CurriculumLibraryCandidateRanking,
    CurriculumLibraryEntry,
    CurriculumLibraryProvenance,
    CurriculumLibrarySelectionTrace,
    CurriculumLibraryStorageScope,
    GeneratedContent,
    AdaptiveScoreComponent,
)
from dibble.models.observability import HarnessBoundary, OperationalTraceStatus
from dibble.models.rollout import (
    CloudLibraryPublishMode,
    CloudLibraryReadMode,
    RolloutCapability,
)
from dibble.services.operational_observability import OperationalObservabilityService
from dibble.services.rollout_decision_service import RolloutDecisionService
from dibble.services.protocols import (
    CurriculumContentLibraryStore,
    GeneratedContentStore,
)

_CURRICULUM_LIBRARY_STUDENT_ID = UUID("00000000-0000-0000-0000-000000000000")
_SAFE_LIBRARY_REQUEST_CONTEXT_KEYS = frozenset(
    {
        "selected_content_type",
        "curriculum_cache_key",
        "library_storage_scope",
        "selected_modality",
        "modality_plugin_id",
        "modality_composition_mode",
        "selected_modalities",
    }
)


class CurriculumContentLibrary(Protocol):
    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
        learner_id: str | None = None,
    ) -> CurriculumLibraryEntry | None: ...

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
        learner_id: str | None = None,
    ) -> CurriculumLibraryEntry: ...

    def get_fresh(
        self, *, key: CurriculumContentKey, learner_id: str | None = None
    ) -> GeneratedContent | None: ...

    def upsert(
        self,
        *,
        key: CurriculumContentKey,
        content: GeneratedContent,
        learner_id: str | None = None,
    ) -> GeneratedContent: ...


class CloudLibraryClient(Protocol):
    def lookup(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None: ...

    def list_candidates(
        self,
        *,
        key: CurriculumContentKey,
        limit: int = 20,
    ) -> list[CurriculumLibraryEntry]: ...


@dataclass(frozen=True, slots=True)
class CloudLibraryTransportResponse:
    status_code: int
    payload: dict[str, Any] | None = None
    text: str = ""


class CloudLibraryTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> CloudLibraryTransportResponse: ...


@dataclass(slots=True)
class UrllibCloudLibraryTransport:
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> CloudLibraryTransportResponse:
        body = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else None
        )
        request = Request(url=url, data=body, method=method.upper())
        for key, value in headers.items():
            request.add_header(key, value)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
                return CloudLibraryTransportResponse(
                    status_code=int(getattr(response, "status", 200)),
                    payload=_parse_json_payload(raw_body),
                    text=raw_body,
                )
        except HTTPError as exc:
            raw_body = exc.read().decode("utf-8") if exc.fp is not None else ""
            return CloudLibraryTransportResponse(
                status_code=exc.code,
                payload=_parse_json_payload(raw_body),
                text=raw_body,
            )
        except URLError as exc:  # pragma: no cover - exercised through callers
            raise RuntimeError(str(exc.reason)) from exc

    def publish(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry | None: ...


class GeneratedContentBackedCurriculumLibraryStore:
    """Transitional local curriculum store backed by learner-scoped content rows."""

    def __init__(self, generated_content_store: GeneratedContentStore) -> None:
        self._generated_content_store = generated_content_store

    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
        learner_id: str | None = None,
    ) -> CurriculumLibraryEntry | None:
        content = self._generated_content_store.get_fresh(cache_key=key.cache_key())
        if content is None:
            return None
        return CurriculumLibraryEntry(
            content_key=key,
            content=content,
            storage_scope=CurriculumLibraryStorageScope.local_only,
        )

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
        learner_id: str | None = None,
    ) -> CurriculumLibraryEntry:
        persisted = self._generated_content_store.upsert(
            cache_key=entry.cache_key,
            content=entry.content,
        )
        return entry.model_copy(
            update={
                "content": persisted,
                "source_generation_id": persisted.generation_id,
            }
        )

    def list_candidate_entries(
        self,
        *,
        key: CurriculumContentKey,
        limit: int = 20,
    ) -> list[CurriculumLibraryEntry]:
        exact = self.get_fresh_entry(key=key)
        return [exact] if exact is not None else []

    def record_outcome(
        self,
        *,
        source_generation_id: str,
        outcome_score: float,
        engagement_score: float | None,
        progress_score: float | None,
    ) -> list[CurriculumLibraryEntry]:
        return []


class LocalCurriculumContentLibrary:
    """Local-only curriculum library backed by an explicit curriculum-store seam."""

    def __init__(self, store: CurriculumContentLibraryStore) -> None:
        self._store = store

    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
        learner_id: str | None = None,
    ) -> CurriculumLibraryEntry | None:
        return self._store.get_fresh_entry(key=key)

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
        learner_id: str | None = None,
    ) -> CurriculumLibraryEntry:
        return self._store.upsert_entry(entry=entry)

    def list_candidate_entries(
        self,
        *,
        key: CurriculumContentKey,
        limit: int = 20,
    ) -> list[CurriculumLibraryEntry]:
        return self._store.list_candidate_entries(key=key, limit=limit)

    def record_outcome(
        self,
        *,
        source_generation_id: str,
        outcome_score: float,
        engagement_score: float | None,
        progress_score: float | None,
    ) -> list[CurriculumLibraryEntry]:
        return self._store.record_outcome(
            source_generation_id=source_generation_id,
            outcome_score=outcome_score,
            engagement_score=engagement_score,
            progress_score=progress_score,
        )

    def get_fresh(
        self, *, key: CurriculumContentKey, learner_id: str | None = None
    ) -> GeneratedContent | None:
        entry = self.get_fresh_entry(key=key, learner_id=learner_id)
        return entry.content if entry is not None else None

    def upsert(
        self,
        *,
        key: CurriculumContentKey,
        content: GeneratedContent,
        learner_id: str | None = None,
    ) -> GeneratedContent:
        return self.upsert_entry(
            entry=CurriculumLibraryEntry(
                content_key=key,
                content=content,
                storage_scope=CurriculumLibraryStorageScope.local_only,
            ),
            learner_id=learner_id,
        ).content


@dataclass(slots=True)
class LocalStubCloudLibraryClient:
    store: CurriculumContentLibraryStore

    def lookup(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None:
        return self.store.get_fresh_entry(key=key)

    def list_candidates(
        self,
        *,
        key: CurriculumContentKey,
        limit: int = 20,
    ) -> list[CurriculumLibraryEntry]:
        try:
            return self.store.list_candidate_entries(key=key, limit=limit)
        except Exception:
            return []

    def publish(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry | None:
        persisted_entry = entry
        if persisted_entry.source_generation_id is None:
            persisted_entry = persisted_entry.model_copy(
                update={"source_generation_id": persisted_entry.content.generation_id}
            )
        return self.store.upsert_entry(entry=persisted_entry)


@dataclass(slots=True)
class RemoteReadyCloudLibraryClient:
    endpoint: str | None = None
    enabled: bool = False
    api_key: str | None = None
    timeout_seconds: float = 5.0
    retry_attempts: int = 2
    transport: CloudLibraryTransport = field(
        default_factory=UrllibCloudLibraryTransport
    )

    def lookup(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None:
        if not self.enabled or not self.endpoint:
            return None
        payload = {
            "cache_key": key.cache_key(),
            "content_key": key.model_dump(mode="json"),
        }
        response = self._request_with_retry(
            method="POST",
            path="/lookup",
            payload=payload,
            miss_status_codes={204, 404},
        )
        if response is None:
            return None
        entry_payload = (
            response.payload.get("entry", response.payload)
            if response.payload is not None
            else None
        )
        if not isinstance(entry_payload, dict):
            return None
        return self._sanitize_remote_entry(
            CurriculumLibraryEntry.model_validate(entry_payload)
        )

    def publish(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry | None:
        if not self.enabled or not self.endpoint:
            return None
        sanitized_entry = self._sanitize_remote_entry(entry)
        response = self._request_with_retry(
            method="POST",
            path="/publish",
            payload={
                "entry": sanitized_entry.model_dump(mode="json"),
            },
            miss_status_codes=set(),
        )
        entry_payload = (
            response.payload.get("entry", response.payload)
            if response is not None and response.payload is not None
            else None
        )
        if not isinstance(entry_payload, dict):
            return sanitized_entry
        return self._sanitize_remote_entry(
            CurriculumLibraryEntry.model_validate(entry_payload)
        )

    def list_candidates(
        self,
        *,
        key: CurriculumContentKey,
        limit: int = 20,
    ) -> list[CurriculumLibraryEntry]:
        entry = self.lookup(key=key)
        return [entry] if entry is not None else []

    def _request_with_retry(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any],
        miss_status_codes: set[int],
    ) -> CloudLibraryTransportResponse | None:
        last_error: Exception | None = None
        max_attempts = max(1, self.retry_attempts)
        for attempt in range(max_attempts):
            try:
                response = self.transport.request(
                    method=method,
                    url=f"{self.endpoint.rstrip('/')}{path}",
                    headers=self._headers(),
                    payload=payload,
                    timeout_seconds=self.timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                if attempt + 1 >= max_attempts:
                    raise RuntimeError(f"cloud library {path} failed: {exc}") from exc
                continue
            if response.status_code in miss_status_codes:
                return None
            if 200 <= response.status_code < 300:
                return response
            if _should_retry_status(response.status_code) and attempt + 1 < max_attempts:
                continue
            detail = response.text.strip() or f"HTTP {response.status_code}"
            raise RuntimeError(f"cloud library {path} failed: {detail}")
        if last_error is not None:
            raise RuntimeError(f"cloud library {path} failed: {last_error}") from last_error
        return None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _sanitize_remote_entry(self, entry: CurriculumLibraryEntry) -> CurriculumLibraryEntry:
        sanitized_response = entry.content.response.model_copy(
            update={"student_id": _CURRICULUM_LIBRARY_STUDENT_ID}
        )
        sanitized_content = entry.content.model_copy(
            update={
                "student_id": _CURRICULUM_LIBRARY_STUDENT_ID,
                "request_context": {
                    key: value
                    for key, value in entry.content.request_context.items()
                    if key in _SAFE_LIBRARY_REQUEST_CONTEXT_KEYS
                },
                "response": sanitized_response,
            }
        )
        return entry.model_copy(update={"content": sanitized_content})


@dataclass(slots=True)
class LibraryFirstCurriculumContentLibrary:
    local_client: CloudLibraryClient
    remote_client: CloudLibraryClient | None = None
    observability_service: OperationalObservabilityService | None = None
    rollout_decision_service: RolloutDecisionService | None = None

    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
        learner_id: str | None = None,
    ) -> CurriculumLibraryEntry | None:
        read_decision = (
            self.rollout_decision_service.decision_for(
                capability=RolloutCapability.cloud_library_remote_read,
                learner_id=learner_id,
            )
            if self.rollout_decision_service is not None
            else None
        )
        remote_error: Exception | None = None
        remote_entry: CurriculumLibraryEntry | None = None
        remote_allowed = (
            read_decision is None
            or read_decision.mode == CloudLibraryReadMode.remote_preferred.value
        )
        if self.remote_client is not None and remote_allowed:
            try:
                remote_entry = self.remote_client.lookup(key=key)
            except Exception as exc:  # pragma: no cover - defensive contract handling
                remote_error = exc
        candidates = self._candidate_entries_for(
            key=key,
            remote_entry=remote_entry,
            remote_error=remote_error,
        )
        if not candidates:
            return None
        selected = self.inspect_selection(
            key=key,
            candidates=candidates,
        ).selected_cache_key
        entry = next(
            (entry for entry in candidates if entry.cache_key == selected),
            candidates[0],
        )
        provenance = entry.provenance
        degraded_mode = bool(provenance.degraded_mode) if provenance is not None else False
        reason_code = provenance.lookup_status if provenance is not None else None
        self._record_trace(
            operation="lookup",
            status=(
                OperationalTraceStatus.degraded
                if degraded_mode
                else OperationalTraceStatus.success
            ),
            summary=(
                "Selected local curriculum library fallback after remote lookup degraded."
                if degraded_mode
                else "Selected curriculum library artifact."
            ),
            degraded_mode=degraded_mode,
            degraded_reason=provenance.degraded_reason if provenance is not None else None,
            fallback_kind=(
                "local_library_fallback"
                if degraded_mode or reason_code == "remote_miss_local_fallback"
                else None
            ),
            fallback_provenance=reason_code,
            reason_code=reason_code,
            payload={
                "cache_key": entry.cache_key,
                "selection_key": key.selection_key(),
                "remote_enabled": self.remote_client is not None,
                "rollout_bucket_id": (
                    read_decision.evaluation_bucket_id if read_decision is not None else None
                ),
                "rollout_mode": read_decision.mode if read_decision is not None else None,
                "rollout_policy_reason": (
                    read_decision.rationale if read_decision is not None else []
                ),
            },
        )
        return entry

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
        learner_id: str | None = None,
    ) -> CurriculumLibraryEntry:
        publish_decision = (
            self.rollout_decision_service.decision_for(
                capability=RolloutCapability.cloud_library_remote_publish,
                learner_id=learner_id,
            )
            if self.rollout_decision_service is not None
            else None
        )
        if not self._is_verified(entry):
            persisted = self._persist_local_entry(
                self._with_library_provenance(
                    entry.model_copy(
                        update={"storage_scope": CurriculumLibraryStorageScope.local_only}
                    ),
                    lookup_status="local_only",
                    publish_status="verification_blocked_local_only",
                    degraded_mode=True,
                    degraded_reason="Content verification blocked remote publication.",
                )
            )
            self._record_trace(
                operation="publish",
                status=OperationalTraceStatus.degraded,
                summary="Skipped shared publication because generated content failed verification.",
                degraded_mode=True,
                degraded_reason="Content verification blocked remote publication.",
                fallback_kind="local_only_hold",
                fallback_provenance="verification_blocked_local_only",
                reason_code="verification_blocked_local_only",
                payload={
                    "cache_key": persisted.cache_key,
                    "selection_key": persisted.content_key.selection_key(),
                    "rollout_bucket_id": (
                        publish_decision.evaluation_bucket_id
                        if publish_decision is not None
                        else None
                    ),
                },
            )
            return persisted
        stored = self.local_client.publish(entry=entry) or entry
        remote_allowed = (
            publish_decision is None
            or publish_decision.mode == CloudLibraryPublishMode.remote_verified.value
        )
        if self.remote_client is not None and remote_allowed:
            try:
                remote_entry = self.remote_client.publish(
                    entry=stored.model_copy(
                        update={"storage_scope": CurriculumLibraryStorageScope.shared_ready}
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive contract handling
                persisted = self._persist_local_entry(
                    self._with_library_provenance(
                        stored.model_copy(
                            update={"storage_scope": CurriculumLibraryStorageScope.local_only}
                        ),
                        lookup_status="local_only",
                        publish_status="remote_publish_failed_local_only",
                        degraded_mode=True,
                        degraded_reason=str(exc),
                    )
                )
                self._record_trace(
                    operation="publish",
                    status=OperationalTraceStatus.degraded,
                    summary="Remote cloud library publish failed and the artifact was retained locally.",
                    degraded_mode=True,
                    degraded_reason=str(exc),
                    fallback_kind="local_only_hold",
                    fallback_provenance="remote_publish_failed_local_only",
                    reason_code="remote_publish_failed_local_only",
                    payload={
                        "cache_key": persisted.cache_key,
                        "selection_key": persisted.content_key.selection_key(),
                        "remote_enabled": True,
                        "rollout_bucket_id": (
                            publish_decision.evaluation_bucket_id
                            if publish_decision is not None
                            else None
                        ),
                    },
                )
                return persisted
            if remote_entry is not None:
                persisted = self._with_library_provenance(
                    remote_entry,
                    lookup_status="remote_hit",
                    publish_status="remote_published",
                    degraded_mode=False,
                )
                self._record_trace(
                    operation="publish",
                    status=OperationalTraceStatus.success,
                    summary="Published curriculum artifact to the remote cloud library.",
                    reason_code="remote_published",
                    payload={
                        "cache_key": persisted.cache_key,
                        "selection_key": persisted.content_key.selection_key(),
                        "remote_enabled": True,
                        "rollout_bucket_id": (
                            publish_decision.evaluation_bucket_id
                            if publish_decision is not None
                            else None
                        ),
                    },
                )
                return persisted
            persisted = self._persist_local_entry(
                self._with_library_provenance(
                    stored.model_copy(
                        update={"storage_scope": CurriculumLibraryStorageScope.local_only}
                    ),
                    lookup_status="local_only",
                    publish_status="remote_skipped_local_only",
                    degraded_mode=False,
                )
            )
            self._record_trace(
                operation="publish",
                status=OperationalTraceStatus.success,
                summary="Remote cloud library skipped publication; local verified copy was retained.",
                fallback_kind="local_only_hold",
                fallback_provenance="remote_skipped_local_only",
                reason_code="remote_skipped_local_only",
                payload={
                    "cache_key": persisted.cache_key,
                    "selection_key": persisted.content_key.selection_key(),
                    "remote_enabled": True,
                    "rollout_bucket_id": (
                        publish_decision.evaluation_bucket_id
                        if publish_decision is not None
                        else None
                    ),
                },
            )
            return persisted
        persisted = self._persist_local_entry(
            self._with_library_provenance(
                stored,
                lookup_status="local_only",
                publish_status=(
                    "rollout_local_only"
                    if publish_decision is not None and not remote_allowed
                    else "local_only"
                ),
                degraded_mode=False,
            )
        )
        self._record_trace(
            operation="publish",
            status=OperationalTraceStatus.success,
            summary="Stored verified curriculum artifact in the local library.",
            reason_code="local_only",
            payload={
                "cache_key": persisted.cache_key,
                "selection_key": persisted.content_key.selection_key(),
                "remote_enabled": False,
                "rollout_bucket_id": (
                    publish_decision.evaluation_bucket_id
                    if publish_decision is not None
                    else None
                ),
                "rollout_mode": (
                    publish_decision.mode if publish_decision is not None else None
                ),
                "rollout_policy_reason": (
                    publish_decision.rationale if publish_decision is not None else []
                ),
            },
        )
        return persisted

    def get_fresh(
        self, *, key: CurriculumContentKey, learner_id: str | None = None
    ) -> GeneratedContent | None:
        entry = self.get_fresh_entry(key=key, learner_id=learner_id)
        return entry.content if entry is not None else None

    def upsert(
        self,
        *,
        key: CurriculumContentKey,
        content: GeneratedContent,
        learner_id: str | None = None,
    ) -> GeneratedContent:
        return self.upsert_entry(
            entry=CurriculumLibraryEntry(
                content_key=key,
                content=content,
            ),
            learner_id=learner_id,
        ).content

    def inspect_selection(
        self,
        *,
        key: CurriculumContentKey,
        candidates: list[CurriculumLibraryEntry] | None = None,
    ) -> CurriculumLibrarySelectionTrace:
        ranked_candidates = candidates or self._candidate_entries_for(
            key=key,
            remote_entry=None,
            remote_error=None,
        )
        requested_modalities = {
            str(item)
            for item in key.request.generation_constraints.get("selected_modalities", [])
            if item
        }
        requested_modality = key.request.generation_constraints.get("selected_modality")
        rankings: list[CurriculumLibraryCandidateRanking] = []
        for entry in ranked_candidates:
            ranking = self._rank_candidate(
                key=key,
                entry=entry,
                requested_modalities=requested_modalities,
                requested_modality=(
                    str(requested_modality) if requested_modality is not None else None
                ),
            )
            rankings.append(ranking)
        rankings.sort(
            key=lambda item: (item.total_score, item.outcome_sample_count, item.cache_key),
            reverse=True,
        )
        selected_cache_key = rankings[0].cache_key if rankings else None
        rankings = [
            item.model_copy(update={"selected": item.cache_key == selected_cache_key})
            for item in rankings
        ]
        return CurriculumLibrarySelectionTrace(
            selection_key=key.selection_key(),
            requested_modality=(
                str(requested_modality) if requested_modality is not None else None
            ),
            selected_cache_key=selected_cache_key,
            candidates=rankings,
        )

    def _is_verified(self, entry: CurriculumLibraryEntry) -> bool:
        return (
            entry.content.quality.validation_passed
            and not entry.content.response.validation_issues
            and entry.content.quality.moderation.status != "flagged"
        )

    def _with_library_provenance(
        self,
        entry: CurriculumLibraryEntry,
        *,
        lookup_status: str,
        publish_status: str | None,
        degraded_mode: bool,
        degraded_reason: str | None = None,
    ) -> CurriculumLibraryEntry:
        provenance = entry.provenance or CurriculumLibraryProvenance(
            source_generation_id=entry.source_generation_id or entry.content.generation_id,
            provider_name=entry.content.quality.provider_name,
            validator_passed=entry.content.quality.validation_passed,
            validation_issues=list(entry.content.response.validation_issues),
            moderation_status=entry.content.quality.moderation.status,
            quality_score=entry.content.quality.quality_score,
            modalities=[
                artifact.provenance.modality
                for artifact in entry.content.response.artifacts
            ],
        )
        return entry.model_copy(
            update={
                "provenance": provenance.model_copy(
                    update={
                        "stored_via": (
                            "remote_cloud_library"
                            if self.remote_client is not None
                            else provenance.stored_via
                        ),
                        "lookup_status": lookup_status,
                        "publish_status": publish_status or provenance.publish_status,
                        "degraded_mode": degraded_mode or provenance.degraded_mode,
                        "degraded_reason": degraded_reason or provenance.degraded_reason,
                        "remote_endpoint": self._remote_endpoint(),
                    }
                )
            }
        )

    def _remote_endpoint(self) -> str | None:
        return (
            getattr(self.remote_client, "endpoint", None)
            if self.remote_client is not None
            else None
        )

    def _persist_local_entry(self, entry: CurriculumLibraryEntry) -> CurriculumLibraryEntry:
        return self.local_client.publish(entry=entry) or entry

    def _record_trace(
        self,
        *,
        operation: str,
        status: OperationalTraceStatus,
        summary: str,
        degraded_mode: bool = False,
        degraded_reason: str | None = None,
        fallback_kind: str | None = None,
        fallback_provenance: str | None = None,
        reason_code: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self.observability_service is None:
            return
        self.observability_service.record_trace(
            harness=HarnessBoundary.content_library,
            operation=operation,
            status=status,
            summary=summary,
            degraded_mode=degraded_mode,
            degraded_reason=degraded_reason,
            fallback_kind=fallback_kind,
            fallback_provenance=fallback_provenance,
            reason_code=reason_code,
            payload=payload,
        )

    def _candidate_entries_for(
        self,
        *,
        key: CurriculumContentKey,
        remote_entry: CurriculumLibraryEntry | None,
        remote_error: Exception | None,
    ) -> list[CurriculumLibraryEntry]:
        candidates: dict[str, CurriculumLibraryEntry] = {}
        if remote_entry is not None:
            enriched_remote = self._with_library_provenance(
                remote_entry,
                lookup_status="remote_hit",
                publish_status="remote_available",
                degraded_mode=False,
            )
            candidates[enriched_remote.cache_key or key.cache_key()] = enriched_remote
        for entry in self.local_client.list_candidates(key=key):
            lookup_status = "local_only"
            publish_status = "local_only"
            degraded_mode = False
            degraded_reason = None
            if remote_error is not None:
                lookup_status = "remote_lookup_failed_local_fallback"
                degraded_mode = True
                degraded_reason = str(remote_error)
            elif self.remote_client is not None:
                lookup_status = "remote_miss_local_fallback"
                publish_status = None
            enriched_local = self._with_library_provenance(
                entry,
                lookup_status=lookup_status,
                publish_status=publish_status,
                degraded_mode=degraded_mode,
                degraded_reason=degraded_reason,
            )
            if enriched_local.cache_key is not None:
                candidates[enriched_local.cache_key] = enriched_local
        return list(candidates.values())

    def _rank_candidate(
        self,
        *,
        key: CurriculumContentKey,
        entry: CurriculumLibraryEntry,
        requested_modalities: set[str],
        requested_modality: str | None,
    ) -> CurriculumLibraryCandidateRanking:
        provenance = entry.provenance or CurriculumLibraryProvenance(
            source_generation_id=entry.source_generation_id or entry.content.generation_id
        )
        now = datetime.now(timezone.utc)
        age_days = max(
            0.0,
            (now - entry.content.created_at).total_seconds() / (60 * 60 * 24),
        )
        freshness = max(0.0, 1.0 - min(age_days / 30.0, 1.0))
        modality_overlap = requested_modalities.intersection(set(provenance.modalities))
        modality_fit = 0.5
        if requested_modality and requested_modality in provenance.modalities:
            modality_fit = 1.0
        elif modality_overlap:
            modality_fit = 0.8
        elif requested_modality:
            modality_fit = 0.25
        outcome_confidence = min(provenance.outcome_sample_count / 3.0, 1.0)
        outcome_score = (
            (provenance.average_outcome_score * outcome_confidence)
            + (0.5 * (1.0 - outcome_confidence))
        )
        total_score = round(
            (provenance.quality_score * 0.42)
            + ((1.0 if provenance.validator_passed else 0.0) * 0.12)
            + (outcome_score * 0.22)
            + (freshness * 0.14)
            + (modality_fit * 0.10),
            2,
        )
        return CurriculumLibraryCandidateRanking(
            cache_key=entry.cache_key or key.cache_key(),
            source_generation_id=entry.source_generation_id,
            total_score=total_score,
            outcome_sample_count=provenance.outcome_sample_count,
            score_components=[
                AdaptiveScoreComponent(
                    label="verifier_quality",
                    value=round(provenance.quality_score * 0.42, 2),
                    detail=(
                        "Verifier quality and validation stay the dominant signal "
                        "until stronger outcome evidence exists."
                    ),
                ),
                AdaptiveScoreComponent(
                    label="historical_outcome",
                    value=round((outcome_score - 0.5) * 0.44, 2),
                    detail=(
                        f"{provenance.outcome_sample_count} outcome sample(s) contribute "
                        "a bounded reuse preference."
                    ),
                ),
                AdaptiveScoreComponent(
                    label="freshness",
                    value=round((freshness - 0.5) * 0.28, 2),
                    detail="Newer curriculum-safe artifacts get a mild freshness bonus.",
                ),
                AdaptiveScoreComponent(
                    label="modality_fit",
                    value=round((modality_fit - 0.5) * 0.20, 2),
                    detail="Requested modality fit is considered, but it does not override safety or quality.",
                ),
            ],
            rationale=[
                f"quality={provenance.quality_score:.2f}",
                f"outcome_avg={provenance.average_outcome_score:.2f}",
                f"freshness={freshness:.2f}",
                f"modality_fit={modality_fit:.2f}",
            ],
        )


def _parse_json_payload(raw_body: str) -> dict[str, Any] | None:
    if not raw_body.strip():
        return None
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600
