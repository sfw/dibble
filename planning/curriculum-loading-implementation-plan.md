# Curriculum Loading Implementation Plan

## Current state

The codebase does not have a real curriculum import pipeline today.

- Runtime curriculum storage is flat and record-oriented:
  - [src/dibble/models/curriculum.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/models/curriculum.py)
  - [src/dibble/services/curriculum_store.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/services/curriculum_store.py)
  - [src/dibble/services/knowledge_component_store.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/services/knowledge_component_store.py)
- The API only exposes direct upserts and list endpoints for `CurriculumResource` and `KnowledgeComponent`:
  - [src/dibble/api/curriculum_routes.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/api/curriculum_routes.py)
- Curriculum is already important to runtime behavior:
  - progression/ranking depends on `CurriculumResource` plus KC prerequisites:
    - [src/dibble/services/learner_progression_service.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/services/learner_progression_service.py)
  - retrieval grounds generation against `curriculum_resources` and lazily computes embeddings:
    - [src/dibble/services/rag_retriever.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/services/rag_retriever.py)
    - [src/dibble/services/retrieval/embedding_store.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/services/retrieval/embedding_store.py)
- SQLite only has published runtime tables plus embedding cache:
  - [src/dibble/storage.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/storage.py)
- There is no bulk upload flow, no file parsing, no staging area, no provenance model, no review workflow, and no curriculum admin UI.

## What that means

Right now, Dibble is set up for hand-authored or test-authored curriculum records, not dynamic regional imports.

That is too weak for the target problem:

- curriculum will arrive in PDFs, spreadsheets, Word docs, HTML, vendor JSON, ministry/state portals, and mixed exports
- many inputs will be semi-structured, incomplete, duplicated, or jurisdiction-specific
- direct LLM-to-production writes would be unsafe because curriculum shapes drive progression, retrieval, and downstream pedagogy

So the design should be:

1. ingest into a staging model first
2. use deterministic parsing where possible
3. use LLM extraction/normalization where needed
4. validate aggressively
5. require review or confidence-based publish gates
6. project only published data into the current runtime curriculum tables

## Recommended architecture

### 1. Separate ingestion from runtime

Do not import external files straight into `curriculum_resources` and `knowledge_components`.

Add an ingestion subsystem with its own models and tables:

- `curriculum_import_jobs`
- `curriculum_import_sources`
- `curriculum_import_fragments`
- `curriculum_import_candidates`
- `curriculum_import_reviews`
- `curriculum_packages`

The current runtime tables remain the published projection:

- `curriculum_resources`
- `knowledge_components`
- `curriculum_resource_embeddings`

This lets us keep the existing runtime behavior stable while making ingestion dynamic.

### 2. Introduce a richer canonical curriculum model

The current runtime model is too flat to be the canonical ingest target.

We should add a canonical staging model that can represent:

- jurisdiction
- region/country/state/province
- framework/version/year
- subject
- grade/band
- strand/domain
- unit/module
- standard/expectation/outcome
- learning objective
- knowledge component
- prerequisite relationships
- source excerpts and citations
- confidence and validation state

Recommendation:

- canonical staging model is richer than runtime
- publish step projects staging data down into current `CurriculumResource` and `KnowledgeComponent`

That gives us flexibility for multiple regional formats without forcing the runtime to absorb all upstream complexity immediately.

### 3. Build the import pipeline as explicit stages

Each import should move through durable stages:

1. Source registration
   - upload file, raw text, or source URL
   - compute checksum
   - capture file type, uploader, jurisdiction hints, and import intent

2. Source parsing
   - deterministic parser first:
     - CSV/XLSX
     - JSON
     - HTML
     - plain text
   - document extraction adapters for:
     - PDF
     - DOCX
   - output normalized fragments with page/row/section provenance

3. Structural segmentation
   - break source into chunks likely to map to standards, units, or objectives
   - preserve original ordering and citations

4. LLM normalization
   - transform fragments into canonical staging entities
   - infer relationships:
     - standards -> objectives
     - objectives -> KCs
     - KC prerequisites
     - subject/grade mappings
   - generate concise resource bodies suitable for retrieval/progression

5. Validation
   - schema validation
   - duplicate detection
   - cycle detection in prerequisites
   - required-field validation
   - citation coverage checks
   - confidence scoring

6. Review
   - human review queue for low-confidence or conflicting imports
   - diff against existing published package when updating

7. Publish
   - project approved staging data into runtime `curriculum_resources` and `knowledge_components`
   - rebuild or prewarm embeddings for changed resources

### 4. Use LLMs as constrained extractors, not freeform authors

LLM use is justified here, but it needs hard boundaries.

Recommended LLM responsibilities:

- classify source format and likely region/framework
- extract candidate standards/objectives from messy fragments
- normalize aliases and naming variants
- infer candidate KC decompositions
- draft structured prerequisite relationships
- propose tags and retrieval-friendly summaries

Recommended non-LLM responsibilities:

- file handling
- table parsing
- checksuming
- chunking
- deterministic deduplication
- schema validation
- graph validation
- final publish decisions

Guardrails:

- every extracted entity keeps provenance back to fragment IDs and source excerpts
- every LLM step returns typed JSON only
- every response gets validated and repaired before persistence
- no direct write to published runtime tables from raw LLM output
- low-confidence outputs require review

## Suggested backend design

Create a new ingestion area rather than expanding `curriculum_store.py`.

Suggested file layout:

- `src/dibble/models/curriculum_import.py`
- `src/dibble/services/curriculum_import/`
- `src/dibble/services/curriculum_import/source_registry.py`
- `src/dibble/services/curriculum_import/parser_router.py`
- `src/dibble/services/curriculum_import/parsers/`
- `src/dibble/services/curriculum_import/fragmenter.py`
- `src/dibble/services/curriculum_import/llm_normalizer.py`
- `src/dibble/services/curriculum_import/validators.py`
- `src/dibble/services/curriculum_import/publisher.py`
- `src/dibble/services/curriculum_import/diffing.py`
- `src/dibble/api/curriculum_import_routes.py`

That keeps responsibilities separated and aligns with the repo’s modularity rules.

### API surface

Recommended new endpoints:

- `POST /api/admin/curriculum/imports`
  - create import job from file/url/raw text
- `GET /api/admin/curriculum/imports`
  - list jobs
- `GET /api/admin/curriculum/imports/{job_id}`
  - status, diagnostics, candidate counts
- `GET /api/admin/curriculum/imports/{job_id}/candidates`
  - staged extracted entities
- `POST /api/admin/curriculum/imports/{job_id}/validate`
  - run validation
- `POST /api/admin/curriculum/imports/{job_id}/publish`
  - publish approved package into runtime tables
- `GET /api/admin/curriculum/packages`
  - list published curriculum packages
- `GET /api/admin/curriculum/packages/{package_id}/diff`
  - compare against current published package

Access recommendation:

- upload/inspect: `editor`
- validate/publish: `admin`

## Suggested frontend/admin UX

This should live in the new staff admin area, not setup.

Recommended staff pages:

- `Curriculum imports`
  - upload file / paste text / provide source URL
  - choose region, subject, grade hints
  - see parsing + normalization progress

- `Import review`
  - preview extracted standards/objectives/KCs
  - inspect provenance excerpts
  - resolve duplicates/conflicts
  - approve/reject before publish

- `Published curriculum`
  - current active packages by region/version
  - diff view between package versions
  - publish/rollback controls

Important UX rule:

- never make the operator trust a black box
- always show source evidence, confidence, and what changed

## Data model changes needed before dynamic import will work well

These are the biggest structural gaps in the current runtime model:

1. No first-class learning objective store
   - only `learning_objective_ids` on resources and `parent_lo_id` on KCs
   - this is workable for runtime, but not enough for import/review/versioning

2. No curriculum package/version concept
   - we need to know which region/version a published set belongs to

3. No provenance
   - imported data must retain source evidence

4. No review state
   - we need `draft`, `validated`, `review_required`, `approved`, `published`, `rejected`

5. No async job model
   - LLM-backed import cannot be a single synchronous request

## Embedding/indexing recommendation

Today, embeddings are generated lazily during retrieval.

That is acceptable for the current small runtime, but not for large curriculum imports.

Recommended change:

- on publish, queue embedding generation for all changed curriculum resources
- keep lazy fallback in retrieval for resilience
- track embedding freshness against `source_updated_at`

This avoids first-query latency spikes immediately after a large import.

## MVP scope

The MVP should not try to solve every document type.

MVP recommendation:

- supported inputs:
  - CSV
  - XLSX
  - JSON
  - pasted text
- supported workflow:
  - upload
  - parse
  - LLM normalize into staging
  - validate
  - human review
  - publish
- supported publish target:
  - existing `CurriculumResource`
  - existing `KnowledgeComponent`

Explicitly defer:

- PDF-first automation
- DOCX-first automation
- direct website crawling
- multilingual ontology alignment
- automatic region-to-region equivalency mapping
- fully autonomous publishing

## Phase plan

### Phase 0: groundwork

- add import models and DB tables
- add package/version/provenance concepts
- add admin routes for job lifecycle

### Phase 1: deterministic ingest MVP

- CSV/XLSX/JSON parsers
- staged import job pipeline
- manual review UI
- publish projection into runtime tables

### Phase 2: LLM normalization

- fragmenter
- typed extraction prompts
- validation/repair loop
- confidence scoring
- reviewer evidence views

### Phase 3: richer document support

- PDF and DOCX adapters
- region/framework templates
- alias dictionaries and dedupe tuning

### Phase 4: operational maturity

- background workers
- retry policy
- observability dashboards
- package diffing and rollback
- embedding prewarm queue

## Concrete recommendation for this repo

Start with a two-layer model:

- Layer 1: staging import system for dynamic messy inputs
- Layer 2: existing published runtime curriculum/KC stores for learner-facing logic

That is the safest path because it preserves the current retrieval/progression contracts while giving us room to support many regional formats and LLM-assisted extraction.

## Immediate next implementation slice

If we want the first real build step, do this next:

1. Add `curriculum_import` Pydantic models and SQLite tables.
2. Add `POST /api/admin/curriculum/imports` for raw text/CSV/JSON ingestion.
3. Add a deterministic parser router with no LLM yet.
4. Add a publish projection service that writes the current runtime `CurriculumResource` and `KnowledgeComponent` records.
5. Add a basic admin UI in `/staff` for upload + job review.

That gets us a real import system quickly, while keeping the LLM phase additive instead of foundational.
