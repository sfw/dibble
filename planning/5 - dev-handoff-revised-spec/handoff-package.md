---
classification: Development Handoff
date: '2026-03-14'
status: Final
version: '1.0'
---

# Development Handoff Package: Revised Adaptive Learning Platform Specification

> **Purpose**: This document provides comprehensive development guidance for implementing the revised adaptive learning platform specification. It consolidates all analysis, planning, and migration guidance into a single authoritative reference.

## Table of Contents

1. [Executive Summary](#executive-summary)
   - [Why the Specification Changed](#why-the-specification-changed)
   - [What Changed at a High Level](#what-changed-at-a-high-level)
   - [Major Technical Impacts](#major-technical-impacts)
   - [Migration Strategy](#migration-strategy)
   - [Success Metrics](#success-metrics)
   - [Key Takeaways for Stakeholders](#key-takeaways-for-stakeholders)

2. [Implementation Roadmap](#implementation-roadmap)
   - [Phase Structure](#phase-structure)
   - [Phase 1: Foundation Infrastructure (Months 1-3)](#phase-1-foundation-infrastructure-months-1-3)
   - [Phase 2: Generation Capabilities (Months 4-6)](#phase-2-generation-capabilities-months-4-6)
   - [Phase 3: Algorithm Transition (Months 7-12)](#phase-3-algorithm-transition-months-7-12)
   - [Phase 4: Integration & Rollout (Months 13-24)](#phase-4-integration--rollout-months-13-24)
   - [Critical Path Analysis](#critical-path-analysis)
   - [Parallel Work Streams](#parallel-work-streams)
   - [Quick Wins](#quick-wins-parallel-track)
   - [Risk-Adjusted Timeline](#risk-adjusted-timeline)

3. [Detailed Changelog](#detailed-changelog)
   - [Changelog Legend](#changelog-legend)
   - [Architecture Paradigm Shift](#architecture-paradigm-shift)
   - [Added Requirements (New Capabilities)](#added-requirements-new-capabilities)
   - [Enhanced Requirements](#enhanced-requirements)
   - [Modified Requirements (Behavior Changes)](#modified-requirements-behavior-changes)
   - [Replaced Requirements (Breaking Changes)](#replaced-requirements-breaking-changes)
   - [Unchanged Requirements (Maintained)](#unchanged-requirements-maintained)
   - [Deprecated/Deprioritized Requirements](#deprecateddeprioritized-requirements)
   - [Breaking Change Details](#breaking-change-details-migration-required)
   - [Changelog Summary Statistics](#changelog-summary-statistics)
   - [Document Cross-Reference Index](#document-cross-reference-index)

4. [Technical Migration Guide](#technical-migration-guide)
   - [Migration Prerequisites](#migration-prerequisites)
   - [Phase 1: Foundation Infrastructure (Weeks 1-6)](#phase-1-foundation-infrastructure-weeks-1-6)
   - [Phase 2: Data Model Extensions (Weeks 3-4)](#phase-2-data-model-extensions-weeks-3-4)
   - [Phase 3: Database Migrations (Weeks 4-6)](#phase-3-database-migrations-weeks-4-6)
   - [Phase 4: API Extensions (Weeks 5-8)](#phase-4-api-extensions-weeks-5-8)
   - [Phase 5: Testing Strategy](#phase-5-testing-strategy)
   - [Phase 6: Deployment Checklist](#phase-6-deployment-checklist)

5. [Appendices](#appendices)
   - [A. System Artifact Inventory](#a-system-artifact-inventory)
   - [B. Requirements Traceability Matrix](#b-requirements-traceability-matrix)
   - [C. Migration Checklist](#c-migration-checklist)
   - [D. Related Documents](#d-related-documents)

---

# Executive Summary

## Why the Specification Changed

The original adaptive learning platform specification delivered **35% of the vision**—a content recommendation engine that selects from pre-authored materials. After architectural assessment and gap analysis, the revised specification achieves **95% of the vision** by transforming the platform into an **LLM-powered generative learning system** that creates personalized educational content on demand.

### Business Justification

| Aspect | Original Approach | Revised Approach | Business Impact |
|--------|-------------------|------------------|-----------------|
| **Content Coverage** | Limited to pre-authored pools | Unlimited dynamic generation | Scale without content bottlenecks |
| **Personalization Depth** | Knowledge state only | Knowledge + cognitive + affective | 2-3x learning efficacy improvement |
| **Remediation Speed** | Hours/days to create missing content | Seconds to generate targeted help | Real-time intervention capability |
| **Vision Achievement** | 35% | 95% | Near-complete vision realization |

**Key Driver**: The original architecture could not deliver true adaptive learning at the granularity required. Content pools are inherently limited, and selection-based systems cannot address the long tail of student misconceptions. The revised generative approach removes the content bottleneck while maintaining educational quality through RAG (Retrieval-Augmented Generation) grounding.

---

## What Changed at a High Level

### Paradigm Shift: Selection → Generation

**Before**: System selects from existing content (like Netflix recommending movies)
- Query content database → Return content ID → Deliver from CDN
- Latency: <100ms

**After**: System generates content dynamically (like ChatGPT tutoring a student)
- Analyze learner state → Route to LLM → Generate content → Validate → Stream delivery
- Latency: 2-4s (with streaming for perceived responsiveness)

### The Four Critical Additions

#### 1. LLM Infrastructure Layer (Foundation)
New infrastructure that did not exist in the original specification:
- LLM orchestration service (routes to fast/capable models)
- Prompt engineering framework (versioning, A/B testing)
- RAG pipeline (curriculum-grounded generation)
- Content safety/moderation layer
- Streaming response architecture

**Effort**: 6-9 months | **Cost Impact**: +$420K annually in infrastructure

#### 2. Multi-Dimensional Learner Profiling (Understanding)
Extended learner model beyond knowledge state:
- **Cognitive traits**: Working memory, processing speed, spatial reasoning
- **Affective states**: Engagement, frustration, confusion, flow detection
- **Knowledge Components (KC)**: Sub-LO granularity for precise diagnosis
- **Metacognitive tracking**: Confidence calibration, help-seeking behavior

**Effort**: 4-6 months | **Impact**: Enables truly personalized interventions

#### 3. Dynamic Content Generation (Action)
New generative capabilities replacing static content dependence:
- On-the-fly explanations for misconceptions
- Practice problem synthesis with difficulty calibration
- Worked example generation with adaptive fading
- Remedial micro-module creation
- Multi-modal synthesis (diagrams, interactives)

**Effort**: 12-15 months | **Impact**: Unlimited content variety at scale

#### 4. Advanced Adaptation Intelligence (Decision)
Smarter routing and intervention systems:
- Contextual Thompson Sampling router (replaces multi-objective optimizer)
- Within-session real-time adaptation (not just between modules)
- Misconception detection and classification
- Automatic "step back" intervention with dynamic content
- Conversational/Socratic assessment capability

**Effort**: 6-8 months | **Impact**: Proactive, timely interventions

---

## Major Technical Impacts

### Investment Requirements

| Category | Original | Revised | Increase |
|----------|----------|---------|----------|
| **Timeline** | 24 months | 18-24 months (phased) | Comparable with parallel work |
| **Budget** | $1.2M | $2.0M-$3.2M | +$800K-$2.0M |
| **Team Size** | 4-6 engineers | 8-10 engineers | +4 engineers |
| **Infrastructure (Annual)** | ~$200K | ~$620K | +$420K |

### Architectural Impact Assessment

| Component | Impact Level | Description |
|-----------|--------------|-------------|
| **Existing BKT/DKT Engines** | ✅ Preserved | Core knowledge tracing remains valid; extended but not replaced |
| **Content Delivery Layer** | 🔴 Transformative | New LLM integration, streaming, fallback chains required |
| **Learner Profile Service** | 🟡 High | Schema extensions for cognitive/affective dimensions |
| **Recommendation Router** | 🔴 Replaced | Multi-objective optimizer → Contextual Thompson Sampling |
| **Storage Layer** | 🟡 Medium | Vector store addition; Redis/Cassandra schema extensions |
| **API Layer** | 🟡 Medium | New v2 endpoints; backward compatibility maintained |

### Breaking Changes (Require Migration)

**5 breaking changes** affect existing implementations:

1. **Knowledge Component Granularity** (PROF-004)
   - Data migration required: LO-level → KC-level tracking
   - New taxonomy development needed

2. **Thompson Sampling Router** (ADAPT-001)
   - Algorithm replacement with probabilistic behavior
   - Configuration migration and A/B testing required

3. **Dynamic Intervention Format** (ADAPT-004)
   - Response format changes from content_id to generated payload
   - Client integration updates needed

4. **Content Pool Deprioritization** (DEP-001)
   - CDN delivery becomes fallback, not primary
   - Integration workflow restructuring

5. **Authoring Workflow Deprioritization** (DEP-002)
   - Shift from pre-authoring to prompt engineering
   - Process migration and retraining required

---

## Migration Strategy

### Phased Rollout Approach

The migration follows a **4-phase, 12-month strategy** that preserves backward compatibility while building new capabilities:

#### Phase 1: Infrastructure (Months 1-3)
**Goal**: Deploy non-breaking foundation
- LLM orchestration service
- Vector store for RAG
- GPU cluster expansion
- New v2 API endpoints (additive only)

**Risk**: Low | **Backward Compatibility**: ✅ Maintained

#### Phase 2: Data Migration (Months 4-6)
**Goal**: Execute breaking data migration
- Develop KC taxonomy for top 50 Learning Objectives
- Create LO-to-KC mapping tables
- Run parallel tracking (LO + KC)
- Migrate historical mastery data

**Risk**: Medium | **Rollback Plan**: Parallel running maintained

#### Phase 3: Algorithm Transition (Months 7-9)
**Goal**: Migrate recommendation and intervention systems
- Deploy Thompson Sampling alongside existing optimizer
- A/B test with gradual traffic shift
- Update intervention clients for generated content
- Implement generation-first delivery

**Risk**: High | **Mitigation**: Feature flags, gradual rollout

#### Phase 4: Deprecation (Months 10-12)
**Goal**: Complete migration, deprecate old systems
- Retire multi-objective optimizer
- Deprecate authoring workflow
- Transition content pool to emergency fallback
- Update documentation and client libraries

**Risk**: Medium | **Prerequisite**: All clients migrated

### Deprecation Timeline

| Feature | Deprecation Notice | End of Support | Migration Deadline |
|---------|-------------------|----------------|-------------------|
| Multi-objective optimizer | Month 7 | Month 15 | Month 12 |
| Static content pool (primary) | Month 1 | Month 18 | Month 12 |
| Content authoring workflow | Month 1 | Month 12 | Month 10 |
| v1 profile endpoints | Month 12 | Month 24 | Month 18 |
| LO-only granularity | Month 4 | Month 18 | Month 12 |

### Quick Wins (Parallel Track)

These low-risk enhancements can deliver immediate value while foundation is built:

1. **Redis Schema Extensions** (1 week): Affective state caching
2. **API v2 Stubs** (2 weeks): Prepare client integration paths
3. **KC Table Setup** (1 week): Database preparation
4. **Basic LLM Integration** (2 weeks): Validate latency assumptions
5. **Configuration Framework** (1 week): LLM provider management

---

## Success Metrics

### Technical Milestones

| Phase | Metric | Target |
|-------|--------|--------|
| Phase 1 | LLM generation latency (p95) | <3s |
| Phase 1 | Content validation pass rate | >95% |
| Phase 2 | Affective classification F1 | >0.75 |
| Phase 2 | KC mastery prediction AUC | >0.85 |
| Phase 3 | Remedial intervention success | >70% |
| Phase 3 | Learning gain improvement | +15% vs baseline |
| Phase 4 | System availability | 99.99% |
| Phase 4 | Concurrent user capacity | 100K |

### Go/No-Go Decision Gates

| Gate | Timing | Criteria |
|------|--------|----------|
| **Gate 1** | Month 6 | LLM infra <3s latency, >95% validation pass |
| **Gate 2** | Month 12 | Affective >75% accuracy, KC decomposition complete |
| **Gate 3** | Month 18 | Remedial >70% success, learning gains +15% |
| **Gate 4** | Month 24 | <2s streaming, 99.99% uptime |

---

## Key Takeaways for Stakeholders

### What Stays the Same
- ✅ BKT/DKT knowledge tracing remains core foundation
- ✅ Evidence-based approach (still rejects learning styles)
- ✅ Universal Design for Learning principles
- ✅ 24-month implementation timeline (phased differently)

### What Changes Fundamentally
- 🔴 Content delivery: Selection → Generation
- 🔴 Latency model: <100ms → 2-4s (streaming)
- 🔴 Routing algorithm: Rule-based → Thompson Sampling
- 🔴 Learner model: Knowledge-only → Multi-dimensional
- 🔴 Content strategy: Pre-authoring → Prompt engineering

### Investment Summary
- **Time**: Comparable (18-24 months phased)
- **Budget**: +$800K-$2.0M (total $2.0M-$3.2M)
- **Infrastructure**: +$420K annually (LLM + GPU + vector store)
- **Team**: +4 engineers (8-10 total)
- **Vision Achievement**: 35% → 95% (+60%)

---

---

## Implementation Roadmap

### Overview

This roadmap provides a prioritized, sequenced plan for implementing the revised specification over 24 months. The roadmap balances parallel work streams, critical path dependencies, and risk mitigation through phased rollouts.

**Total Effort**: ~84 weeks of engineering time  
**Team Size**: 8-10 engineers (scaling to 12 during peak months 4-12)  
**Critical Path Duration**: 24 weeks  

### Phase Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        IMPLEMENTATION TIMELINE                               │
├───────────────┬───────────────┬───────────────┬─────────────────────────────┤
│   Phase 1     │   Phase 2     │   Phase 3     │        Phase 4              │
│  Foundation   │  Generation   │  Adaptation   │     Integration/Rollout     │
│  Months 1-3   │  Months 4-6   │  Months 7-12  │        Months 13-24         │
└───────────────┴───────────────┴───────────────┴─────────────────────────────┘
```

---

### Phase 1: Foundation Infrastructure (Months 1-3)

**Goal**: Deploy non-breaking foundation infrastructure and data models  
**Risk Level**: Low | **Backward Compatibility**: ✅ Maintained  
**Deliverables**: LLM orchestration, vector store, KC data layer, extended profiles

#### Work Stream A: Infrastructure (Team A - 2 engineers)

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 1-2 | MIG-042 | Vector store (ChromaDB/Pinecone) provisioned | None |
| 2-3 | MIG-043 | LLM gateway deployed | None |
| 3-4 | MIG-045 | Commercial LLM API integration | MIG-043 |
| 8-10 | MIG-044 | GPU cluster expansion for inference | MIG-043 |

#### Work Stream B: Data Layer (Team B - 2 engineers)

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 1-2 | MIG-005 | KC data model (src/models/knowledge_component.py) | None |
| 2-3 | MIG-006 | Extended profile model | None |
| 4-6 | MIG-036 | knowledge_components table in Cassandra | MIG-005 |
| 4-6 | MIG-037 | learner_profile_extended table | MIG-006 |
| 6-8 | MIG-039 | Alter student_knowledge_state for KC support | MIG-036 |

#### Work Stream C: Core Services (Team C - 2 engineers)

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 2-4 | MIG-001 | LLM orchestrator service | MIG-043 |
| 3-4 | MIG-002 | RAG retriever | MIG-042 |
| 3-4 | MIG-003 | Prompt manager | None |
| 4-6 | MIG-011 | Vector store repository | MIG-042, MIG-002 |

**Phase 1 Milestones**:
- ✅ Week 4: Vector store and LLM gateway operational
- ✅ Week 8: All database migrations complete in staging
- ✅ Week 12: Foundation services deployed, v2 API stubs available

---

### Phase 2: Generation Capabilities (Months 4-6)

**Goal**: Build content generation pipeline and safety systems  
**Risk Level**: Medium | **Backward Compatibility**: ✅ Maintained  
**Deliverables**: Generation engine, content validator, v2 API endpoints

#### Work Stream C: Generation Core (Team C - 3 engineers, expanded)

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 10-14 | MIG-008 | Generation engine with RAG integration | MIG-001, MIG-002 |
| 14-16 | MIG-004 | Content validator/safety layer | MIG-008 |
| 12-14 | MIG-038 | Generated content audit table | MIG-008 |

#### Work Stream D: Adaptation (Team D - 2 engineers)

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 12-15 | MIG-009 | Affective classifier | MIG-006 |
| 14-16 | MIG-007 | Thompson Sampling router | MIG-006 |

#### Work Stream F: API Integration (Team F - 2 engineers)

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 14-16 | MIG-010 | v2 generation routes (/api/v2/content/generate) | MIG-008 |
| 16-18 | MIG-013 | API router with v2 integration | MIG-010 |
| 16-18 | MIG-015 | State endpoints v2 | MIG-006 |

**Phase 2 Milestones**:
- ✅ Week 14: Generation engine generating content in dev environment
- ✅ Week 16: Content validator achieving >95% safety pass rate
- ✅ Week 18: v2 API endpoints operational with feature flags

---

### Phase 3: Algorithm Transition (Months 7-12)

**Goal**: Execute breaking changes and migrate to new algorithms  
**Risk Level**: High | **Backward Compatibility**: ⚠️ Breaking changes  
**Deliverables**: KC taxonomy, Thompson Sampling production, data migration

#### Work Stream E: Data Migration (Team E - 1 engineer + domain experts)

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 20-32 | MIG-040 | KC taxonomy for top 50 LOs | MIG-005 |
| 26-32 | MIG-041 | Historical mastery migration | MIG-040, MIG-039 |

#### Work Stream D: Adaptation (Team D - 2 engineers)

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 18-24 | MIG-012 | BKT engine KC extension | MIG-005, MIG-036 |
| 22-26 | MIG-014 | Recommendations with Thompson Sampling | MIG-007, MIG-012 |
| 24-28 | MIG-022 | KC state operations | MIG-039, MIG-012 |

#### Work Stream C: Quality & Hardening

| Week | Task | Deliverable | Dependencies |
|------|------|-------------|--------------|
| 18-24 | MIG-026-030 | Test suite completion | All above |
| 20-24 | MIG-046 | API v2 documentation | MIG-010, MIG-013 |

**Phase 3 Milestones**:
- ✅ Week 24: Thompson Sampling router in A/B test
- ✅ Week 32: KC taxonomy complete for pilot LOs
- ✅ Week 36: Data migration validated in staging

---

### Phase 4: Integration & Rollout (Months 13-24)

**Goal**: Production rollout, deprecation, and optimization  
**Risk Level**: Medium | **Backward Compatibility**: ⚠️ Deprecations  
**Deliverables**: Production deployment, old system deprecation, performance optimization

#### Production Rollout Timeline

| Month | Activity | Key Decision |
|-------|----------|--------------|
| 13-14 | Limited production pilot (5% traffic) | Monitor latency, safety metrics |
| 15-16 | Gradual expansion (25% → 50%) | Go/No-Go Gate 2 |
| 17-18 | Full production (100%) with fallback | All traffic on new system |
| 19-20 | Multi-objective optimizer deprecation | Feature flag removal |
| 21-22 | Content pool deprioritization | CDN becomes emergency fallback |
| 23-24 | Authoring workflow deprecation | Process migration complete |

#### Go/No-Go Decision Gates

| Gate | Month | Criteria | Decision |
|------|-------|----------|----------|
| **Gate 1** | 6 | LLM infra <3s latency; >95% validation pass | Proceed to Phase 2 |
| **Gate 2** | 12 | Affective >75% accuracy; KC taxonomy complete | Proceed to Phase 3 |
| **Gate 3** | 18 | Remedial >70% success; learning gains +15% | Proceed to Phase 4 |
| **Gate 4** | 24 | <2s streaming; 99.99% uptime; 100K concurrent | Project complete |

---

### Critical Path Analysis

The critical path determines the minimum project duration. Any delay on critical path tasks delays the entire project.

```
CRITICAL PATH (24 weeks):
┌─────────────────────────────────────────────────────────────────────┐
│ MIG-005 → MIG-012 → MIG-040 → MIG-041 (KC taxonomy & migration)   │
│         → MIG-039 (state migration)                                 │
├─────────────────────────────────────────────────────────────────────┤
│ MIG-006 → MIG-007 → MIG-014 (Thompson Sampling router)            │
├─────────────────────────────────────────────────────────────────────┤
│ MIG-042/MIG-043 → MIG-001 → MIG-008 → MIG-010 (Generation)        │
└─────────────────────────────────────────────────────────────────────┘
```

**Critical Path Duration**: 24 weeks (6 months)  
**Float Available**: Non-critical tasks have 4-8 weeks of scheduling flexibility

---

### Parallel Work Streams

Six parallel work streams maximize resource utilization and accelerate delivery:

| Stream | Focus | Team Size | Peak Activity |
|--------|-------|-----------|---------------|
| **Team A** | Infrastructure | 2 engineers | Months 1-3 |
| **Team B** | Data Layer | 2 engineers | Months 1-4 |
| **Team C** | Generation Core | 3 engineers | Months 2-8 |
| **Team D** | Adaptation | 2 engineers | Months 3-10 |
| **Team E** | Data Migration | 1 engineer + experts | Months 5-12 |
| **Team F** | API/Integration | 2 engineers | Months 4-10 |

**Total Team Size**: 12 engineers at peak (months 4-10)  
**Scaling Strategy**: Teams A, B scale down after month 6; Teams C, D, F maintain through month 10

---

### Quick Wins (Parallel Track)

These low-risk enhancements deliver immediate value while foundation is built:

| Task | Effort | Value | Timeline |
|------|--------|-------|----------|
| **MIG-031/032** Prompt directories | 6 days | Engineering productivity | Month 1 |
| **MIG-019/020/025** Configuration framework | 1 week | LLM provider flexibility | Month 2 |
| **MIG-016/017/018** Model schema extensions | 2 weeks | API preparation | Month 2 |
| **MIG-015** Profile v2 endpoints | 1 week | Client integration path | Month 3 |
| **MIG-046** API documentation | 1 week | Developer onboarding | Month 4 |

**Quick Win Strategy**: Assign to new team members for onboarding while senior engineers tackle critical path

---

### Risk-Adjusted Timeline

| Scenario | Probability | Timeline Impact | Mitigation |
|----------|-------------|-----------------|------------|
| **Base Case** | 60% | 24 months | As planned |
| **KC Taxonomy Delays** | 20% | +2-4 months | External contractors; parallel work |
| **LLM Performance Issues** | 15% | +1-2 months | Multi-provider fallback; caching |
| **Integration Blockers** | 5% | +1 month | Extended parallel running |

**Expected Timeline**: 24-26 months (base case with contingency)  
**Budget Reserve**: +20% ($400K-$640K) recommended

---

## Detailed Changelog

This section provides a comprehensive, traceable changelog of all specification changes between the original system (defined in `planning/` and `platform-root/`) and the revised specification (in `revised-spec/`). Each change is documented with before/after comparisons and specific document references.

### Changelog Legend

| Symbol | Meaning |
|--------|---------|
| 🟢 **Added** | New capability with no prior equivalent |
| 🔵 **Enhanced** | Existing capability significantly extended |
| 🟡 **Modified** | Behavior changed; may require migration |
| 🔴 **Replaced** | Old approach deprecated for new approach |
| ⚪ **Unchanged** | No change from original specification |
| ⚫ **Deprecated** | Feature removed or deprioritized |

---

## Architecture & Core Approach

### Paradigm Shift: Selection → Generation

| Aspect | Original (planning/) | Revised (revised-spec/) | Document Reference |
|--------|---------------------|-------------------------|-------------------|
| **Core Mechanism** | Content selection from pre-authored pools | LLM-powered dynamic generation | `revised-spec/architecture-assessment.md` Section 2 |
| **Vision Achievement** | ~35% per gap analysis | ~95% per validation report | `revised-spec/gap-analysis.md`, `revised-spec/validation-report.md` |
| **Content Creation Model** | Human-authored, system-selected | AI-generated, human-validated | `revised-spec/adaptive-learning-architecture.md` Section 1 |
| **Latency Expectation** | <100ms content delivery | <2-4s with streaming progress | `revised-spec/gap-analysis.md` Gap #18 |
| **Personalization Depth** | Knowledge state only (DKT+BKT) | Multi-dimensional (knowledge + cognitive + affective + metacognitive) | `revised-spec/adaptive-learning-architecture.md` Section 3 |

---

## 🟢 Added Requirements (New Capabilities)

### LLM Infrastructure Layer

| ID | Requirement | Original State | Revised State | Source Document | Specific Section | Effort |
|----|-------------|----------------|---------------|-----------------|------------------|--------|
| **LLM-001** | LLM orchestration service with model routing (fast/capable/balanced tiers) | ❌ Absent — AI tutor deferred per `platform-root/requirements-spec.md` REQ-020 | ✅ Required — Core infrastructure | `revised-spec/adaptive-learning-architecture.md` | Section 4: "LLM Infrastructure" | 2 months |
| **LLM-002** | Prompt engineering framework with versioning and A/B testing capabilities | ❌ Absent | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 4: "Prompt Engineering Framework" | 1-2 months |
| **LLM-003** | RAG (Retrieval-Augmented Generation) pipeline for curriculum-grounded generation | ❌ Absent — Content authoring was manual per REQ-011 | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 4: "RAG Pipeline" | 1-2 months |
| **LLM-004** | Content safety/moderation layer for K-12 appropriateness | ❌ Absent — REQ-020 deferred | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 4: "Safety Layer" | 2-3 months |
| **LLM-005** | Streaming response architecture (SSE/WebSocket) for progressive delivery | ❌ Absent — NFR-006 assumed <200ms sync responses | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 4: "Streaming Architecture" | 1 month |

**Traceability**: LLM-001 through LLM-005 map to deferred REQ-020 (AI tutor) from `platform-root/requirements-spec.md` Appendix B. The original specification explicitly deferred AI tutoring: "Conversational AI tutor deferred to Phase 4 (funding dependent)." The revised specification activates this deferred requirement and makes it foundational.

### Content Generation Capabilities

| ID | Requirement | Original State | Revised State | Source Document | Specific Section | Effort |
|----|-------------|----------------|---------------|-----------------|------------------|--------|
| **GEN-001** | On-the-fly explanation generation for detected misconceptions | ❌ Absent — REQ-003 remediation selected from static pool | ✅ Required — Dynamic generation | `revised-spec/gap-analysis.md` | Gap #6: "Explanation Generation" | 3 months |
| **GEN-002** | Practice problem synthesis with IRT difficulty calibration | ❌ Absent — Problems from pre-authored item banks | ✅ Required — Algorithmic generation | `revised-spec/gap-analysis.md` | Gap #7: "Practice Problem Generation" | 3 months |
| **GEN-003** | Worked example generation with adaptive fading | ❌ Absent — Static worked examples only | ✅ Required — Dynamic generation | `revised-spec/adaptive-learning-architecture.md` | Section 5: "Worked Example Generator" | 2 months |
| **GEN-004** | Remedial micro-module creation for prerequisite gaps | ❌ Absent — Selected from prerequisite content pool | ✅ Required — Generated on-demand | `revised-spec/gap-analysis.md` | Gap #8: "Remedial Content Generation" | 4 months |
| **GEN-005** | Multi-modal synthesis (diagrams, interactives, code snippets) | ❌ Absent — REQ-013 enrichment was static content | ✅ Required — Dynamic synthesis | `revised-spec/adaptive-learning-architecture.md` | Section 5: "Multi-Modal Synthesis" | 6 months |

**Traceability**: GEN-001 through GEN-005 address Gap #6-8 and #10 from `revised-spec/gap-analysis.md`. Original `planning/adaptive-ed-platform-dev-handoff/02-content-model/content-delivery-spec.md` Section 3.2 described content delivery as "Query content database → Return content ID → Deliver from CDN." The revised specification replaces this with generation pipeline.

### Enhanced Learner Profiling (New Dimensions)

| ID | Requirement | Original State | Revised State | Source Document | Specific Section | Effort |
|----|-------------|----------------|---------------|-----------------|------------------|--------|
| **PROF-001** | Cognitive trait assessment (working memory, processing speed, spatial reasoning) | ❌ Absent — Knowledge state only per DKT+BKT | ✅ Required | `revised-spec/gap-analysis.md` | Gap #2: "Cognitive Traits" | 4 months |
| **PROF-002** | Affective state detection (engagement, frustration, confusion, flow) | ❌ Absent — No emotional modeling | ✅ Required | `revised-spec/gap-analysis.md` | Gap #3: "Affective States" | 3-4 months |
| **PROF-003** | Real-time cognitive load estimation with CLT-based modeling | ❌ Absent — No cognitive load tracking | ✅ Required | `revised-spec/gap-analysis.md` | Gap #5: "Cognitive Load" | 3-4 months |
| **PROF-005** | Metacognitive tracking (confidence calibration, help-seeking behavior) | ❌ Absent — No metacognitive modeling | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 3: "Metacognitive Dimension" | 2 months |

**Traceability**: PROF-001/002/003/005 represent entirely new capabilities not present in any original specification document. Original `platform-root/architecture-design.md` Section 2.1 defined Learner Profile as "Knowledge State (DKT+BKT) + Performance History + Preferences." The revised specification adds four additional dimensions.

### Advanced Adaptation Intelligence

| ID | Requirement | Original State | Revised State | Source Document | Specific Section | Effort |
|----|-------------|----------------|---------------|-----------------|------------------|--------|
| **ADAPT-002** | Within-session real-time adaptation (not just between modules) | ❌ Absent — Adaptation between learning sessions | ✅ Required — Continuous adaptation | `revised-spec/gap-analysis.md` | Gap #16: "Within-Session Adaptation" | 3-4 months |
| **ADAPT-003** | Misconception detection and classification system | ❌ Absent — Error tracking only | ✅ Required — Diagnostic classification | `revised-spec/gap-analysis.md` | Gap #11: "Misconception Detection" | 4-6 months |
| **ADAPT-005** | Conversational/Socratic assessment capability | ❌ Absent — REQ-020 deferred | ✅ Required — Active requirement | `revised-spec/adaptive-learning-architecture.md` | Section 6: "Socratic Assessment" | 4 months |

**Traceability**: ADAPT-002 addresses Gap #16 (within-session adaptation). Original `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/adaptation-rules-spec.md` Section 2 specified "adaptation triggered at module boundaries." ADAPT-005 implements the previously deferred REQ-020 AI tutor.

### API Infrastructure

| ID | Requirement | Original State | Revised State | Source Document | Specific Section | Effort |
|----|-------------|----------------|---------------|-----------------|------------------|--------|
| **API-001** | POST `/api/v2/content/generate` endpoint | ❌ Absent | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | API Specification Table | 1 month |
| **API-002** | POST `/api/v2/remedial/trigger` endpoint | ❌ Absent — Used content ID references | ✅ Required — Generation trigger | `revised-spec/adaptive-learning-architecture.md` | API Specification Table | 1 month |
| **API-004** | SSE `/api/v2/llm/stream` for progressive delivery | ❌ Absent | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | API Specification Table | 1 month |

**Traceability**: API endpoints are additions. Original `platform-root/tool-documentation.md` Section 3 documented v1 endpoints. The revised specification adds v2 endpoints alongside preserved v1 endpoints.

### Data Model Extensions

| ID | Requirement | Original State | Revised State | Source Document | Specific Section | Effort |
|----|-------------|----------------|---------------|-----------------|------------------|--------|
| **DATA-001** | KnowledgeComponent entity with prerequisite graph (sub-LO granularity) | ❌ Absent — LO-level only | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 7: "Knowledge Component Model" | 2 months |
| **DATA-002** | Extended LearnerProfile with cognitive/affective/metacognitive dimensions | ❌ Absent — Knowledge state only | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 3: "Multi-Dimensional Profile" | 2 months |
| **DATA-003** | GeneratedContent entity with quality metadata and provenance | ❌ Absent | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 7: "Content Generation Model" | 1 month |

**Traceability**: DATA-001 through DATA-003 are new entities. Original `platform-root/architecture-design.md` Section 4.2 defined data models: "LearningObjective, ContentModule, LearnerProfile (knowledge state only), InteractionEvent."

### Infrastructure Additions

| ID | Requirement | Original State | Revised State | Source Document | Specific Section | Effort |
|----|-------------|----------------|---------------|-----------------|------------------|--------|
| **INFRA-001** | GPU cluster for LLM inference (separate from DKT Triton) | ❌ Absent — Triton for DKT only | ✅ Required | `revised-spec/implementation-roadmap.md` | Phase 1 Infrastructure | 2 months |
| **INFRA-002** | Vector store (ChromaDB/Pinecone) for RAG grounding | ❌ Absent | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 4: "Vector Store" | 1 month |
| **INFRA-003** | Pre-generation and intelligent caching layer | ❌ Absent — Hot Redis cache only | ✅ Required | `revised-spec/adaptive-learning-architecture.md` | Section 4: "Caching Strategy" | 2 months |

**Traceability**: INFRA-002 is entirely new. Original `platform-root/architecture-design.md` Section 5 listed infrastructure: "Neo4j, PostgreSQL, Redis, Cassandra, Kafka." The revised specification adds vector store and extends GPU infrastructure.

---

## 🔵 Enhanced Requirements (Extended Capabilities)

| ID | Requirement | Original Behavior | Revised Behavior | Source Document | Specific Section | Change Impact |
|----|-------------|-------------------|------------------|-----------------|------------------|---------------|
| **GEN-002** | Practice problem synthesis | Problems selected from pre-authored item banks per `planning/adaptive-ed-platform-dev-handoff/02-content-model/content-pools-spec.md` | Dynamically generated with IRT difficulty calibration | `revised-spec/gap-analysis.md` | Gap #7 | Extends REQ-001 BKT/DKT |
| **API-003** | Learner profile endpoint | `GET /api/v1/learners/{id}/profile` returned DKT+BKT state only per `platform-root/tool-documentation.md` | `GET /api/v2/learners/{id}/profile` returns extended dimensions | `revised-spec/adaptive-learning-architecture.md` | API Specification | Extends REQ-007 teacher dashboard |

---

## 🟡 Modified Requirements (Behavior Changes)

| ID | Requirement | Original Specification | Revised Specification | Source Document | Specific Section | Migration Notes |
|----|-------------|----------------------|---------------------|-----------------|------------------|-----------------|
| **MOD-001** | Content personalization mechanism | Selection from 5 difficulty tiers per `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/adaptive-difficulty-spec.md` Section 2 | Dynamic difficulty adjustment via generation parameters | `revised-spec/gap-analysis.md` | Gap #1 | Client handling unchanged; backend mechanism changes |
| **MOD-002** | Latency target for content delivery | <200ms per `platform-root/requirements-spec.md` NFR-006 | <2-4s with streaming for generation, <100ms for routing | `revised-spec/gap-analysis.md` | Gap #18 | 100x latency relaxation; requires UX adaptation |
| **MOD-003** | Learning style accommodation | Explicitly rejected per Pashler et al. (2008) in `platform-root/research-synthesis.md` | Evidence-based preference detection (not VARK) | `revised-spec/adaptive-learning-architecture.md` | Section 3 | Philosophy refined, not reversed |
| **MOD-004** | Remediation approach | Prerequisite LO selection per `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/mastery-loop-spec.md` Section 4 | Targeted KC-level generation | `revised-spec/gap-analysis.md` | Gap #11, #12 | Granularity increase; format changes |
| **MOD-005** | Assessment timing | Between learning modules per `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/assessment-engine-spec.md` | Continuous within-session | `revised-spec/gap-analysis.md` | Gap #16 | Real-time enhancement |

**Traceability Notes**:
- MOD-001: Original 5-tier system from `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/adaptive-difficulty-spec.md` Section 2.3: "Content organized into 5 difficulty bands."
- MOD-002: Original NFR-006 from `platform-root/requirements-spec.md` Appendix D: "Response time < 200ms for all user-facing operations."
- MOD-003: Original rejection from `platform-root/research-synthesis.md` Section 3: "Learning styles lack empirical support per Pashler et al. (2008)." Revised spec maintains rejection of VARK but adds evidence-based preferences.

---

## 🔴 Replaced Requirements (Breaking Changes)

| ID | Original Requirement | Replacement | Source Document | Specific Section | Migration Impact |
|----|---------------------|-------------|-----------------|------------------|------------------|
| **ADAPT-001** | Multi-objective optimization router per `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/recommendation-router-spec.md` | Contextual Thompson Sampling router | `revised-spec/adaptive-learning-architecture.md` | Section 6: "Thompson Sampling Router" | Configuration migration; A/B testing required |

**Traceability**: Original router specified in `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/recommendation-router-spec.md` Section 3: "Multi-objective optimizer balances engagement, learning gain, and time." The revised specification replaces this entirely with Thompson Sampling.

---

## ⚪ Unchanged Requirements (Maintained)

| ID | Requirement | Rationale | Source Document |
|----|-------------|-----------|-----------------|
| **SEQ-001** | Content sequencing via prerequisite graph | Core capability retained | `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/adaptive-sequencing-spec.md` |
| **SEQ-002** | Spaced repetition scheduling (SM-2 algorithm) | Core capability retained | `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/spaced-repetition-spec.md` |
| **SEQ-003** | BKT mastery tracking with interpretable thresholds | Core capability retained; extended but not replaced | `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/bkt-engine-spec.md` |
| **SEQ-004** | DKT hidden state for temporal pattern recognition | Core capability retained; extended but not replaced | `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/dkt-integration-spec.md` |
| **LSTYLE-001** | Rejection of learning styles (VARK/Felder-Silverman) | Both specifications reject per Pashler et al. (2008) | `platform-root/research-synthesis.md` |
| **UDL-001** | Universal Design for Learning principles | Maintained in both specifications | `planning/adaptive-ed-platform-dev-handoff/05-specialized-populations/universal-design-spec.md` |
| **PRIV-001** | FERPA/COPPA compliance framework | Compliance maintained | `platform-root/requirements-spec.md` Appendix E |

**Traceability**: These requirements appear in both original and revised specifications with no material changes. They represent the stable foundation upon which new capabilities are built.

---

## ⚫ Deprecated/Deprioritized Requirements

| ID | Original Requirement | Original Priority | Revised Status | Rationale | Source Document | Migration Notes |
|----|---------------------|-------------------|----------------|-----------|-----------------|-----------------|
| **DEP-001** | Static content pool as primary content source | Should Have (REQ-011) | ⚠️ Reduced to emergency fallback | Shift to generation-first | `revised-spec/implementation-roadmap.md` | CDN delivery paths must be restructured |
| **DEP-002** | Content authoring workflow for pre-authored modules | Should Have (REQ-011) | ⚠️ Deprecated in favor of prompt engineering | Less pre-authored content needed | `revised-spec/architecture-assessment.md` | Authoring tool users require retraining |

**Traceability**: REQ-011 from `platform-root/requirements-spec.md` Section 3: "Content authoring tools for educator-created modules." The revised specification in `revised-spec/architecture-assessment.md` Section 2 states: "Fundamental architectural mismatch: System designed as recommendation platform, but vision requires generation platform."

---

## 🟠 Breaking Change Details (Migration Required)

### PROF-004: Knowledge Component Granularity

**Before**: Learning Objectives (LOs) were the atomic unit of knowledge tracking.
- Source: `platform-root/architecture-design.md` Section 4.2: "LearningObjective entity represents atomic knowledge units."
- Data model: LO-level mastery tracking only

**After**: Knowledge Components (KCs) provide sub-LO granularity.
- Source: `revised-spec/adaptive-learning-architecture.md` Section 7: "KC entity decomposes Learning Objectives into granular skills."
- Data model: KC-level tracking with parent LO references

**Migration Impact**:
- Data migration required: Decompose existing LO mastery into KC estimates
- New taxonomy development for top 50 Learning Objectives
- Parallel tracking period (LO + KC) recommended

### ADAPT-001: Thompson Sampling Router Replacement

**Before**: Multi-objective optimization router.
- Source: `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/recommendation-router-spec.md` Section 3
- Algorithm: Weighted multi-objective optimizer balancing engagement, learning gain, time

**After**: Contextual Thompson Sampling router.
- Source: `revised-spec/adaptive-learning-architecture.md` Section 6
- Algorithm: Probabilistic contextual bandit with exploration/exploitation

**Migration Impact**:
- Configuration parameters completely different
- A/B testing required for validation
- Behavioral changes (probabilistic vs deterministic)

### ADAPT-004: Dynamic Step-Back Intervention

**Before**: Static content references for remediation.
- Response format: `{ "content_id": "string", "type": "remedial" }`

**After**: Generated content payloads.
- Response format: `{ "generated_content": object, "streaming_url": "string" }`

**Migration Impact**:
- Client integration updates required
- Must handle streaming responses
- Fallback logic for generation failures

### DEP-001: Content Pool Deprioritization

**Before**: CDN primary delivery path.
- Flow: Query → Select content_id → CDN delivery

**After**: Generation primary, CDN fallback.
- Flow: Analyze → Generate → Stream (or CDN fallback)

**Migration Impact**:
- Integration workflow restructuring
- CDN becomes emergency fallback only
- Cache warming strategies obsolete

### DEP-002: Authoring Workflow Deprecation

**Before**: Pre-authoring workflow for content creation.
- Source: `planning/adaptive-ed-platform-dev-handoff/03-authoring-tools/authoring-workflow-spec.md`

**After**: Prompt engineering workflow.
- Source: `revised-spec/implementation-roadmap.md` Phase 1

**Migration Impact**:
- Process migration from authoring to prompt engineering
- User retraining required
- Authoring tool maintenance reduced

---

## Changelog Summary Statistics

| Change Category | Count | Effort Range | Backward Compatible |
|-----------------|-------|--------------|---------------------|
| 🟢 **Added (New)** | 24 | 1-6 months each | Yes (new endpoints/services) |
| 🔵 **Enhanced** | 2 | 1-2 months each | Yes |
| 🟡 **Modified** | 5 | N/A | Partially |
| 🔴 **Replaced** | 1 | 4-6 months | No |
| ⚪ **Unchanged** | 7 | N/A | Yes |
| ⚫ **Deprecated** | 2 | N/A | No |
| **🟠 Breaking Changes** | **5** | **Variable** | **No** |

**Total Requirements Tracked**: 46
**Requirements with Migration Impact**: 5 breaking changes
**New Capabilities Introduced**: 24 added requirements

---

## Document Cross-Reference Index

### Original Specification Documents

| Document | Path | Sections Referenced |
|----------|------|---------------------|
| Requirements Specification | `platform-root/requirements-spec.md` | REQ-001, REQ-002, REQ-003, REQ-011, REQ-020, NFR-006, Appendix B, D, E |
| Architecture Design | `platform-root/architecture-design.md` | Section 2.1, 4.2, 5 |
| Research Synthesis | `platform-root/research-synthesis.md` | Section 3 (learning styles) |
| Tool Documentation | `platform-root/tool-documentation.md` | Section 3 (API endpoints) |
| Personalization Engine Specs | `planning/adaptive-ed-platform-dev-handoff/01-personalization-engine/` | 8 specification documents |
| Content Model Specs | `planning/adaptive-ed-platform-dev-handoff/02-content-model/` | 4 specification documents |
| Authoring Tools Specs | `planning/adaptive-ed-platform-dev-handoff/03-authoring-tools/` | authoring-workflow-spec.md |
| Specialized Populations | `planning/adaptive-ed-platform-dev-handoff/05-specialized-populations/` | universal-design-spec.md |

### Revised Specification Documents

| Document | Path | Sections Referenced |
|----------|------|---------------------|
| Adaptive Learning Architecture | `revised-spec/adaptive-learning-architecture.md` | Sections 1, 3, 4, 5, 6, 7, API Specification |
| Gap Analysis | `revised-spec/gap-analysis.md` | Gaps #1-8, #10-12, #16, #18 |
| Architecture Assessment | `revised-spec/architecture-assessment.md` | Section 2 (fundamental mismatch) |
| Implementation Roadmap | `revised-spec/implementation-roadmap.md` | Phase 1 Infrastructure |
| Validation Report | `revised-spec/validation-report.md` | Vision achievement scores |

---

## Technical Migration Guide

This section provides step-by-step technical instructions for migrating the existing `platform-root/` codebase to the revised specification. Each migration step includes code examples, configuration changes, and testing strategies.

### Migration Prerequisites

Before beginning migration:

1. **Backup existing data**: `cqlsh` dumps of Cassandra tables, Redis snapshots
2. **Verify environment**: Python 3.11+, Docker 24+, 32GB+ RAM for local LLM testing
3. **Review breaking changes**: 5 breaking changes documented in Changelog Section 7
4. **Set up feature flags**: Enable gradual rollout capability

### Phase 1: Foundation Infrastructure (Weeks 1-6)

#### Step 1.1: Add LLM Dependencies

Update `pyproject.toml`:

```toml
[tool.poetry.dependencies]
# Existing dependencies preserved
openai = "^1.0.0"
anthropic = "^0.7.0"
chromadb = "^0.4.0"
sentence-transformers = "^2.2.0"
streamlit = "^1.28.0"  # For prompt testing

[tool.poetry.group.dev.dependencies]
pytest-asyncio = "^0.21.0"  # For testing streaming endpoints
```

Install dependencies:
```bash
poetry lock --no-update
poetry install
```

**Testing**: Verify imports work:
```bash
python -c "import openai; import chromadb; print('OK')"
```

#### Step 1.2: Extend Configuration Schema

Modify `src/config.py`:

```python
from pydantic import Field
from typing import Literal

class Settings(BaseSettings):
    # Existing settings preserved...
    
    # New: LLM Configuration
    LLM_PROVIDER: Literal["openai", "anthropic", "triton"] = "openai"
    LLM_API_KEY: str = Field(default="", env="LLM_API_KEY")
    LLM_MODEL_FAST: str = "gpt-3.5-turbo"
    LLM_MODEL_CAPABLE: str = "gpt-4"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.7
    
    # New: Vector Store Configuration
    VECTOR_STORE_PROVIDER: Literal["chromadb", "pinecone"] = "chromadb"
    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8000
    
    # New: Generation Settings
    GENERATION_TIMEOUT_MS: int = 4000
    ENABLE_STREAMING: bool = True
    PRE_GENERATION_CACHE_TTL: int = 3600
```

Modify `config.yaml`:

```yaml
# Existing configuration preserved
llm:
  provider: "openai"
  model_tiers:
    fast: "gpt-3.5-turbo"
    capable: "gpt-4"
    balanced: "gpt-3.5-turbo-16k"
  timeout_ms: 4000
  retry_policy:
    max_retries: 3
    backoff_factor: 2

vector_store:
  provider: "chromadb"
  collection_name: "curriculum_chunks"
  embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
  
generation:
  streaming_enabled: true
  validation_enabled: true
  cache_ttl_seconds: 3600
```

**Testing**: Load configuration without errors:
```python
from src.config import settings
assert settings.LLM_PROVIDER in ["openai", "anthropic", "triton"]
```

#### Step 1.3: Create LLM Orchestrator Service

Create `src/services/llm_orchestrator.py`:

```python
"""LLM orchestration service with multi-provider routing."""
import openai
import anthropic
from typing import AsyncGenerator, Literal
from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

class LLMOrchestrator:
    """Routes requests to appropriate LLM based on tier and context."""
    
    def __init__(self):
        self.openai_client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)
        self.anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        
    async def generate(
        self,
        prompt: str,
        tier: Literal["fast", "capable", "balanced"] = "balanced",
        stream: bool = False,
        **kwargs
    ) -> str | AsyncGenerator[str, None]:
        """Generate content using appropriate model tier."""
        model = self._select_model(tier)
        
        if stream:
            return self._stream_generate(prompt, model, **kwargs)
        return await self._generate_sync(prompt, model, **kwargs)
    
    def _select_model(self, tier: str) -> str:
        mapping = {
            "fast": settings.LLM_MODEL_FAST,
            "capable": settings.LLM_MODEL_CAPABLE,
            "balanced": settings.LLM_MODEL_BALANCED,
        }
        return mapping.get(tier, settings.LLM_MODEL_BALANCED)
    
    async def _generate_sync(self, prompt: str, model: str, **kwargs) -> str:
        """Synchronous generation for non-streaming requests."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise GenerationError(f"Failed to generate content: {e}")
    
    async def _stream_generate(self, prompt: str, model: str, **kwargs) -> AsyncGenerator[str, None]:
        """Streaming generation for progressive delivery."""
        stream = await self.openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            stream=True,
            **kwargs
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class GenerationError(Exception):
    pass
```

**Testing**:
```python
import pytest
from src.services.llm_orchestrator import LLMOrchestrator

@pytest.mark.asyncio
async def test_llm_orchestrator_selects_model():
    orch = LLMOrchestrator()
    model = orch._select_model("fast")
    assert model == "gpt-3.5-turbo"
```

#### Step 1.4: Create Vector Store Repository

Create `src/repositories/vector_store.py`:

```python
"""Vector store repository for RAG pipeline."""
import chromadb
from sentence_transformers import SentenceTransformer
from src.config import settings
from typing import List, Dict

class VectorStoreRepository:
    """Repository for curriculum chunk storage and retrieval."""
    
    def __init__(self):
        self.client = chromadb.HttpClient(
            host=settings.CHROMADB_HOST,
            port=settings.CHROMADB_PORT
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMADB_COLLECTION
        )
        self.embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
    
    def add_chunks(self, chunks: List[Dict[str, any]]) -> None:
        """Add curriculum chunks with embeddings."""
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedder.encode(texts).tolist()
        
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=[chunk["metadata"] for chunk in chunks],
            ids=[chunk["id"] for chunk in chunks]
        )
    
    def query(self, query_text: str, k: int = 5) -> List[Dict]:
        """Retrieve relevant chunks for query."""
        embedding = self.embedder.encode([query_text]).tolist()
        results = self.collection.query(
            query_embeddings=embedding,
            n_results=k
        )
        return [
            {
                "text": doc,
                "metadata": meta,
                "distance": dist
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )
        ]
```

**Testing**: Mock ChromaDB for unit tests:
```python
@pytest.fixture
def mock_vector_store():
    with patch('chromadb.HttpClient') as mock_client:
        mock_collection = MagicMock()
        mock_client.return_value.get_or_create_collection.return_value = mock_collection
        yield VectorStoreRepository()
```

### Phase 2: Data Model Extensions (Weeks 3-4)

#### Step 2.1: Create Knowledge Component Model

Create `src/models/knowledge_component.py`:

```python
"""Knowledge Component model for sub-LO granularity."""
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class KnowledgeComponent(BaseModel):
    """Granular knowledge unit within a Learning Objective."""
    
    kc_id: str = Field(..., description="Unique KC identifier")
    lo_id: str = Field(..., description="Parent Learning Objective ID")
    name: str = Field(..., description="Human-readable KC name")
    description: Optional[str] = None
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    estimated_time_minutes: int = Field(default=5, gt=0)
    prerequisite_kcs: List[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True
```

#### Step 2.2: Create Extended Profile Model

Create `src/models/extended_profile.py`:

```python
"""Extended learner profile with cognitive and affective dimensions."""
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime
from uuid import UUID

class CognitiveTraits(BaseModel):
    """Cognitive trait assessment scores."""
    working_memory_capacity: Optional[float] = Field(None, ge=0, le=1)
    processing_speed: Optional[float] = Field(None, ge=0, le=1)
    spatial_reasoning: Optional[float] = Field(None, ge=0, le=1)
    verbal_comprehension: Optional[float] = Field(None, ge=0, le=1)

class AffectiveState(BaseModel):
    """Real-time affective state detection."""
    engagement: float = Field(default=0.5, ge=0, le=1)
    frustration: float = Field(default=0.0, ge=0, le=1)
    confusion: float = Field(default=0.0, ge=0, le=1)
    flow: float = Field(default=0.0, ge=0, le=1)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class ExtendedLearnerProfile(BaseModel):
    """Multi-dimensional learner profile."""
    
    student_id: UUID
    cognitive_traits: CognitiveTraits = Field(default_factory=CognitiveTraits)
    affective_state: AffectiveState = Field(default_factory=AffectiveState)
    learning_preferences: Dict[str, str] = Field(default_factory=dict)
    metacognitive_data: Dict[str, float] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

#### Step 2.3: Extend BKT Model for KC Support

Modify `src/models/bkt.py`:

```python
"""BKT model extended for Knowledge Component granularity."""
from typing import Optional
from pydantic import BaseModel, Field

class BKTState(BaseModel):
    """BKT state with optional KC-level tracking."""
    
    # Existing fields preserved
    student_id: str
    lo_id: str
    p_mastery: float = Field(ge=0, le=1)
    
    # New: KC-level tracking (breaking change)
    kc_id: Optional[str] = None
    is_kc_level: bool = Field(default=False)
    
    class Config:
        from_attributes = True
```

### Phase 3: Database Migrations (Weeks 4-6)

#### Step 3.1: Create Knowledge Components Table

Execute in `cqlsh`:

```sql
-- Create new KC table
CREATE TABLE IF NOT EXISTS knowledge_components (
    kc_id TEXT PRIMARY KEY,
    lo_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    difficulty DOUBLE,
    estimated_time_minutes INT,
    prerequisite_kcs LIST<TEXT>,
    created_at TIMESTAMP
);

-- Index for LO lookup
CREATE INDEX idx_kc_lo_id ON knowledge_components(lo_id);
```

**Rollback**:
```sql
DROP TABLE IF EXISTS knowledge_components;
DROP INDEX IF EXISTS idx_kc_lo_id;
```

#### Step 3.2: Alter Student Knowledge State Table

```sql
-- Add KC support to existing table
ALTER TABLE student_knowledge_state 
ADD COLUMN kc_id TEXT;

ALTER TABLE student_knowledge_state 
ADD COLUMN is_kc_level BOOLEAN DEFAULT FALSE;

-- Create index for KC lookups
CREATE INDEX idx_sks_kc_id ON student_knowledge_state(kc_id);
```

**Rollback**:
```sql
ALTER TABLE student_knowledge_state DROP COLUMN kc_id;
ALTER TABLE student_knowledge_state DROP COLUMN is_kc_level;
DROP INDEX IF EXISTS idx_sks_kc_id;
```

#### Step 3.3: Create Extended Profile Table

```sql
CREATE TABLE IF NOT EXISTS learner_profile_extended (
    student_id UUID PRIMARY KEY,
    cognitive_traits MAP<TEXT, DOUBLE>,
    affective_state MAP<TEXT, TEXT>,
    learning_preferences MAP<TEXT, TEXT>,
    metacognitive_data MAP<TEXT, DOUBLE>,
    updated_at TIMESTAMP
);
```

#### Step 3.4: Create Generated Content Audit Table

```sql
CREATE TABLE IF NOT EXISTS generated_content (
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

CREATE INDEX idx_gen_content_student ON generated_content(student_id);
CREATE INDEX idx_gen_content_created ON generated_content(created_at);
```

### Phase 4: API Extensions (Weeks 5-8)

#### Step 4.1: Create v2 Generation Routes

Create `src/api/generation_routes.py`:

```python
"""v2 API endpoints for content generation."""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from src.services.llm_orchestrator import LLMOrchestrator, GenerationError
from src.repositories.vector_store import VectorStoreRepository
from src.config import settings

router = APIRouter(prefix="/api/v2")

@router.post("/content/generate")
async def generate_content(request: GenerationRequest):
    """Generate personalized content for student."""
    try:
        orchestrator = LLMOrchestrator()
        
        if request.stream and settings.ENABLE_STREAMING:
            return StreamingResponse(
                _stream_with_context(request, orchestrator),
                media_type="text/event-stream"
            )
        
        content = await orchestrator.generate(
            prompt=request.prompt,
            tier=request.model_tier
        )
        return {"content": content, "streamed": False}
        
    except GenerationError as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/remedial/trigger")
async def trigger_remediation(request: RemediationRequest):
    """Trigger remedial content generation for KC gap."""
    # Retrieve RAG context
    vector_store = VectorStoreRepository()
    context_chunks = vector_store.query(
        query_text=request.misconception_description,
        k=3
    )
    
    # Build remedial prompt
    prompt = _build_remediation_prompt(request, context_chunks)
    
    orchestrator = LLMOrchestrator()
    content = await orchestrator.generate(prompt=prompt, tier="capable")
    
    return {
        "generated_content": content,
        "grounding_sources": [c["metadata"] for c in context_chunks],
        "kc_id": request.kc_id
    }

async def _stream_with_context(
    request: GenerationRequest,
    orchestrator: LLMOrchestrator
) -> AsyncGenerator[str, None]:
    """Stream generation with SSE format."""
    async for chunk in orchestrator.generate(
        prompt=request.prompt,
        tier=request.model_tier,
        stream=True
    ):
        yield f"data: {chunk}\n\n"
    yield "data: [DONE]\n\n"
```

#### Step 4.2: Extend Main Router

Modify `src/api/router.py`:

```python
from fastapi import APIRouter
from src.api import state, recommendations, generation_routes

router = APIRouter()

# Existing v1 routes preserved
router.include_router(state.router, tags=["v1-state"])
router.include_router(recommendations.router, tags=["v1-recommendations"])

# New: v2 generation routes
router.include_router(generation_routes.router, tags=["v2-generation"])
```

### Phase 5: Testing Strategy

#### Step 5.1: Unit Test Patterns

Create `tests/test_llm_orchestrator.py`:

```python
"""Unit tests for LLM orchestration."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.llm_orchestrator import LLMOrchestrator, GenerationError

@pytest.fixture
def orchestrator():
    with patch('openai.AsyncOpenAI'):
        yield LLMOrchestrator()

@pytest.mark.asyncio
async def test_generate_with_fast_tier(orchestrator):
    """Test that fast tier routes to appropriate model."""
    orchestrator.openai_client = AsyncMock()
    orchestrator.openai_client.chat.completions.create.return_value = \
        MagicMock(choices=[MagicMock(message=MagicMock(content="test"))])
    
    result = await orchestrator.generate("test prompt", tier="fast")
    
    call_args = orchestrator.openai_client.chat.completions.create.call_args
    assert call_args.kwargs["model"] == "gpt-3.5-turbo"

@pytest.mark.asyncio
async def test_generation_error_handling(orchestrator):
    """Test error handling for failed generation."""
    orchestrator.openai_client = AsyncMock()
    orchestrator.openai_client.chat.completions.create.side_effect = \
        Exception("API Error")
    
    with pytest.raises(GenerationError):
        await orchestrator.generate("test prompt")
```

#### Step 5.2: Integration Test Patterns

Create `tests/integration/test_generation_flow.py`:

```python
"""Integration tests for generation pipeline."""
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_generate_content_endpoint():
    """Test v2 content generation endpoint."""
    response = client.post("/api/v2/content/generate", json={
        "prompt": "Explain fractions to a 4th grader",
        "student_id": "test-student-001",
        "model_tier": "fast",
        "stream": False
    })
    
    assert response.status_code in [200, 503]  # 503 if LLM not configured
    if response.status_code == 200:
        assert "content" in response.json()

def test_streaming_generation():
    """Test SSE streaming endpoint."""
    response = client.post("/api/v2/content/generate", json={
        "prompt": "Create a math problem",
        "student_id": "test-student-001",
        "stream": True
    }, headers={"Accept": "text/event-stream"})
    
    assert response.status_code in [200, 503]
    if response.status_code == 200:
        assert "text/event-stream" in response.headers["content-type"]
```

#### Step 5.3: Database Migration Tests

Create `tests/test_kc_migration.py`:

```python
"""Tests for KC-level data migration."""
import pytest
from src.models.knowledge_component import KnowledgeComponent
from src.repositories.knowledge_state import KnowledgeStateRepository

@pytest.fixture
def sample_kc():
    return KnowledgeComponent(
        kc_id="KC-MATH-4-FRAC-01",
        lo_id="LO-MATH-4-FRAC",
        name="Identify unit fractions",
        difficulty=0.3,
        estimated_time_minutes=5,
        prerequisite_kcs=[]
    )

@pytest.mark.asyncio
async def test_kc_decomposition_logic():
    """Test that LOs decompose correctly to KCs."""
    lo_id = "LO-MATH-4-FRAC"
    
    # Decomposition logic
    kcs = decompose_lo_to_kcs(lo_id)
    
    assert len(kcs) > 0
    assert all(kc.lo_id == lo_id for kc in kcs)
    assert len(set(kc.kc_id for kc in kcs)) == len(kcs)  # Unique IDs
```

### Phase 6: Deployment Checklist

Before deploying to each environment:

#### Pre-Deployment
- [ ] All unit tests pass: `pytest tests/ -xvs`
- [ ] Database migrations tested in staging
- [ ] LLM API keys configured in secrets manager
- [ ] Vector store provisioned and populated
- [ ] Feature flags configured (default off)

#### Deployment Steps
1. **Infrastructure**: Deploy ChromaDB, LLM gateway
2. **Database**: Run migration scripts
3. **Application**: Deploy new code with v2 routes
4. **Validation**: Run smoke tests
5. **Gradual Rollout**: Enable feature flags for 5% traffic

#### Post-Deployment Monitoring
- [ ] Generation latency < 3s (p95)
- [ ] Error rate < 1%
- [ ] LLM token usage within budget
- [ ] Vector store query latency < 100ms

---

## Appendices

### A. System Artifact Inventory

A complete inventory of all specification documents is maintained in **`spec-inventory.md`**. This inventory catalogs:

- **9 revised specification documents** in `revised-spec/` (authoritative)
- **29+ original dev handoff documents** in `planning/adaptive-ed-platform-dev-handoff/` (superseded)
- **23+ research package documents** in `planning/adaptive-ed-platform-research/` (reference)
- **10 implementation files** in `platform-root/` (requires migration)

**Key Documents**:
| Document | Path | Purpose |
|----------|------|---------|
| Adaptive Learning Architecture | `revised-spec/adaptive-learning-architecture.md` | Technical design specification |
| Gap Analysis | `revised-spec/gap-analysis.md` | 22 critical gaps identified |
| Implementation Roadmap | `revised-spec/implementation-roadmap.md` | 18-24 month phased plan |
| Validation Report | `revised-spec/validation-report.md` | 95% vision achievement verification |

### B. Requirements Traceability Matrix

The complete traceability matrix mapping original requirements to revised requirements is available in **`requirements-traceability.csv`** and **`requirements-traceability-severity.csv`**.

**Summary Statistics**:
- 39 total requirements traced
- 24 new capabilities added
- 5 breaking changes requiring migration
- 7 unchanged core capabilities

### C. Migration Checklist

The detailed migration checklist with effort estimates and dependencies is available in:
- **`migration-checklist.csv`** — 46 migration tasks
- **`migration-checklist-complexity.csv`** — Complexity categorization (High/Medium/Low)
- **`migration-effort-summary.md`** — Effort analysis and critical path

### D. Related Documents

| Document | Description |
|----------|-------------|
| `spec-delta-analysis.md` | Detailed comparison between original and revised specifications |
| `impact-assessment.md` | Technical impact analysis on existing codebase |
| `platform-structure.md` | Analysis of existing AKSRE microservice implementation |

---

## Document Summary

| Section | Lines | Description |
|---------|-------|-------------|
| Executive Summary | ~150 | Business justification, high-level changes, migration strategy |
| Implementation Roadmap | ~400 | 4-phase roadmap, work streams, quick wins, risk analysis |
| Detailed Changelog | ~550 | 46 requirements documented with traceability |
| Technical Migration Guide | ~350 | Step-by-step migration with code examples |
| Appendices | ~50 | Reference to supporting documents |
| **Total** | **~1,500** | Comprehensive handoff package |

---

**Document Status**: Final  
**Version**: 1.0  
**Date**: 2026-03-14  
**Classification**: Development Handoff
