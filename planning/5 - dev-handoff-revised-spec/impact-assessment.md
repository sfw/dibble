# Implementation Impact Assessment: Revised Specification vs Platform-Root

## Executive Summary

This document analyzes the impact of the revised adaptive learning platform specification on the existing `platform-root/` AKSRE (Adaptive Knowledge State & Recommendation Engine) codebase. The assessment identifies architectural conflicts, refactoring requirements, and integration changes needed to align with the new LLM-powered generative architecture.

| Impact Dimension | Severity | Status |
|------------------|----------|--------|
| Architecture Paradigm | **Transformative** | Content recommendation → LLM generation |
| Code Reuse Potential | **Moderate** | BKT/DKT engines preserved; new LLM layer required |
| Database Schema | **Breaking** | New KC granularity + extended profile models |
| API Contracts | **Non-Breaking** | v2 endpoints added; v1 preserved |
| Infrastructure | **Additive** | GPU/LLM cluster + vector store required |
| Latency Model | **Changed** | <100ms → dual target (<100ms routing, <3s generation) |

**Key Finding**: The existing AKSRE codebase provides a solid foundation for knowledge state tracking (BKT/DKT) but requires substantial new infrastructure for LLM orchestration, content generation, and affective computing.

## Affected Modules and Services

## High Impact (Architectural Changes Required)

| Module | Current State | Required Changes | Effort |
|--------|---------------|------------------|--------|
| **API Router** (`src/api/router.py`) | v1 endpoints for state/recommendations | Add v2 generation endpoints; streaming support | 2-3 weeks |
| **BKT Engine** (`src/engines/bkt_engine.py`) | LO-level mastery tracking | Extend to KC-level granularity | 3-4 weeks |
| **Recommendation Engine** (`src/api/recommendations.py`) | Multi-objective optimizer | Replace with Thompson Sampling router | 4-6 weeks |
| **Learner Profile** (new) | Knowledge state only | Add cognitive/affective dimensions | 4-6 weeks |
| **LLM Orchestration** (new) | Does not exist | New service layer required | 6-8 weeks |
| **Content Generation** (new) | Does not exist | RAG + prompt + validation pipeline | 8-12 weeks |

## Medium Impact (Feature Extensions)

| Module | Current State | Required Changes | Effort |
|--------|---------------|------------------|--------|
| **Configuration** (`config.yaml`) | Redis/Cassandra/DKT config | Add LLM, vector store, GPU settings | 1 week |
| **Data Models** (`src/models/`) | BKTState, SM2Data | Add KC, GeneratedContent, ProfileV2 | 2-3 weeks |
| **Event Publisher** (`src/services/event_publisher.py`) | Kafka interaction events | Add generation events | 1 week |
| **Docker Compose** | Redis/Cassandra stack | Add ChromaDB/Pinecone, LLM proxy | 1-2 weeks |
| **Repositories** (`src/repositories/`) | Redis/Cassandra stores | Add vector store repository | 2-3 weeks |

## Low Impact (Preserved As-Is)

| Module | Justification |
|--------|---------------|
| **SM2 Scheduler** (`src/engines/sm2_scheduler.py`) | Spaced repetition unchanged; integrates with extended profile |
| **Circuit Breaker** (`src/services/circuit_breaker.py`) | Pattern reusable for LLM calls; configuration only |
| **Structured Logging** (`src/utils/logging.py`) | No changes required |
| **Error Handling** (`src/utils/errors.py`) | Add generation-specific errors only |
| **DKT Client** (stubbed) | Already prepared for Phase 2; minimal changes |

## Architectural Conflicts and Resolutions

## Conflict 1: Latency Model Incompatibility

**Issue**: Original system targets <100ms for content delivery. Revised spec accepts 2-4s for LLM generation.

**Resolution Strategy**:
- Implement **dual latency model**: <100ms for routing/state, <3s for generation
- Use **streaming delivery** (SSE) to provide progressive content delivery
- Maintain **fallback chain**: Generated content → Pre-generated cache → Static pool
- Add **pre-generation cache** for common content patterns

## Conflict 2: Content Source Paradigm Shift

**Issue**: Original system selects from pre-authored content pools. Revised system generates content on-demand.

**Resolution Strategy**:
- Preserve existing **ContentModule** entity as fallback
- Add **GeneratedContent** entity for new paradigm
- Modify recommendation flow to attempt generation first, fallback to pool
- Update CDN integration to cache generated content

## Conflict 3: Routing Algorithm Replacement

**Issue**: Original multi-objective optimizer must be replaced with Thompson Sampling contextual bandits.

**Resolution Strategy**:
- Implement **Thompson Sampling Engine** as new service
- Run **A/B test** between old and new router during transition
- Maintain configuration for gradual traffic shift
- Preserve optimizer for comparison baseline

## Conflict 4: Learner Model Granularity

**Issue**: Original system tracks mastery at Learning Objective (LO) level. Revised requires Knowledge Component (KC) sub-granularity.

**Resolution Strategy**:
- Create **KC taxonomy** with LO-to-KC mappings
- Extend BKT engine to track KC-level mastery
- Maintain LO-level aggregation for backward compatibility
- Implement **data migration** for historical LO mastery → KC estimates

## Database Migration Requirements

## New Tables/Collections Required

### 1. knowledge_components
```sql
CREATE TABLE knowledge_components (
    kc_id TEXT PRIMARY KEY,
    lo_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    difficulty DOUBLE,
    estimated_time_minutes INT,
    prerequisite_kcs LIST<TEXT>,
    created_at TIMESTAMP
);
```
**Purpose**: Decompose LOs into granular KCs for finer adaptation.

### 2. learner_profile_extended
```sql
CREATE TABLE learner_profile_extended (
    student_id UUID PRIMARY KEY,
    cognitive_traits MAP<TEXT, DOUBLE>,
    affective_state MAP<TEXT, TEXT>,
    learning_preferences MAP<TEXT, TEXT>,
    metacognitive_data MAP<TEXT, DOUBLE>,
    updated_at TIMESTAMP
);
```
**Purpose**: Store cognitive traits, affective states, and preferences.

### 3. generated_content
```sql
CREATE TABLE generated_content (
    generation_id TEXT PRIMARY KEY,
    student_id UUID,
    request_context TEXT,
    content_type TEXT,
    body TEXT,
    quality_score DOUBLE,
    validation_passed BOOLEAN,
    model_used TEXT,
    generation_latency_ms INT,
    created_at TIMESTAMP
);
```
**Purpose**: Audit trail and caching for generated content.

### 4. vector_store_curriculum
**Purpose**: ChromaDB/Pinecone collection for RAG grounding.
- Document chunks with embeddings
- Metadata: subject, grade, standard, kc_id
- Similarity search for retrieval-augmented generation

## Schema Modifications Required

### 5. student_knowledge_state (ALTER)
```sql
ALTER TABLE student_knowledge_state ADD COLUMN kc_id TEXT;
ALTER TABLE student_knowledge_state ADD COLUMN is_kc_level BOOLEAN;
CREATE INDEX idx_kc_lookup ON student_knowledge_state(kc_id);
```
**Purpose**: Support both LO-level (legacy) and KC-level (new) tracking.

## Data Migration Strategy

| Migration | Source | Target | Complexity |
|-----------|--------|--------|------------|
| LO → KC mapping | Existing LO definitions | knowledge_components table | High |
| Historical mastery | LO-level BKT states | KC-level estimates | Medium |
| Profile extension | N/A (new data) | learner_profile_extended | Low |
| Content audit | N/A (new data) | generated_content | Low |

## Third-Party Integration Changes

## New Integrations Required

| Service | Technology | Purpose | Integration Point |
|---------|------------|---------|-------------------|
| **LLM Gateway** | LiteLLM / Custom | Multi-provider LLM abstraction | `src/services/llm_orchestrator.py` |
| **Vector Store** | ChromaDB / Pinecone | RAG curriculum grounding | `src/repositories/vector_store.py` |
| **GPU Cluster** | NVIDIA Triton | LLM inference (self-hosted) | New service endpoint |
| **LLM APIs** | OpenAI / Anthropic | Commercial LLM fallback | LLM Gateway |
| **Prompt Registry** | Weights & Biases / Custom | Prompt versioning | `src/services/prompt_manager.py` |

## Modified Integrations

| Service | Current Usage | Required Changes |
|---------|---------------|------------------|
| **Redis** | Hot cache for BKT states | Add cache for pre-generated content |
| **Cassandra** | Time-series interaction data | Add generated content audit table |
| **Kafka** | Interaction events | Add generation events topic |
| **NVIDIA Triton** | DKT inference (Phase 2) | Add LLM inference endpoints |

## Deprecated Integrations

| Service | Rationale | Migration Path |
|---------|-----------|----------------|
| **Primary CDN workflow** | Generation replaces static as primary | Fallback/emergency use only |
| **Authoring tool integration** | Reduced pre-authored content | Prompt management system |

## Refactoring Recommendations

## Priority 1: Foundation (Weeks 1-6)

1. **Extract Configuration**
   - Move LLM settings to environment-aware config
   - Add feature flags for gradual rollout

2. **Create LLM Service Layer**
   ```
   src/services/
   ├── llm_orchestrator.py    # NEW: Route to appropriate model
   ├── rag_retriever.py       # NEW: Vector store queries
   ├── prompt_manager.py      # NEW: Version and template prompts
   └── content_validator.py   # NEW: Safety/quality checks
   ```

3. **Extend Data Models**
   - Create `KnowledgeComponent` model
   - Create `ExtendedProfile` model
   - Modify `BKTState` to optionally reference KC

## Priority 2: Core Capabilities (Weeks 7-14)

4. **Implement Thompson Sampling Router**
   - Replace multi-objective optimizer
   - Add A/B testing infrastructure
   - Implement contextual bandit logic

5. **Build Generation Pipeline**
   - Integrate RAG retrieval
   - Implement streaming response handler
   - Add validation layer

6. **Extend Learner Profile**
   - Add cognitive trait tracking
   - Implement affective state classifier
   - Create profile v2 API endpoints

## Priority 3: Migration (Weeks 15-24)

7. **Data Migration**
   - KC taxonomy development
   - Historical data transformation
   - Dual-write during transition

8. **API v2 Rollout**
   - Deploy new endpoints
   - Client migration support
   - Deprecate v1 (long-term)

## Risk Analysis

## High Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM latency >3s | Poor UX, student disengagement | Streaming, pre-generation, model tiering |
| Content hallucination | Misinformation, trust loss | RAG grounding, validation pipeline, human review |
| KC decomposition errors | Incorrect mastery assessment | Expert validation, gradual rollout, rollback plan |
| Thompson Sampling underperformance | Worse recommendations than optimizer | A/B testing, fallback to optimizer |

## Medium Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| GPU cost overruns | Budget exceedance | Usage quotas, caching, model tiering |
| Affective classifier inaccuracy | Misadaptation | Start with rules-based, graduate to ML |
| Profile migration data loss | Incomplete learner history | Backup strategy, parallel tracking |
| Third-party LLM rate limits | Service degradation | Multi-provider fallback, self-hosted option |

## Low Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| Docker Compose complexity | Developer onboarding friction | Documentation, simplified dev profile |
| Configuration sprawl | Maintenance burden | Configuration validation, documentation |
| Test coverage gaps | Regression bugs | Incremental test additions per module |

## Implementation Priority Matrix

## Phase 1: Foundation (Months 1-3)
- [ ] LLM orchestration service
- [ ] Vector store integration
- [ ] Prompt management system
- [ ] Extended profile schema
- [ ] v2 API scaffolding

## Phase 2: Generation (Months 4-6)
- [ ] Explanation generator
- [ ] Problem generator
- [ ] Content validation pipeline
- [ ] RAG pipeline
- [ ] Pre-generation cache

## Phase 3: Adaptation (Months 7-9)
- [ ] Thompson Sampling router
- [ ] KC decomposition (top 50 LOs)
- [ ] Affective classifier (rule-based)
- [ ] Cognitive trait assessment
- [ ] Within-session adaptation

## Phase 4: Advanced (Months 10-12)
- [ ] Remedial generation
- [ ] Multi-modal synthesis
- [ ] Misconception detection
- [ ] Full KC taxonomy
- [ ] v1 deprecation planning

## Dependencies and Task Sequencing

### Dependency Graph

```
Phase 1: Foundation (Months 1-3)
├── MIG-042 Infrastructure: Vector store [Complexity: Medium]
├── MIG-043 Infrastructure: LLM gateway [Complexity: Medium]
│   └── MIG-045 Integration: OpenAI/Anthropic [Complexity: Low]
├── MIG-005 src/models/knowledge_component.py [Complexity: Medium]
│   ├── MIG-012 src/engines/bkt_engine.py [Complexity: High]
│   └── MIG-036 Database: knowledge_components [Complexity: High]
├── MIG-006 src/models/extended_profile.py [Complexity: Medium]
│   ├── MIG-007 src/engines/thompson_sampler.py [Complexity: High]
│   └── MIG-037 Database: learner_profile_extended [Complexity: Medium]
├── MIG-001 src/services/llm_orchestrator.py [Complexity: High]
│   └── MIG-008 src/engines/generation_engine.py [Complexity: High]
├── MIG-002 src/services/rag_retriever.py [Complexity: Medium]
│   └── MIG-011 src/repositories/vector_store.py [Complexity: Medium]
└── MIG-003 src/services/prompt_manager.py [Complexity: Medium]

Phase 2: Generation (Months 4-6)
├── MIG-008 src/engines/generation_engine.py [Depends: MIG-001 + MIG-002]
├── MIG-004 src/services/content_validator.py [Depends: MIG-008]
├── MIG-009 src/engines/affective_classifier.py [Complexity: High]
├── MIG-010 src/api/generation_routes.py [Depends: MIG-008]
└── MIG-038 Database: generated_content [Depends: MIG-008]

Phase 3: Adaptation (Months 7-9)
├── MIG-040 Data: LO to KC mapping [Complexity: High - CRITICAL PATH]
├── MIG-039 Database: student_knowledge_state [Depends: MIG-005]
├── MIG-041 Data: Historical mastery migration [Depends: MIG-040]
├── MIG-007 src/engines/thompson_sampler.py [Depends: MIG-006]
└── MIG-014 src/api/recommendations.py [Depends: MIG-007]

Phase 4: Integration & Rollout (Months 10-12)
├── MIG-013 src/api/router.py [Depends: MIG-010]
├── MIG-015 src/api/state.py [Depends: MIG-006]
└── MIG-044 Infrastructure: GPU expansion [Complexity: Medium]
```

### Critical Path Analysis

**Longest Path (Critical Path)**: 24 weeks
- MIG-005 → MIG-012 → MIG-040 → MIG-041 (KC taxonomy development and migration)
- MIG-006 → MIG-007 → MIG-014 (Thompson Sampling router implementation)
- MIG-042/MIG-043 → MIG-001 → MIG-008 → MIG-010 (Generation pipeline)

**Parallel Work Streams**:
- **Stream A (Infrastructure)**: MIG-042, MIG-043, MIG-044, MIG-045 → Can start immediately
- **Stream B (Data Models)**: MIG-005, MIG-006, MIG-036, MIG-037 → Foundation for features
- **Stream C (Generation)**: MIG-001, MIG-002, MIG-003, MIG-008, MIG-004 → Core new capability
- **Stream D (Adaptation)**: MIG-007, MIG-009, MIG-040, MIG-041 → Advanced features

### Risk Factors by Complexity Level

#### High Complexity Tasks (8 tasks, 34 weeks total)

| Task ID | Risk Factor | Mitigation Strategy |
|---------|-------------|---------------------|
| MIG-001 | LLM provider API instability | Abstract via gateway; multi-provider fallback |
| MIG-004 | Content safety validation gaps | Human-in-the-loop review; conservative thresholds |
| MIG-007 | Thompson Sampling underperforms vs optimizer | A/B test with rollback; maintain optimizer fallback |
| MIG-008 | Generation latency >4s | Streaming; pre-generation cache; model tiering |
| MIG-009 | Affective classifier inaccuracy | Start rule-based; graduate to ML gradually |
| MIG-012 | KC granularity breaks mastery aggregation | Dual-write period; validation dashboards |
| MIG-036 | KC taxonomy requires expert validation | Phased rollout; top 50 LOs first; iterative refinement |
| MIG-040 | Expert availability bottleneck | External contractor budget; parallel taxonomy work |

#### Medium Complexity Tasks (20 tasks, 38 weeks total)

| Task ID | Risk Factor | Mitigation Strategy |
|---------|-------------|---------------------|
| MIG-002 | Vector store query performance | Benchmark early; index optimization; caching layer |
| MIG-010 | Streaming API backward compatibility | Versioned endpoints; client SDK updates |
| MIG-022 | KC state operations data consistency | Transaction wrapper; eventual consistency acceptable |
| MIG-026-030 | Test coverage gaps | Incremental test addition; integration test priority |
| MIG-041 | Historical data transformation errors | Validation sampling; rollback scripts; audit logging |

#### Low Complexity Tasks (15 tasks, 12 weeks total)

| Task ID | Risk Factor | Mitigation Strategy |
|---------|-------------|---------------------|
| MIG-015-025 | Configuration drift | Environment validation; automated config testing |
| MIG-031-032 | Prompt directory structure changes | Document conventions; code review checklist |
| MIG-045 | API key rotation management | Secrets manager integration; automated rotation |

### Suggested Sequencing of Complex Changes

#### Sequence 1: Infrastructure First (Weeks 1-4)
1. **MIG-042** Vector store provisioning
2. **MIG-043** LLM gateway deployment
3. **MIG-045** Commercial LLM configuration
4. **MIG-044** GPU expansion (can parallelize with development)

#### Sequence 2: Foundation Models (Weeks 1-6)
5. **MIG-005** KC data model (blocks MIG-012, MIG-036)
6. **MIG-006** Extended profile model (blocks MIG-007, MIG-037)
7. **MIG-036** KC database table
8. **MIG-037** Extended profile database table

#### Sequence 3: Core Services (Weeks 4-10)
9. **MIG-001** LLM orchestrator (blocks MIG-008)
10. **MIG-002** RAG retriever (blocks MIG-008)
11. **MIG-003** Prompt manager
12. **MIG-008** Generation engine (CRITICAL - blocks MIG-004, MIG-010)

#### Sequence 4: Quality & Safety (Weeks 10-14)
13. **MIG-004** Content validator
14. **MIG-009** Affective classifier
15. **MIG-038** Generated content audit table

#### Sequence 5: Algorithm Migration (Weeks 8-18)
16. **MIG-007** Thompson Sampling router
17. **MIG-012** BKT engine KC extension
18. **MIG-014** Recommendations integration

#### Sequence 6: Data Migration (Weeks 12-24)
19. **MIG-040** KC taxonomy (CRITICAL PATH - longest task)
20. **MIG-039** Student knowledge state migration
21. **MIG-041** Historical mastery transformation

#### Sequence 7: API Integration (Weeks 16-24)
22. **MIG-010** Generation routes
23. **MIG-013** API router v2
24. **MIG-015** State endpoints v2
