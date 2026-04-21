from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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

    def lookup(
        self,
        *,
        key: CurriculumContentKey,
    ) -> CurriculumLibraryEntry | None:
        return None

    def publish(
        self,
        *,
        entry: CurriculumLibraryEntry,
    ) -> CurriculumLibraryEntry | None:
        return None


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
