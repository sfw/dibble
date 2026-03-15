---
classification: Technical Reference
date: '2026-03-14'
version: '1.0'
---

# Platform-Root Codebase Structure Analysis

## Executive Summary

This document provides a comprehensive analysis of the `platform-root/` directory containing the **Adaptive Knowledge State & Recommendation Engine (AKSRE)**—a FastAPI-based microservice implementing Bayesian Knowledge Tracing (BKT) for the Adaptive K-12 Learning Platform.

**Key Findings:**
- **Target System**: AKSRE—core personalization microservice for real-time student knowledge state tracking
- **Technology Stack**: Python 3.11+, FastAPI, Redis (hot cache), Cassandra (persistent), Kafka (events)
- **Architecture**: Hybrid storage with circuit breaker fault tolerance, event-driven design
- **Implementation Status**: Complete MVP implementation with BKT-only knowledge tracing; DKT integration stubbed for Phase 2
- **Quality**: Verified against requirements, includes comprehensive tests, documentation, and Docker deployment configs

## Directory Contents Overview

The `platform-root/` directory contains **10 files** organized as implementation artifacts for the AKSRE microservice:

| File | Type | Size | Purpose |
|------|------|------|---------|
| `architecture-design.md` | Markdown | ~24KB | Technical architecture specification |
| `requirements-spec.md` | Markdown | ~65KB | Complete requirements (sections + 5 appendices) |
| `requirements-validation.md` | Markdown | ~13KB | Validated requirements with resolved ambiguities |
| `research-synthesis.md` | Markdown | ~19KB | Technical context from research synthesis |
| `tool-source.md` | Markdown | ~87KB | Complete Python source code |
| `tool-documentation.md` | Markdown | ~21KB | API documentation and usage guide |
| `verification-report.md` | Markdown | ~20KB | Implementation verification results |
| `evidence-ledger.csv` | CSV | ~75KB | Evidence tracking and artifacts |
| `handoff-inventory.md` | Markdown | ~7.5KB | Planning directory catalog |
| `validity-scorecard.json` | JSON | ~1KB | Validity metrics |

**Total Size**: ~312KB of structured technical documentation and source code.

## System Architecture

## Core Component: AKSRE Microservice

The Adaptive Knowledge State & Recommendation Engine (AKSRE) is a specialized microservice that implements the platform's personalization layer.

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AKSRE SERVICE                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ API Controller│◄──►│  BKT Engine  │◄──►│  DKT Client  │  │
│  │  (REST/gRPC) │    │ (Inference)  │    │  (Triton)    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┘  │
│         │                   │                               │
│         ▼                   ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Knowledge State Repository                │   │
│  │                                                     │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │Hot Cache │  │Persistent│  │Event Log │          │   │
│  │  │(Redis)   │  │(Cass.)   │  │(Kafka)   │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Service Boundaries

**IN SCOPE (AKSRE owns):**
- Knowledge state storage and retrieval
- BKT parameter management (P(L), P(T), P(G), P(S))
- Mastery probability computation
- Spaced repetition scheduling (SM2)
- DKT inference client integration (Phase 2)
- Learning interaction event processing

**OUT OF SCOPE (other services):**
- Content selection/ranking (Recommendation Service)
- Content delivery/rendering (Delivery Service)
- Prerequisite graph traversal (Learning Graph Service)
- Authentication/authorization (Auth Service)
- IRT diagnostics (Assessment Service)

## Technology Stack

## Runtime and Framework

| Layer | Technology | Version | Justification |
|-------|------------|---------|---------------|
| Language | Python | 3.11+ | Rich ML ecosystem, async support |
| Web Framework | FastAPI | 0.104+ | Auto-generated OpenAPI, async I/O |
| Data Validation | Pydantic | v2.5+ | Type safety, serialization |
| Server | Uvicorn | 0.24+ | ASGI server with HTTP/2 |

## Storage Layer

| Store | Technology | Purpose | Latency Target |
|-------|------------|---------|----------------|
| Hot Cache | Redis Cluster 7.x | Real-time state reads | <5ms |
| Persistent | Cassandra 4.x | Time-series interaction data | <15ms |
| Event Stream | Apache Kafka | Async event publishing | Fire-and-forget |
| ML Inference | NVIDIA Triton 2.x | GPU DKT predictions (Phase 2) | <10ms |

## Observability

| Component | Technology | Purpose |
|-----------|------------|---------|
| Logging | structlog + python-json-logger | Structured JSON logging |
| Metrics | prometheus-client | Application metrics |
| Tracing | Jaeger (via config) | Distributed tracing |

## Resilience

| Pattern | Implementation | Configuration |
|---------|----------------|---------------|
| Circuit Breaker | Custom implementation | Redis: 5 failures/30s, Cassandra: 10/60s |
| Retry Logic | tenacity library | Exponential backoff |
| Health Checks | FastAPI endpoints | Liveness + Readiness probes |

## Deployment

| Component | Technology |
|-----------|------------|
| Containerization | Docker multi-stage build |
| Orchestration | Kubernetes (planned) |
| Local Dev | Docker Compose |
| Monitoring | Prometheus + Grafana |

## Source Code Organization

## Project Structure (from tool-source.md)

```
aksre/
├── pyproject.toml              # Project dependencies
├── config.yaml                 # Runtime configuration
├── Dockerfile                  # Multi-stage container build
├── docker-compose.yml          # Local development stack
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── bkt.py              # BKT data models (BKTParams, BKTState)
│   │   ├── requests.py         # API request schemas
│   │   └── responses.py        # API response schemas
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── bkt_engine.py       # Bayesian inference engine
│   │   └── sm2_scheduler.py    # SM2 spaced repetition
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── knowledge_state.py  # Repository interface
│   │   ├── redis_store.py      # Redis implementation
│   │   └── cassandra_store.py  # Cassandra implementation
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py           # API route definitions
│   │   ├── state.py            # State endpoints (GET/POST)
│   │   └── recommendations.py  # Recommendation endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── event_publisher.py  # Kafka event publishing
│   │   └── circuit_breaker.py  # Fault tolerance
│   └── utils/
│       ├── __init__.py
│       ├── logging.py          # Structured logging
│       └── errors.py           # Error definitions
└── tests/
    ├── __init__.py
    ├── test_bkt_engine.py      # BKT algorithm tests
    ├── test_api.py             # API endpoint tests
    └── test_integration.py     # Integration tests
```

## Key Source Files

| File | Lines | Purpose |
|------|-------|---------|
| `bkt_engine.py` | ~120 | Bayesian Knowledge Tracing implementation |
| `sm2_scheduler.py` | ~100 | SM2 algorithm for spaced repetition |
| `redis_store.py` | ~150 | Redis repository with circuit breaker |
| `cassandra_store.py` | ~200 | Cassandra repository with schema |
| `state.py` | ~150 | REST endpoints for knowledge state |
| `recommendations.py` | ~80 | Recommendation scoring endpoint |

## API Endpoints

## Implemented REST Endpoints

| Endpoint | Method | Description | Latency Target |
|----------|--------|-------------|----------------|
| `/students/{id}/knowledge-state` | GET | Retrieve BKT state for student | <50ms |
| `/students/{id}/knowledge-state/update` | POST | Update state from interaction | <50ms |
| `/personalization/recommendations` | POST | Get scored content recommendations | <100ms |
| `/students/health/live` | GET | Liveness probe | <5ms |
| `/students/health/ready` | GET | Readiness probe (checks deps) | <10ms |

## Request/Response Models

**UpdateRequest** (`models/requests.py`):
```python
{
  "lo_id": str,                    # Learning objective ID
  "interaction": {
    "content_module_id": UUID,
    "correctness": float,          # 0.0-1.0
    "time_spent_seconds": int,
    "hints_used": int,
    "timestamp": datetime
  },
  "context": dict                  # Optional metadata
}
```

**UpdateResponse** (`models/responses.py`):
```python
{
  "student_id": UUID,
  "lo_id": str,
  "previous_p_mastery": float,     # Before update
  "current_p_mastery": float,      # After update
  "is_mastered": bool,
  "next_review_at": datetime,
  "processing_time_ms": int
}
```

## Data Models

## BKT State Model

**BKTState** (`models/bkt.py`):

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `student_id` | UUID | Student identifier | Required |
| `lo_id` | str | Learning objective ID | Required |
| `p_mastery` | float | P(mastered) | 0.0-1.0 |
| `p_learn` | float | P(learn) | 0.0-1.0 |
| `p_guess` | float | P(guess) | 0.0-1.0 |
| `p_slip` | float | P(slip) | 0.0-1.0 |
| `attempt_count` | int | Total attempts | >=0 |
| `is_mastered` | bool | Mastery achieved | Computed |
| `next_review_at` | datetime | Next review time | Optional |

## BKT Parameter Defaults

| Parameter | Symbol | Default | Description |
|-----------|--------|---------|-------------|
| Initial mastery | P(L₀) | 0.30 | Prior probability of mastery |
| Learning rate | P(T) | 0.20 | Probability of transitioning to mastered |
| Guess rate | P(G) | 0.15 | Probability of correct without mastery |
| Slip rate | P(S) | 0.10 | Probability of incorrect despite mastery |
| Mastery threshold | — | 0.80 | Threshold for `is_mastered=true` |
| Min attempts | — | 3 | Minimum attempts before mastery check |

## SM2 Data Model

**SM2Data** (`engines/sm2_scheduler.py`):

| Field | Type | Description |
|-------|------|-------------|
| `interval` | int | Days until next review |
| `repetitions` | int | Successful review count |
| `easiness_factor` | float | 1.3-2.5, starts at 2.5 |
| `next_review_at` | datetime | Calculated review time |

## Algorithm Implementations

## Bayesian Knowledge Tracing (BKT)

**Core Update Formula** (`engines/bkt_engine.py`):

```python
# Prior probability of correctness
p_correct = (1 - p_slip) * p_mastery + p_guess * (1 - p_mastery)

# Bayes' rule update
if correct:
    p_l_given_obs = ((1 - p_slip) * p_mastery) / p_correct
else:
    p_l_given_obs = (p_slip * p_mastery) / (1 - p_correct)

# Apply learning transition
new_p_mastery = p_l_given_obs + (1 - p_l_given_obs) * p_learn
```

**Success Probability Prediction**:
```python
p_success = p_mastery * (1 - p_slip) + (1 - p_mastery) * p_guess
```

**Target Accuracy**: AUC ≥ 0.75 (MVP), AUC ≥ 0.85 (Phase 2 with DKT)

## SM-2 Spaced Repetition

**Quality Rating** (converts correctness to SM2 scale):
```python
quality = min(5, int(performance * 5))
# 0.0-0.2 → 0 (blackout)
# 0.2-0.4 → 1 (incorrect)
# 0.4-0.6 → 2 (correct with difficulty)
# 0.6-0.8 → 3 (correct with hesitation)
# 0.8-1.0 → 4-5 (correct with ease)
```

**Easiness Factor Update**:
```python
delta_ef = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
new_ef = max(1.3, easiness_factor + delta_ef)
```

**Interval Calculation**:
```python
if quality < 3:
    interval = 1  # Reset
elif repetitions == 0:
    interval = 1
elif repetitions == 1:
    interval = 6
else:
    interval = round(previous_interval * ef)
```

## Storage Layer

## Redis Key Schema (Hot Cache)

| Key Pattern | Data Type | Contents |
|-------------|-----------|----------|
| `ks:{student_id}:{lo_id}` | Hash | BKT params, attempt count, mastery flag |
| `ks:{student_id}:{lo_id}:sm2` | Hash | Interval, repetitions, easiness factor |

**TTL**: 24 hours (configurable via `redis.ttl_seconds`)

## Cassandra Schema (Persistent)

**Table: `student_knowledge_state`**
```sql
CREATE TABLE student_knowledge_state (
    student_id UUID,
    lo_id TEXT,
    timestamp TIMESTAMP,
    p_mastery DOUBLE,
    p_learn DOUBLE,
    p_guess DOUBLE,
    p_slip DOUBLE,
    interaction_count INT,
    PRIMARY KEY ((student_id, lo_id), timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC)
```

**Table: `student_sm2_data`**
```sql
CREATE TABLE student_sm2_data (
    student_id UUID,
    lo_id TEXT,
    interval_days INT,
    repetitions INT,
    easiness_factor DOUBLE,
    last_reviewed_at TIMESTAMP,
    next_review_at TIMESTAMP,
    PRIMARY KEY ((student_id, lo_id))
)
```

## Write Strategy

1. **Synchronous**: Redis (immediate consistency for reads)
2. **Asynchronous**: Cassandra (durability via event publisher)
3. **Read Path**: Always from Redis (hot path)
4. **Fallback**: Direct Cassandra access if Redis unavailable

## Error Handling & Resilience

## Error Hierarchy

| Error Class | HTTP Status | Use Case |
|-------------|-------------|----------|
| `ValidationError` | 400 | Invalid request data |
| `NotFoundError` | 404 | Student or LO not found |
| `DependencyError` | 503 | Redis/Cassandra/DKT unavailable |
| `AKSREError` (base) | 500 | Internal errors |

## Fallback Chain (4 Levels)

```
Level 1: Hybrid (DKT + BKT) ──► DKT timeout/failure
    ↓
Level 2: BKT-only ────────────► Redis failure
    ↓
Level 3: Cached State ────────► No cache
    ↓
Level 4: Default Parameters
```

## Circuit Breaker Configuration

| Dependency | Failure Threshold | Recovery Timeout |
|------------|-------------------|------------------|
| Redis | 5 errors in 60s | 30 seconds |
| Cassandra | 10 errors in 60s | 60 seconds |
| DKT (Phase 2) | 3 errors in 30s | 20 seconds |

**States**: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing recovery)

## Configuration Management

## Configuration Sources (Priority Order)

1. **Environment variables** (highest priority)
2. **YAML config file** (`config.yaml`)
3. **Default values** in Pydantic models

## Key Environment Variables

| Variable | Maps To | Default |
|----------|---------|---------|
| `AKSRE_LOG_LEVEL` | `log_level` | INFO |
| `AKSRE_ENVIRONMENT` | `environment` | development |
| `REDIS_HOST` | `redis.host` | localhost |
| `REDIS_PORT` | `redis.port` | 6379 |
| `CASSANDRA_HOSTS` | `cassandra.hosts` | localhost |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka.bootstrap_servers` | localhost:9092 |
| `DKT_ENABLED` | `dkt.enabled` | false |

## Configurable BKT Parameters

| Parameter | Environment Variable | Default |
|-----------|---------------------|---------|
| P(L₀) | `BKT_P_L0` | 0.30 |
| P(T) | `BKT_P_T` | 0.20 |
| P(G) | `BKT_P_G` | 0.15 |
| P(S) | `BKT_P_S` | 0.10 |
| Mastery threshold | `BKT_MASTERY_THRESHOLD` | 0.80 |
| Min attempts | `BKT_MIN_ATTEMPTS` | 3 |

## Testing & Verification

## Test Suite

**Unit Tests** (`tests/test_bkt_engine.py`):
- Initial state creation with defaults
- Correct/incorrect response updates
- Mastery threshold detection
- Minimum attempts requirement
- Success probability prediction formula
- Multiple sequential updates
- Confidence calculation

**API Tests** (`tests/test_api.py`):
- Liveness/readiness probes
- Knowledge state GET/POST
- Validation error handling
- Recommendation endpoint

## Verification Results

From `verification-report.md`:

| Criterion | Target | Status |
|-----------|--------|--------|
| BKT Algorithm Correctness | Bayes' rule properly applied | ✅ PASS |
| SM2 Scheduler Accuracy | SM2 formula implemented | ✅ PASS |
| API Contract Compliance | Matches OpenAPI spec | ✅ PASS |
| Error Handling | 4-level fallback chain | ✅ PASS |
| Latency Targets | <50ms update, <100ms predict | ✅ ARCHITECTURE SUPPORTS |
| Test Coverage | Unit tests present | ✅ PASS |
| Code Quality | Type hints, structured logging | ✅ PASS |

**Overall**: PASS with minor observations (DKT stubbed as planned for Phase 2)

## Documentation Artifacts

## Primary Documents

| Document | Purpose | Audience |
|----------|---------|----------|
| `architecture-design.md` | Component architecture, data flows, interfaces | System architects |
| `requirements-spec.md` | Full requirements with 5 appendices (A-E) | Product, Engineering |
| `requirements-validation.md` | Resolved ambiguities, assumptions documented | Engineering leads |
| `research-synthesis.md` | Evidence-based technical decisions | Data scientists |
| `tool-source.md` | Complete source code reference | Developers |
| `tool-documentation.md` | API reference, quickstart guide | API consumers |
| `verification-report.md` | Implementation verification results | QA, Engineering |

## Related Planning Documents

The `platform-root/` implementation is derived from specifications in `planning/adaptive-ed-platform-dev-handoff/`:
- Executive summary and developer quickstart
- Architecture overview and component specs
- Platform specs (API contracts, database schema)
- UX specifications and user flows
- Security architecture and threat model
- Implementation roadmap and requirements backlog

## Dependencies & Relationships

## External Service Dependencies

| Service | Protocol | Purpose | Criticality |
|---------|----------|---------|-------------|
| Redis | Redis protocol | Hot cache | Critical (has fallback) |
| Cassandra | CQL | Persistent storage | Critical (has fallback) |
| Kafka | Kafka protocol | Event streaming | Non-critical (fire-and-forget) |
| Triton (Phase 2) | gRPC | DKT inference | Non-critical (BKT fallback) |
| Learning Graph | HTTP/REST | Prerequisite queries | Non-critical (cached) |

## Document Dependencies

```
requirements-spec.md
    ├── requirements-validation.md (resolves ambiguities)
    ├── architecture-design.md (implements architecture)
    └── research-synthesis.md (evidence base)

architecture-design.md
    ├── tool-source.md (implements design)
    └── tool-documentation.md (documents API)

tool-source.md
    └── verification-report.md (verifies implementation)
```

## Downstream Consumers

- **Recommendation Service**: Consumes scored LOs from `/recommendations`
- **Analytics Service**: Consumes Kafka events for reporting
- **Teacher Dashboard**: Reads knowledge states via API
- **ML Pipeline**: Uses interaction data for model retraining

## Summary & Next Steps

## Current State Summary

The `platform-root/` directory contains a **complete, verified MVP implementation** of the AKSRE microservice:

✅ **Architecture**: Well-defined with clear service boundaries  
✅ **Implementation**: Full Python source with BKT + SM2 algorithms  
✅ **Quality**: Type hints, structured logging, circuit breakers  
✅ **Testing**: Unit tests for core algorithms and API endpoints  
✅ **Documentation**: Comprehensive API docs and architecture specs  
✅ **Deployment**: Docker multi-stage build + Compose configuration  

## Phase 2 Readiness

The codebase is structured for Phase 2 DKT integration:
- DKT client class stubbed with Triton gRPC interface
- Circuit breaker configured (50ms timeout, 3-failure threshold)
- `dkt_enabled` feature flag in configuration
- `dkt_prediction` field in response models
- Hybrid scoring logic location identified

## Key Gaps Identified

| Gap | Impact | Mitigation |
|-----|--------|------------|
| No live integration tests | Medium | Docker Compose test setup needed |
| DKT not implemented | Low | Planned for Phase 2 |
| Rate limiting middleware | Low | Add before production |
| Production K8s manifests | Low | Create from architecture spec |

## Recommended Next Actions

1. **Compare with revised-spec/** to identify delta requirements
2. **Update architecture** if revised spec changes scope
3. **Implement migrations** for any schema changes
4. **Run integration tests** against live Redis/Cassandra
