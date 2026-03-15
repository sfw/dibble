---
author: Technical Architecture Team
classification: Development Handoff
date: '2026-03-14'
version: '1.0'
---

# Specification Delta Analysis: Original vs Revised Adaptive Learning Platform

## Executive Summary

This document provides a comprehensive comparison between the original Adaptive Educational Platform specification and the revised specification. The analysis reveals a **fundamental architectural paradigm shift** from a content recommendation engine to an LLM-powered generative learning platform.

| Dimension | Original System | Revised System | Impact |
|-----------|-----------------|----------------|--------|
| **Architecture Type** | Content recommendation | LLM-powered generation | **Transformative** |
| **Vision Achievement** | ~35% | ~95% | **+60%** |
| **Core Technology** | DKT+BKT knowledge tracing | DKT+BKT + LLM infrastructure | **Additive** |
| **Latency Model** | <100ms selection | <2-4s generation + streaming | **Architectural change** |
| **Content Creation** | Static pools | Dynamic generation | **Paradigm shift** |
| **Personalization Depth** | Knowledge state only | Knowledge + cognitive + affective | **Comprehensive** |

**Critical Finding**: The revised specification requires building an entirely new LLM infrastructure layer that does not exist in the original architecture, representing 12-19 months of additional development work.

## Architecture Paradigm Comparison

## Original Architecture: Content Recommendation Engine

```
[Student Interaction] → [DKT+BKT Update] → [Content Selection] → [CDN Delivery]
       ↓                       ↓                  ↓                  ↓
   <50ms update           Mastery map       DB Query (B-tree)    Static asset
```

**Key Characteristics**:
- Content is **pre-authored** by human experts
- System **selects** from existing content pools
- Latency optimized for **<100ms** response times
- **No LLM infrastructure** present
- **BKT interpretability** for teacher trust

## Revised Architecture: Generative AI Platform

```
[Student Interaction] → [Profile Update] → [Router Decision] → [LLM Generation] → [Validation] → [Delivery]
       ↓                      ↓                 ↓                   ↓                ↓            ↓
   <50ms DKT+BKT       Affective/Cognitive   Thompson        RAG + Prompt      Safety        Streaming
                       traits detection      Sampling        Engineering       Layer
```

**Key Characteristics**:
- Content is **generated on-the-fly** via LLMs
- System **creates** personalized content dynamically
- Latency accepts **2-4s** for generation (with streaming)
- **Full LLM infrastructure** required (orchestration, RAG, prompting)
- **Multi-modal synthesis** capabilities

## Core Architectural Changes

| Component | Original | Revised | Change Type |
|-----------|----------|---------|-------------|
| **Content Source** | Pre-authored pools | LLM generation | **New capability** |
| **Adaptation Speed** | Between modules | Within-session continuous | **Enhanced** |
| **Learner Model** | Knowledge state (DKT+BKT) | Multi-dimensional (knowledge + cognitive + affective + metacognitive) | **Extended** |
| **Routing Algorithm** | Multi-objective optimization | Contextual Thompson Sampling | **Replaced** |
| **Remedial System** | Select from prerequisite pool | Dynamic "step back" content generation | **New capability** |
| **Infrastructure** | Redis/Cassandra/Kafka | + LLM orchestration + Vector store + Prompt framework | **Additive** |

## Detailed Requirement Changes

## Added Requirements (New Capabilities)

### 1. LLM Infrastructure Layer (CRITICAL)
| Requirement ID | Description | Original | Revised | Effort |
|----------------|-------------|----------|---------|--------|
| LLM-001 | LLM orchestration service with model routing | ❌ Absent | ✅ Required | 2 months |
| LLM-002 | Prompt engineering framework with versioning | ❌ Absent | ✅ Required | 1-2 months |
| LLM-003 | RAG pipeline for curriculum-grounded generation | ❌ Absent | ✅ Required | 1-2 months |
| LLM-004 | Content safety/moderation layer | ❌ Absent | ✅ Required | 2-3 months |
| LLM-005 | Streaming response architecture | ❌ Absent | ✅ Required | 1 month |

### 2. Dynamic Content Generation (CRITICAL)
| Requirement ID | Description | Original | Revised | Effort |
|----------------|-------------|----------|---------|--------|
| GEN-001 | On-the-fly explanation generation | ❌ Absent | ✅ Required | 3 months |
| GEN-002 | Practice problem synthesis with IRT calibration | ❌ Absent | ✅ Required | 3 months |
| GEN-003 | Worked example generation with fading | ❌ Absent | ✅ Required | 2 months |
| GEN-004 | Remedial micro-module creation | ❌ Absent | ✅ Required | 4 months |
| GEN-005 | Multi-modal synthesis (diagrams, interactives) | ❌ Absent | ✅ Required | 6 months |

### 3. Enhanced Learner Profiling (HIGH)
| Requirement ID | Description | Original | Revised | Effort |
|----------------|-------------|----------|---------|--------|
| PROF-001 | Cognitive trait assessment (working memory, processing speed) | ❌ Absent | ✅ Required | 4 months |
| PROF-002 | Affective state detection (engagement, frustration, confusion) | ❌ Absent | ✅ Required | 3-4 months |
| PROF-003 | Real-time cognitive load estimation | ❌ Absent | ✅ Required | 3-4 months |
| PROF-004 | Knowledge Component (KC) granularity | LO-level | KC-level | 4-6 months |
| PROF-005 | Metacognitive tracking (confidence calibration) | ❌ Absent | ✅ Required | 2 months |

### 4. Advanced Adaptation (HIGH)
| Requirement ID | Description | Original | Revised | Effort |
|----------------|-------------|----------|---------|--------|
| ADAPT-001 | Contextual Thompson Sampling router | ❌ Absent | ✅ Required | 4-6 months |
| ADAPT-002 | Within-session real-time adaptation | ❌ Absent | ✅ Required | 3-4 months |
| ADAPT-003 | Misconception detection and classification | ❌ Absent | ✅ Required | 4-6 months |
| ADAPT-004 | Automatic "step back" intervention | ❌ Absent | ✅ Required | 3-4 months |
| ADAPT-005 | Conversational/Socratic assessment | ❌ Absent | ✅ Required | 4 months |

## Modified Requirements (Changed Behavior)

| Requirement ID | Description | Original | Revised | Change |
|----------------|-------------|----------|---------|--------|
| MOD-001 | Content personalization mechanism | Selection from 5 tiers | Dynamic difficulty adjustment | **Fundamental** |
| MOD-002 | Latency target for content delivery | <100ms | <2-4s (streaming) | **100x relaxation** |
| MOD-003 | Learning style accommodation | Explicitly rejected | Evidence-based preference detection | **Philosophy refinement** |
| MOD-004 | Remediation approach | Prerequisite LO selection | Targeted KC-level generation | **Granularity increase** |
| MOD-005 | Assessment timing | Between modules | Continuous within-session | **Real-time enhancement** |

## Removed/Deprecated Requirements

| Requirement ID | Description | Original | Revised | Rationale |
|----------------|-------------|----------|---------|-----------|
| DEP-001 | VARK learning style detection | ❌ Considered | ❌ Maintained rejection | Evidence still against efficacy |
| DEP-002 | Static content pool management | ✅ Required | ⚠️ Reduced scope | Shift to generation |
| DEP-003 | Content authoring workflow | ✅ Required | ⚠️ Reduced priority | Less pre-authored content needed |

## API Contract Changes

## New API Endpoints Required

| Endpoint | Method | Purpose | Latency Target |
|----------|--------|---------|----------------|
| `/api/v2/content/generate` | POST | Dynamic content generation | <3s |
| `/api/v2/explanations/generate` | POST | On-demand explanation creation | <2s |
| `/api/v2/problems/generate` | POST | Practice problem synthesis | <2s |
| `/api/v2/remedial/trigger` | POST | Initiate remedial intervention | <5s |
| `/api/v2/learners/{id}/profile/v2` | GET | Extended learner profile | <100ms |
| `/api/v2/learners/{id}/affective` | GET | Real-time affective state | <50ms |
| `/api/v2/router/decide` | POST | Thompson Sampling decision | <100ms |
| `/api/v2/llm/stream` | SSE | Streaming content delivery | <1s first token |

## Modified API Endpoints

| Endpoint | Change Type | Original Behavior | New Behavior |
|----------|-------------|-------------------|--------------|
| `/api/v1/recommendations/next` | Enhanced | Returns content_id from pool | May trigger generation or return static |
| `/api/v1/learners/{id}/knowledge-state` | Extended | Returns DKT+BKT only | Includes cognitive/affective dimensions |
| `/api/v1/content/{id}` | Fallback | Primary delivery method | Fallback to generated content |

## Deprecated API Endpoints

| Endpoint | Rationale | Replacement |
|----------|-----------|-------------|
| `/api/v1/content/search` | Less relevant with generation | `/api/v2/content/generate` |
| `/api/v1/content/variants/{id}` | Replaced by dynamic generation | In-generation variation |

## Data Model Changes

## New Data Entities

### LearnerProfileV2 (Extended Schema)
```json
{
  "profile_metadata": { "version": "2.0", "completeness_score": 0.85 },
  "cognitive_traits": {
    "working_memory_capacity": { "percentile": 45, "confidence": 0.82 },
    "processing_speed": { "percentile": 60, "confidence": 0.78 },
    "spatial_reasoning": { "percentile": 55, "confidence": 0.75 }
  },
  "affective_state": {
    "engagement": { "level": "high", "confidence": 0.88 },
    "frustration": { "level": "low", "confidence": 0.72 },
    "confusion": { "level": "none", "confidence": 0.91 }
  },
  "kc_mastery_map": {
    "KC-4NF-2.1": { "p_mastery": 0.65, "parent_lo": "4.NF.A.1" }
  },
  "learning_preferences": {
    "modality_affinity": { "visual": 0.7, "textual": 0.5 },
    "example_domain_preferences": ["sports", "science"]
  }
}
```

### KnowledgeComponent (New Entity)
```json
{
  "kc_id": "KC-4NF-2.1",
  "name": "Understand multiplication property of equivalence",
  "parent_lo_id": "CCSS.MATH.4.NF.A.1",
  "prerequisite_kcs": ["KC-4NF-1.1", "KC-4NF-1.2"],
  "difficulty": 0.65,
  "estimated_time_minutes": 8
}
```

### GeneratedContent (New Entity)
```json
{
  "generation_id": "gen_123",
  "request_context": { "trigger": "misconception_detected" },
  "content_type": "micro_explanation",
  "body": "generated text...",
  "quality_score": 0.91,
  "validation_passed": true,
  "model_used": "gpt-4o",
  "generation_latency_ms": 1800
}
```

## Modified Data Entities

### LearningObjective (Enhanced)
| Field | Original | Revised | Change |
|-------|----------|---------|--------|
| `knowledge_components` | Absent | Array of KC references | Added |
| `granularity` | LO-level | LO + KC decomposition | Enhanced |
| `prerequisites` | LO-to-LO | LO-to-LO + KC-to-KC | Extended |

### ContentModule (Reduced Importance)
| Field | Original | Revised | Change |
|-------|----------|---------|--------|
| `is_generated` | N/A | Boolean flag | Added |
| `generation_metadata` | N/A | Object reference | Added |
| `authoring_status` | Primary | Secondary to generation | Deprioritized |

## Technology Stack Changes

## New Infrastructure Components

| Component | Technology | Purpose | Cost Impact |
|-----------|------------|---------|-------------|
| **LLM Orchestration Service** | Custom (Python/FastAPI) | Route requests to appropriate models | Medium |
| **Vector Store** | ChromaDB/Pinecone | RAG curriculum grounding | Low-Medium |
| **Prompt Management System** | Custom + Weights & Biases | Version prompts, A/B test | Low |
| **LLM Gateway** | LiteLLM/proxy | Multi-provider abstraction | Low |
| **Streaming Infrastructure** | SSE/WebSocket | Progressive content delivery | Low |
| **Content Validation Pipeline** | Custom + Pydantic | Safety/quality checks | Medium |
| **Affective State Classifier** | PyTorch/ONNX | Real-time emotion detection | Low |
| **Thompson Sampling Engine** | Python/NumPy | Contextual bandit optimization | Low |

## Modified Infrastructure Components

| Component | Original | Revised | Change |
|-----------|----------|---------|--------|
| **API Latency Target** | <100ms | <100ms (routing), <3s (generation) | Dual targets |
| **Caching Strategy** | Hot (Redis) | Hot + Pre-generation cache | Enhanced |
| **CDN Usage** | Primary delivery | Fallback for generated content | Reduced |
| **Database Write Pattern** | Sync (Redis), Async (Cassandra) | + Async generation logging | Extended |
| **GPU Infrastructure** | Triton for DKT only | + LLM inference cluster | **Major addition** |

## Infrastructure Cost Impact

| Category | Original (Annual) | Revised (Annual) | Delta |
|----------|-------------------|------------------|-------|
| GPU Compute | $30K (DKT inference) | $200K (+ LLM generation) | **+$170K** |
| Vector Store | $0 | $60K (RAG) | **+$60K** |
| LLM API Costs | $0 | $150K (generation tokens) | **+$150K** |
| Storage (S3) | $40K | $80K (generated content) | **+$40K** |
| **Total Infrastructure** | **~$200K** | **~$620K** | **+$420K** |

## Implementation Impact Assessment

## Files Requiring Modification (platform-root/)

### High Impact (Architectural Changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `architecture-design.md` | Major update | Add LLM layer, streaming architecture |
| `requirements-spec.md` | Major update | Add generation requirements |
| `tool-source.md` | Partial rewrite | Add LLM client, Thompson Sampling router |
| `src/api/router.py` | Extend | Add generation endpoints |
| `src/models/` | Extend | Add KC models, extended learner profile |
| `src/engines/` | Add | Content generation engine, affective classifier |
| `src/services/llm.py` | **New file** | LLM orchestration service |
| `src/services/rag.py` | **New file** | Retrieval pipeline |

### Medium Impact (Feature Additions)
| File | Change Type | Description |
|------|-------------|-------------|
| `config.yaml` | Extend | Add LLM configuration |
| `docker-compose.yml` | Extend | Add vector store, LLM proxy |
| `requirements.txt` | Extend | Add LLM SDKs (openai, anthropic) |
| `src/repositories/` | Extend | Add vector store repository |
| `tests/` | Extend | Add generation tests |

### Low Impact (Configuration)
| File | Change Type | Description |
|------|-------------|-------------|
| `handoff-inventory.md` | Update | Document new spec sources |
| `evidence-ledger.csv` | Update | Add generation tracking |

## New Files Required

```
platform-root/
├── src/
│   ├── services/
│   │   ├── llm_orchestrator.py      # NEW
│   │   ├── rag_retriever.py         # NEW
│   │   ├── prompt_manager.py        # NEW
│   │   └── content_validator.py     # NEW
│   ├── engines/
│   │   ├── generation_engine.py     # NEW
│   │   ├── thompson_sampler.py      # NEW
│   │   └── affective_classifier.py  # NEW
│   ├── models/
│   │   ├── knowledge_component.py   # NEW
│   │   └── extended_profile.py      # NEW
│   └── api/
│       └── generation_routes.py     # NEW
├── prompts/
│   ├── templates/                   # NEW directory
│   └── versions/                    # NEW directory
└── tests/
    ├── test_generation.py           # NEW
    └── test_affective.py            # NEW
```

## Migration Complexity

| Area | Complexity | Risk | Recommended Approach |
|------|------------|------|---------------------|
| **LLM Integration** | High | High | Phased rollout, fallback chains |
| **KC Decomposition** | Medium | Medium | Parallel to existing LO system |
| **Learner Profile Extension** | Medium | Low | Backward-compatible schema |
| **Router Replacement** | Medium | High | A/B test vs. existing optimizer |
| **Affective Detection** | High | Medium | Start with rule-based, add ML |
| **Streaming Delivery** | Low | Low | Incremental enhancement |

## Change Severity Classification

This section classifies all specification changes by their impact on existing systems, backward compatibility, and migration requirements.

### Severity Summary

| Severity Level | Count | Description |
|----------------|-------|-------------|
| **Breaking** | 5 | Requires migration; affects existing data, APIs, or integrations |
| **Non-Breaking** | 29 | Additive/enhancement; backward compatible additions |
| **Unchanged/N/A** | 7 | No change required or not applicable |

### Breaking Changes (Migration Required)

Breaking changes fundamentally alter existing behavior, data structures, or integration contracts. These require explicit migration planning.

| Req ID | Requirement | Migration Impact | Backward Compatible | Deprecation Notes |
|--------|-------------|------------------|---------------------|-------------------|
| **PROF-004** | Knowledge Component granularity | **Data migration required**: Existing LO-level data must be decomposed into KC-level granularity. Requires new KC taxonomy development and LO-to-KC mapping. | No | LO table structure deprecated; new KC entity becomes primary |
| **ADAPT-001** | Thompson Sampling router | **Configuration migration**: Multi-objective optimizer configuration must be migrated to Thompson Sampling parameters. Router behavior changes from rule-based to probabilistic. | No | Multi-objective optimizer deprecated; A/B testing recommended for transition |
| **ADAPT-004** | Dynamic step-back intervention | **Client integration updates**: Intervention response format changes from `content_id` reference to generated content payload. Clients must handle streaming responses. | No | Static pool fallback deprecated; generation becomes primary |
| **DEP-001** | Static content pool deprioritization | **Integration updates**: Content delivery workflows must be restructured to attempt generation first, fallback to pool. CDN integration paths change. | No | Content pool primary role deprecated; becomes emergency fallback only |
| **DEP-002** | Authoring workflow deprioritization | **Process migration**: Content creation workflows shift from pre-authoring to prompt engineering. Authoring tool users require retraining. | No | Authoring workflow deprecated; replaced by prompt management system |

### Non-Breaking Changes (Additive/Enhancement)

Non-breaking changes extend functionality without affecting existing behavior. These can be deployed incrementally.

#### Core LLM Infrastructure (5 requirements)
All LLM infrastructure additions are **non-breaking** as they introduce new v2 endpoints and services:
- LLM-001 through LLM-005: New orchestration, prompt management, RAG, safety, and streaming components
- **Backward compatibility**: Maintained through v1 endpoint preservation
- **Impact scope**: Backend infrastructure only; no client changes required

#### Content Generation Capabilities (5 requirements)
All generation features are **non-breaking** as they add new API endpoints:
- GEN-001 through GEN-005: Explanation, problem, example, remedial, and multi-modal generation
- **Backward compatibility**: New `/api/v2/content/generate` endpoint; v1 recommendation endpoint unchanged
- **Impact scope**: New service modules; existing code unaffected

#### Enhanced Learner Profiling (4 requirements)
Profile extensions are **non-breaking** through additive schema evolution:
- PROF-001, PROF-002, PROF-003, PROF-005: Cognitive traits, affective state, cognitive load, metacognitive tracking
- **Backward compatibility**: v1 profile endpoint returns subset; v2 endpoint returns extended profile
- **Impact scope**: Learner profile service; additive fields only

#### Advanced Adaptation (3 requirements)
Adaptation enhancements are **non-breaking** as they extend existing behavior:
- ADAPT-002, ADAPT-003, ADAPT-005: Within-session adaptation, misconception detection, conversational assessment
- **Backward compatibility**: Enhanced behavior maintains existing API contracts
- **Impact scope**: Adaptation engine; internal algorithm improvements

#### API Extensions (4 requirements)
All API changes are **non-breaking** through v2 versioning:
- API-001, API-002, API-003, API-004: New generation, remedial, profile v2, and streaming endpoints
- **Backward compatibility**: v1 endpoints preserved; clients opt-in to v2
- **Impact scope**: API layer only; clear migration path

#### Data Model Extensions (3 requirements)
Data changes are **non-breaking** through new entities and additive fields:
- DATA-001, DATA-002, DATA-003: KnowledgeComponent entity, extended LearnerProfile, GeneratedContent entity
- **Backward compatibility**: Existing tables unchanged; new tables/collections added
- **Impact scope**: Data layer; no migration of existing data required

#### Infrastructure Additions (3 requirements)
Infrastructure changes are **non-breaking** as they add parallel capacity:
- INFRA-001, INFRA-002, INFRA-003: GPU cluster expansion, vector store, enhanced caching
- **Backward compatibility**: Existing Redis/Cassandra infrastructure unchanged
- **Impact scope**: Infrastructure layer; additive resources

### Backward Compatibility Matrix

| System Component | Breaking Changes | Non-Breaking Changes | Migration Required |
|------------------|------------------|----------------------|-------------------|
| **API Layer** | 0 | 4 new v2 endpoints | No - v1 preserved |
| **Data Layer** | 1 (KC granularity) | 3 (new entities/fields) | Yes - PROF-004 |
| **Recommendation Engine** | 1 (Thompson Sampling) | 0 | Yes - ADAPT-001 |
| **Intervention Service** | 1 (Dynamic content) | 0 | Yes - ADAPT-004 |
| **Content Delivery** | 1 (Pool deprioritized) | 0 | Yes - DEP-001 |
| **Content Management** | 1 (Authoring deprecated) | 0 | Yes - DEP-002 |
| **Backend Services** | 0 | 14 (new capabilities) | No |
| **Infrastructure** | 0 | 3 (new components) | No |

### Migration Path Recommendations

#### Phase 1: Infrastructure (Months 1-3)
Deploy all non-breaking infrastructure changes:
- LLM infrastructure (LLM-001 through LLM-005)
- Vector store (INFRA-002)
- GPU cluster expansion (INFRA-001)
- New v2 API endpoints (API-001, API-002, API-004)

**Risk**: Low - All changes are additive

#### Phase 2: Data Migration (Months 4-6)
Execute breaking data migration:
- Develop KC taxonomy for top 50 Learning Objectives (PROF-004)
- Create LO-to-KC mapping tables
- Run parallel KC tracking alongside existing LO tracking
- Migrate historical mastery data (optional, can be computed)

**Risk**: Medium - Requires data validation and rollback plan

#### Phase 3: Algorithm Transition (Months 7-9)
Migrate recommendation and intervention systems:
- Deploy Thompson Sampling router alongside multi-objective optimizer (ADAPT-001)
- A/B test router performance; gradual traffic shift
- Update intervention clients to handle generated content (ADAPT-004)
- Implement generation-first content delivery (DEP-001)

**Risk**: High - Behavioral changes affect student experience

#### Phase 4: Deprecation (Months 10-12)
Complete migration and deprecate old systems:
- Retire multi-objective optimizer (post-A/B test validation)
- Deprecate authoring workflow (DEP-002)
- Transition content pool to emergency fallback only (DEP-001)
- Update documentation and client libraries

**Risk**: Medium - Ensure all clients migrated before deprecation

### Deprecation Timeline

| Feature | Deprecation Notice | End of Support | Migration Deadline |
|---------|-------------------|----------------|-------------------|
| Multi-objective optimizer | Month 7 | Month 15 | Month 12 |
| Static content pool (primary) | Month 1 | Month 18 | Month 12 |
| Content authoring workflow | Month 1 | Month 12 | Month 10 |
| v1 profile endpoints | Month 12 | Month 24 | Month 18 |
| LO-only granularity | Month 4 | Month 18 | Month 12 |

## Risk and Dependency Analysis

## Critical Path Dependencies

```
Phase 1: LLM Infrastructure (Months 1-3)
├─ LLM orchestration service [CRITICAL]
├─ RAG pipeline [CRITICAL]
└─ Prompt framework [CRITICAL]
        ↓
Phase 2: Generation Capabilities (Months 4-6)
├─ Explanation generator [DEPENDS: Phase 1]
├─ Problem generator [DEPENDS: Phase 1]
└─ Validation pipeline [DEPENDS: Generation]
        ↓
Phase 3: Advanced Features (Months 7-12)
├─ Remedial system [DEPENDS: Generation]
├─ Thompson Sampling [DEPENDS: Affective/Cognitive]
└─ Multi-modal [DEPENDS: Generation]
```

## Risk Factors

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **LLM hallucination** | High | Critical | RAG grounding, validation pipeline, human review |
| **Latency degradation** | High | High | Streaming, pre-generation, fallback chains |
| **Cost overrun** | Medium | High | Model tiering, caching, usage quotas |
| **Content quality inconsistency** | Medium | High | Automated QA, teacher feedback loop |
| **Privacy concerns** | Low | High | Transparency, opt-in, on-device processing |
| **Teacher adoption** | Medium | Medium | Explainability, override controls |

## Go/No-Go Decision Criteria

| Gate | Criteria | Measurement |
|------|----------|-------------|
| **Gate 1** (Month 6) | LLM infra <3s latency, >95% validation pass | Performance metrics |
| **Gate 2** (Month 12) | Affective >75% accuracy, KC decomposition complete | Model validation |
| **Gate 3** (Month 18) | Remedial >70% success, learning gains +15% | Efficacy study |
| **Gate 4** (Month 24) | <2s streaming, 99.99% uptime | Production readiness |

## Requirement Traceability Analysis

This section establishes bidirectional traceability between original requirements (from `platform-root/requirements-spec.md` and `planning/adaptive-ed-platform-research/requirements-backlog.csv`) and the revised specification requirements.

### Traceability Methodology

| Traceability Type | Description | Count |
|-------------------|-------------|-------|
| **Direct Mapping** | Revised requirement directly extends/modifies an original requirement | 24 |
| **Deferred→Active** | Original deferred requirement now activated (e.g., REQ-020 AI tutor) | 3 |
| **New Capability** | No corresponding original requirement; entirely new functionality | 5 |
| **Unchanged** | Original requirement maintained without modification | 4 |
| **Deprioritized** | Original requirement reduced in priority or deprecated | 2 |

### Orphaned Original Requirements

The following original requirements have **no direct mapping** to the revised specification and are considered orphaned:

| Original Req ID | Description | Status | Rationale |
|-----------------|-------------|--------|-----------|
| **REQ-004** | Full keyboard navigation and screen reader support | ⚠️ Partially Orphaned | Accessibility requirements (REQ-004) maintained but refined; WCAG 2.1 AA compliance still required |
| **REQ-005** | Text-to-speech on all content | ⚠️ Partially Orphaned | TTS requirement maintained but implementation shifts to support generated content |
| **REQ-006** | Cognate highlighting for ELL students | 🔴 Fully Orphaned | ELL-specific feature not addressed in revised spec; may require explicit scope decision |
| **REQ-009** | Verifiable parental consent workflow (COPPA) | 🟡 Maintained | Compliance requirement implicitly maintained but not explicitly re-documented |
| **REQ-010** | FERPA-compliant Data Protection Agreements | 🟡 Maintained | Compliance requirement implicitly maintained but not explicitly re-documented |
| **REQ-012** | Growth mindset progress visualization | 🔴 Fully Orphaned | Student motivation feature not carried forward; consider for Phase 2 |
| **REQ-014** | District-wide learning analytics | 🔴 Fully Orphaned | Analytics requirement not explicitly addressed in revised spec |
| **REQ-015** | Weekly parent progress summaries | 🔴 Fully Orphaned | Parent engagement feature not carried forward |
| **REQ-016** | IEP goal progress monitoring | 🔴 Fully Orphaned | SPED compliance feature not explicitly addressed |
| **REQ-018** | Interoperability (LTI/Clever/OneRoster) | 🟡 Maintained | Integration requirements implicitly maintained |
| **REQ-019** | Native language diagnostics | 🔴 Fully Orphaned | ELL feature deferred; not in revised scope |
| **NFR-001** | 99.9% uptime during school hours | 🟡 Maintained | Reliability requirement implicitly maintained |
| **NFR-002** | AES-256 encryption at rest/TLS 1.3 | 🟡 Maintained | Security requirement implicitly maintained |
| **NFR-003** | WCAG 2.1 Level AA compliance | 🟡 Maintained | Accessibility requirement implicitly maintained |
| **NFR-007** | Differential privacy for analytics | 🔴 Fully Orphaned | Advanced privacy feature not in revised scope |

**Recommendation**: Review orphaned requirements marked 🔴 to determine if they should be:
1. Explicitly added back to revised scope
2. Deferred to future phase
3. Formally deprecated with stakeholder approval

### Newly Introduced Capabilities

The following capabilities are **entirely new** with no corresponding original requirement:

| New Req ID | Capability | Original Gap | Strategic Value |
|------------|------------|--------------|-----------------|
| **PROF-001** | Cognitive trait assessment (working memory, processing speed) | Not in original scope | Enables capacity-aware personalization |
| **PROF-002** | Affective state detection (engagement, frustration, confusion) | Not in original scope | Drives real-time intervention triggers |
| **PROF-003** | Real-time cognitive load estimation | Not in original scope | CLT-based difficulty adjustment |
| **PROF-005** | Metacognitive tracking | Not in original scope | Self-regulation support |
| **INFRA-002** | Vector store for RAG | Not in original scope | Curriculum-grounded generation |

**Strategic Note**: The 4 new profiling capabilities (PROF-001/002/003/005) represent a significant expansion beyond knowledge-state-only personalization, addressing the 22 identified gaps from the gap analysis.

### Quick Reference: Requirement Mapping Table

| Original Req | Original Description | Revised Mapping | Change Type |
|--------------|---------------------|-----------------|-------------|
| REQ-001 | BKT/DKT knowledge tracing | SEQ-003, SEQ-004, GEN-002, ADAPT-002 | Extended |
| REQ-002 | Spaced repetition | SEQ-002, ADAPT-002 | Extended |
| REQ-003 | Mastery with remediation | GEN-001, GEN-003, GEN-004, ADAPT-004 | Enhanced |
| REQ-007 | Teacher at-risk dashboard | API-003, DATA-002 | Extended |
| REQ-008 | Standards-based assignment | PROF-004, DATA-001 | Enhanced |
| REQ-011 | Content authoring | DEP-001, DEP-002 | Deprioritized |
| REQ-013 | High-achiever enrichment | GEN-005 | Extended |
| REQ-017 | Performance (200ms latency) | MOD-001, LLM-005 | Modified |
| REQ-020 | AI tutor (deferred) | LLM-001/002/004, ADAPT-005 | Activated |
| NFR-004 | Scalability (1M users) | INFRA-003 | Extended |
| NFR-005 | ML accuracy (AUC ≥ 0.85) | INFRA-001 | Extended |
| NFR-006 | Latency targets | LLM-005, MOD-001 | Modified |

## Summary and Recommendations

## Key Takeaways

1. **Fundamental Paradigm Shift**: The revised specification transforms the system from content selection to content generation, requiring entirely new infrastructure.

2. **Significant Investment Required**: Estimated 18-24 months and $2.0M-$3.2M to achieve full vision, with LLM infrastructure as the critical path.

3. **Architectural Additions, Not Replacements**: The existing DKT+BKT knowledge tracing remains valuable and should be extended, not replaced.

4. **Latency Model Change**: The system must accommodate 100x latency increase (100ms → 2-4s) through streaming and progressive delivery.

5. **Evidence-Based Evolution**: The revised spec maintains rejection of learning styles while adding evidence-based cognitive and affective profiling.

## Immediate Next Steps

1. **Prototype LLM Integration** (Month 1-2): Validate latency and quality assumptions with limited pilot
2. **KC Taxonomy Development** (Month 1-4): Decompose top 50 Learning Objectives for pilot
3. **Infrastructure Provisioning** (Month 1-2): GPU cluster, vector store setup
4. **Safety Framework** (Month 2-3): Content moderation, bias detection, teacher override design
5. **A/B Testing Infrastructure** (Month 3-4): Enable comparison of generated vs. static content

## Success Metrics for Development Team

| Phase | Technical Metric | Target |
|-------|-----------------|--------|
| Phase 1 | LLM generation latency (p95) | <3s |
| Phase 1 | Content validation pass rate | >95% |
| Phase 2 | Affective classification F1 | >0.75 |
| Phase 2 | KC mastery prediction AUC | >0.85 |
| Phase 3 | Remedial intervention success | >70% |
| Phase 3 | Learning gain improvement | +15% vs baseline |
| Phase 4 | System availability | 99.99% |
| Phase 4 | Concurrent user capacity | 100K |
