# Migration Effort Summary: Complexity and Sequencing Analysis

## Overview

This document provides detailed effort estimates, complexity categorization, and dependency sequencing for migrating the AKSRE platform to the revised LLM-powered generative architecture.

## Effort Summary by Complexity

| Complexity Level | Task Count | Total Effort | % of Total |
|------------------|------------|--------------|------------|
| **High** | 8 | 34 weeks | 42% |
| **Medium** | 20 | 38 weeks | 47% |
| **Low** | 15 | 12 weeks | 11% |
| **N/A (No Change)** | 3 | 0 | 0% |
| **TOTAL** | **46** | **~84 weeks** | **100%** |

## Complexity Classification

### High Complexity Tasks (8 tasks, 34 weeks)

| Task ID | Module | Effort | Key Challenge |
|---------|--------|--------|---------------|
| MIG-001 | LLM Orchestrator | 2 weeks | Multi-provider abstraction; fallback handling |
| MIG-004 | Content Validator | 2 weeks | Safety/quality validation; edge case coverage |
| MIG-007 | Thompson Sampler | 3 weeks | Contextual bandits; A/B testing integration |
| MIG-008 | Generation Engine | 4 weeks | RAG integration; streaming; latency optimization |
| MIG-009 | Affective Classifier | 3 weeks | Real-time inference; accuracy/performance tradeoff |
| MIG-012 | BKT Engine Extension | 3 weeks | KC granularity; backward compatibility |
| MIG-036 | KC Database | 4 weeks | Schema design; prerequisite relationships |
| MIG-040 | LO to KC Mapping | 6 weeks | Expert validation; taxonomy development |

### Medium Complexity Tasks (20 tasks, 38 weeks)

| Task ID | Module | Effort | Key Challenge |
|---------|--------|--------|---------------|
| MIG-002 | RAG Retriever | 1 week | Query optimization; relevance scoring |
| MIG-005 | KC Data Model | 1 week | Relationship modeling; validation |
| MIG-006 | Extended Profile | 1 week | Multi-dimensional data structure |
| MIG-010 | Generation Routes | 2 weeks | API design; streaming support |
| MIG-011 | Vector Store Repo | 1 week | ChromaDB/Pinecone abstraction |
| MIG-013 | API Router v2 | 2 weeks | Endpoint organization; versioning |
| MIG-014 | Recommendations | 2 weeks | Router integration; fallback logic |
| MIG-022 | KC State Operations | 1 week | Repository pattern extension |
| MIG-026-030 | Test Suite | 5 weeks | Comprehensive coverage; mocking LLM |
| MIG-037-039 | Database Migrations | 5 weeks | Schema changes; data integrity |
| MIG-041 | Historical Migration | 3 weeks | Data transformation; validation |
| MIG-042-044 | Infrastructure | 4 weeks | Provisioning; networking; security |
| MIG-046 | API Documentation | 1 week | OpenAPI spec; examples |

### Low Complexity Tasks (15 tasks, 12 weeks)

| Task ID | Module | Effort | Description |
|---------|--------|--------|-------------|
| MIG-003 | Prompt Manager | 1 week | Template versioning |
| MIG-015 | State Endpoints | 1 week | Profile v2 API |
| MIG-016-018 | Model Updates | ~2 weeks | Schema additions |
| MIG-019-025 | Configuration | ~2 weeks | Settings; dependencies |
| MIG-023-024 | Service Updates | 5 days | Event publishing; errors |
| MIG-031-032 | Directories | 6 days | Prompt structure |
| MIG-045 | LLM Integration | 3 days | API configuration |

## Dependency Graph

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

## Critical Path Analysis

**Longest Path (Critical Path)**: 24 weeks
- MIG-005 → MIG-012 → MIG-040 → MIG-041 (KC taxonomy development and migration)
- MIG-006 → MIG-007 → MIG-014 (Thompson Sampling router implementation)
- MIG-042/MIG-043 → MIG-001 → MIG-008 → MIG-010 (Generation pipeline)

## Risk Factors by Complexity

### High Complexity Risks

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

### Medium Complexity Risks

| Task ID | Risk Factor | Mitigation Strategy |
|---------|-------------|---------------------|
| MIG-002 | Vector store query performance | Benchmark early; index optimization; caching layer |
| MIG-010 | Streaming API backward compatibility | Versioned endpoints; client SDK updates |
| MIG-022 | KC state operations data consistency | Transaction wrapper; eventual consistency acceptable |
| MIG-026-030 | Test coverage gaps | Incremental test addition; integration test priority |
| MIG-041 | Historical data transformation errors | Validation sampling; rollback scripts; audit logging |

### Low Complexity Risks

| Task ID | Risk Factor | Mitigation Strategy |
|---------|-------------|---------------------|
| MIG-015-025 | Configuration drift | Environment validation; automated config testing |
| MIG-031-032 | Prompt directory structure changes | Document conventions; code review checklist |
| MIG-045 | API key rotation management | Secrets manager integration; automated rotation |

## Suggested Sequencing

### Sequence 1: Infrastructure First (Weeks 1-4)
1. **MIG-042** Vector store provisioning
2. **MIG-043** LLM gateway deployment
3. **MIG-045** Commercial LLM configuration
4. **MIG-044** GPU expansion (can parallelize with development)

### Sequence 2: Foundation Models (Weeks 1-6)
5. **MIG-005** KC data model (blocks MIG-012, MIG-036)
6. **MIG-006** Extended profile model (blocks MIG-007, MIG-037)
7. **MIG-036** KC database table
8. **MIG-037** Extended profile database table

### Sequence 3: Core Services (Weeks 4-10)
9. **MIG-001** LLM orchestrator (blocks MIG-008)
10. **MIG-002** RAG retriever (blocks MIG-008)
11. **MIG-003** Prompt manager
12. **MIG-008** Generation engine (CRITICAL - blocks MIG-004, MIG-010)

### Sequence 4: Quality & Safety (Weeks 10-14)
13. **MIG-004** Content validator
14. **MIG-009** Affective classifier
15. **MIG-038** Generated content audit table

### Sequence 5: Algorithm Migration (Weeks 8-18)
16. **MIG-007** Thompson Sampling router
17. **MIG-012** BKT engine KC extension
18. **MIG-014** Recommendations integration

### Sequence 6: Data Migration (Weeks 12-24)
19. **MIG-040** KC taxonomy (CRITICAL PATH - longest task)
20. **MIG-039** Student knowledge state migration
21. **MIG-041** Historical mastery transformation

### Sequence 7: API Integration (Weeks 16-24)
22. **MIG-010** Generation routes
23. **MIG-013** API router v2
24. **MIG-015** State endpoints v2

## Team Allocation Recommendation

Based on task dependencies and complexity distribution:

| Team | Focus | Size | Tasks |
|------|-------|------|-------|
| **Team A** | Infrastructure | 2 engineers | MIG-042, MIG-043, MIG-044, MIG-045 |
| **Team B** | Data Layer | 2 engineers | MIG-005, MIG-006, MIG-036, MIG-037 |
| **Team C** | Generation Core | 3 engineers | MIG-001, MIG-002, MIG-003, MIG-008, MIG-004 |
| **Team D** | Adaptation | 2 engineers | MIG-007, MIG-009, MIG-012, MIG-014 |
| **Team E** | Data Migration | 1 engineer + experts | MIG-040, MIG-039, MIG-041 |
| **Team F** | API/Integration | 2 engineers | MIG-010, MIG-013, MIG-015, MIG-022 |

**Total Recommended**: 12 engineers for 6 months (parallel streams), reducing to 6 engineers for months 7-12.

## Quick Reference: Migration Checklist with Complexity

See `migration-checklist-complexity.csv` for the complete annotated checklist with complexity classifications.
