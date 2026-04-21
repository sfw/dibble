from __future__ import annotations

from typing import Protocol

from dibble.models.generation import (
    CurriculumContentKey,
    CurriculumLibraryEntry,
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
