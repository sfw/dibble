from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from dibble.models.generation import (
    CurriculumContentKey,
    CurriculumLibraryEntry,
    CurriculumLibraryProvenance,
    CurriculumLibraryStorageScope,
    GeneratedContent,
)
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
    ) -> CurriculumLibraryEntry | None: ...

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry: ...

    def get_fresh(self, *, key: CurriculumContentKey) -> GeneratedContent | None: ...

    def upsert(
        self,
        *,
        key: CurriculumContentKey,
        content: GeneratedContent,
    ) -> GeneratedContent: ...


class CloudLibraryClient(Protocol):
    def lookup(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None: ...


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


class LocalCurriculumContentLibrary:
    """Local-only curriculum library backed by an explicit curriculum-store seam."""

    def __init__(self, store: CurriculumContentLibraryStore) -> None:
        self._store = store

    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None:
        return self._store.get_fresh_entry(key=key)

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry:
        return self._store.upsert_entry(entry=entry)

    def get_fresh(self, *, key: CurriculumContentKey) -> GeneratedContent | None:
        entry = self.get_fresh_entry(key=key)
        return entry.content if entry is not None else None

    def upsert(
        self,
        *,
        key: CurriculumContentKey,
        content: GeneratedContent,
    ) -> GeneratedContent:
        return self.upsert_entry(
            entry=CurriculumLibraryEntry(
                content_key=key,
                content=content,
                storage_scope=CurriculumLibraryStorageScope.local_only,
            )
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

    def get_fresh_entry(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None:
        remote_error: Exception | None = None
        remote_entry: CurriculumLibraryEntry | None = None
        if self.remote_client is not None:
            try:
                remote_entry = self.remote_client.lookup(key=key)
            except Exception as exc:  # pragma: no cover - defensive contract handling
                remote_error = exc
        if remote_entry is not None:
            return self._with_library_provenance(
                remote_entry,
                lookup_status="remote_hit",
                publish_status="remote_available",
                degraded_mode=False,
            )
        local_entry = self.local_client.lookup(key=key)
        if local_entry is None:
            return None
        if remote_error is not None:
            return self._with_library_provenance(
                local_entry,
                lookup_status="remote_lookup_failed_local_fallback",
                publish_status=None,
                degraded_mode=True,
                degraded_reason=str(remote_error),
            )
        if self.remote_client is not None:
            return self._with_library_provenance(
                local_entry,
                lookup_status="remote_miss_local_fallback",
                publish_status=None,
                degraded_mode=False,
            )
        return self._with_library_provenance(
            local_entry,
            lookup_status="local_only",
            publish_status="local_only",
            degraded_mode=False,
        )

    def upsert_entry(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry:
        if not self._is_verified(entry):
            return self._persist_local_entry(
                self._with_library_provenance(
                    entry.model_copy(
                        update={"storage_scope": CurriculumLibraryStorageScope.local_only}
                    ),
                    lookup_status="local_only",
                    publish_status="verification_blocked_local_only",
                    degraded_mode=False,
                )
            )
        stored = self.local_client.publish(entry=entry) or entry
        if self.remote_client is not None:
            try:
                remote_entry = self.remote_client.publish(
                    entry=stored.model_copy(
                        update={"storage_scope": CurriculumLibraryStorageScope.shared_ready}
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive contract handling
                return self._persist_local_entry(
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
            if remote_entry is not None:
                return self._with_library_provenance(
                    remote_entry,
                    lookup_status="remote_hit",
                    publish_status="remote_published",
                    degraded_mode=False,
                )
            return self._persist_local_entry(
                self._with_library_provenance(
                    stored.model_copy(
                        update={"storage_scope": CurriculumLibraryStorageScope.local_only}
                    ),
                    lookup_status="local_only",
                    publish_status="remote_skipped_local_only",
                    degraded_mode=False,
                )
            )
        return self._persist_local_entry(
            self._with_library_provenance(
                stored,
                lookup_status="local_only",
                publish_status="local_only",
                degraded_mode=False,
            )
        )

    def get_fresh(self, *, key: CurriculumContentKey) -> GeneratedContent | None:
        entry = self.get_fresh_entry(key=key)
        return entry.content if entry is not None else None

    def upsert(
        self,
        *,
        key: CurriculumContentKey,
        content: GeneratedContent,
    ) -> GeneratedContent:
        return self.upsert_entry(
            entry=CurriculumLibraryEntry(
                content_key=key,
                content=content,
            )
        ).content

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
