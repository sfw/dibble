---
based_on:
- requirements-spec.md
- requirements-validation.md
- research-synthesis.md
classification: Technical Architecture
date: '2026-03-14'
version: '1.0'
---

# AKSRE Architecture Design

## Executive Summary

This document describes the architecture for the **Adaptive Knowledge State & Recommendation Engine (AKSRE)**, a core microservice implementing hybrid DKT+BKT knowledge tracing for the Adaptive K-12 Learning Platform.

**Target Tool**: AKSRE provides real-time student knowledge state management, BKT-based mastery inference, and learning interaction processing.

**Success Criteria**:
- Knowledge tracing AUC ≥ 0.75 (MVP BKT-only), ≥ 0.85 (Phase 2 Hybrid)
- API latency: <50ms for updates, <100ms for predictions (p95)
- Throughput: 10K+ updates/second
- Storage: 50TB+ learning interaction data

**Source Documents**: Based on validated requirements (requirements-spec.md, requirements-validation.md, research-synthesis.md).

## Component Architecture

## 2.1 High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AKSRE SERVICE                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │  API Controller │    │  BKT Engine     │    │  DKT Client     │        │
│  │  (REST/gRPC)    │◄──►│  (Inference)    │◄──►│  (Triton)       │        │
│  │                 │    │                 │    │                 │        │
│  │ - /recommend    │    │ - P(L) compute  │    │ - Hidden state  │        │
│  │ - /update       │    │ - Mastery gate  │    │ - Prediction    │        │
│  │ - /state        │    │ - SM2 schedule  │    │ - AUC feedback  │        │
│  └────────┬────────┘    └────────┬────────┘    └─────────────────┘        │
│           │                      │                                         │
│           ▼                      ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐          │
│  │              Knowledge State Repository                      │          │
│  │                                                              │          │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │          │
│  │  │  Hot Cache   │  │  Persistent  │  │  Event Log   │       │          │
│  │  │  (Redis)     │  │  (Cassandra) │  │  (Kafka)     │       │          │
│  │  │              │  │              │  │              │       │          │
│  │  │ p_mastery    │  │ BKT params   │  │ interactions │       │          │
│  │  │ last_access  │  │ history      │  │ state_changes│       │          │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │          │
│  └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
           │                                         ▲
           │                                         │
           ▼                                         │
  ┌─────────────────────┐                  ┌───────────────┐
  │  Learning Graph     │                  │  Analytics    │
  │  Service (Neo4j)    │                  │  (Flink)      │
  │                     │                  │               │
  │  /prerequisites/    │                  │  Model perf   │
│  {loId}               │                  │  Efficacy     │
  └─────────────────────┘                  └───────────────┘
```

## 2.2 Module Descriptions

| Module | Responsibility | Interface | Latency Target |
|--------|---------------|-----------|----------------|
| **API Controller** | HTTP/gRPC request handling, auth validation, response formatting | REST: `GET /state`, `POST /update`, `POST /recommend` | <5ms processing |
| **BKT Engine** | Bayesian knowledge tracing inference, mastery probability computation, SM2 scheduling | Internal: `computeMastery()`, `updateParameters()`, `getSpacedInterval()` | <15ms |
| **DKT Client** | Triton inference client for DKT predictions, hidden state management | gRPC: Triton inference API | <15ms (incl. network) |
| **State Repository** | Knowledge state storage/retrieval with tiered caching | Internal: `getState()`, `updateState()`, `appendEvent()` | <5ms read, <10ms write |
| **Event Publisher** | Async event streaming to Kafka for analytics and downstream consumers | Kafka Producer API | Fire-and-forget |

## 2.3 Service Boundaries

**IN SCOPE (AKSRE owns)**:
- Knowledge state storage and retrieval
- BKT parameter management
- Mastery probability computation
- Spaced repetition scheduling (SM2)
- DKT inference client integration
- Learning interaction event processing

**OUT OF SCOPE (other services own)**:
- Content selection and recommendation ranking (Recommendation Service)
- Content delivery and rendering (Delivery Service)
- Prerequisite graph traversal (Learning Graph Service)
- Authentication and authorization (Auth Service)
- IRT diagnostics (Assessment Service)

## Data Flow Architecture

## 3.1 Core Data Flows

### 3.1.1 Knowledge State Update Flow

```
Student submits ──► API Controller ──► Auth Validation
answer                              │
                                    ▼
                              BKT Engine
                              │         │
                              ▼         ▼
                        DKT Client  SM2 Scheduler
                              │         │
                              ▼         ▼
                        Knowledge State Repository
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              Redis (hot)         Cassandra (durable)
                    │                   │
                    └─────────┬─────────┘
                              ▼
                         Event Publisher ──► Kafka ──► Analytics/ML Pipeline
```

**Flow Steps**:
1. Student submits response via `POST /knowledge-state/update`
2. API Controller validates JWT and extracts student_id, lo_id
3. BKT Engine retrieves current parameters from Redis
4. BKT Engine computes P(correct), updates P(L) using Bayes' rule
5. DKT Client sends interaction to Triton for hidden state update (Phase 2)
6. SM2 Scheduler calculates next review interval
7. State Repository writes to Redis (sync) and Cassandra (async via Kafka)
8. Event Publisher emits `KNOWLEDGE_STATE_UPDATED` event
9. Response returned with updated mastery probability and next recommendation time

### 3.1.2 Recommendation Request Flow

```
Request ──► API Controller ──► BKT Engine (P(mastery) lookup)
                                  │
                                  ▼
                            Knowledge State (Redis)
                                  │
                                  ▼
                            DKT Client (predict) ──► Triton
                                  │
                                  ▼
                            Combined Score ──► Response
```

**Flow Steps**:
1. Request via `POST /personalization/recommendations` with target LOs
2. BKT Engine retrieves P(mastery) for each LO from Redis
3. DKT Client requests success probability predictions from Triton (Phase 2)
4. Combined scoring: weighted average (0.4 BKT + 0.6 DKT in Phase 2)
5. Return recommendation payload with predicted_success_probability

## 3.2 Data Store Contracts

| Store | Data | Access Pattern | Consistency | Retention |
|-------|------|----------------|-------------|-----------|
| **Redis** | Hot knowledge states (P(L), last_access, attempt_count) | Read-heavy, <5ms | Eventual | 24h LRU |
| **Cassandra** | Persistent BKT parameters, interaction history | Write-heavy, time-series | Eventual | 7 years |
| **Kafka** | Event log (KNOWLEDGE_STATE_UPDATED, INTERACTION_RECORDED) | Append-only | At-least-once | 30 days |

### 3.2.1 Redis Key Schema
```
ks:{student_id}:{lo_id} → Hash { p_mastery, p_learn, p_guess, p_slip, last_attempt_at, attempt_count }
ks:{student_id}:{lo_id}:sm2 → Hash { interval, repetitions, ef }
```

### 3.2.2 Cassandra Table Schema
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
) WITH CLUSTERING ORDER BY (timestamp DESC);
```

## Interface Specifications

## 4.1 REST API Endpoints

### 4.1.1 Get Knowledge State
```
GET /api/v1/students/{student_id}/knowledge-state?lo_ids={list}

Headers:
  Authorization: Bearer {jwt}
  X-Request-ID: {uuid}

Response 200:
{
  "student_id": "uuid",
  "timestamp": "2026-03-14T12:00:00Z",
  "states": [
    {
      "lo_id": "3.NF.A.1",
      "p_mastery": 0.85,
      "p_learn": 0.20,
      "p_guess": 0.15,
      "p_slip": 0.10,
      "attempt_count": 12,
      "last_attempt_at": "2026-03-14T11:30:00Z",
      "is_mastered": true,
      "next_review_at": "2026-03-16T11:30:00Z"
    }
  ]
}

Response 404: Student not found
Response 403: Insufficient permissions
```

### 4.1.2 Update Knowledge State
```
POST /api/v1/students/{student_id}/knowledge-state/update

Headers:
  Authorization: Bearer {jwt}
  Content-Type: application/json

Request:
{
  "lo_id": "3.NF.A.1",
  "interaction": {
    "content_module_id": "uuid",
    "correctness": 1.0,
    "time_spent_seconds": 45,
    "hints_used": 0,
    "timestamp": "2026-03-14T12:00:00Z"
  },
  "context": {
    "accommodations": ["extended_time"],
    "device_type": "tablet"
  }
}

Response 200:
{
  "student_id": "uuid",
  "lo_id": "3.NF.A.1",
  "previous_p_mastery": 0.75,
  "current_p_mastery": 0.82,
  "is_mastered": true,
  "next_review_at": "2026-03-16T12:00:00Z",
  "processing_time_ms": 23
}

Response 400: Invalid interaction data
Response 422: LO not found
```

### 4.1.3 Get Recommendations
```
POST /api/v1/personalization/recommendations

Headers:
  Authorization: Bearer {jwt}
  Content-Type: application/json

Request:
{
  "student_id": "uuid",
  "target_lo_ids": ["3.NF.A.2", "3.NF.A.3"],
  "limit": 5
}

Response 200:
{
  "student_id": "uuid",
  "recommendations": [
    {
      "lo_id": "3.NF.A.2",
      "predicted_success_probability": 0.78,
      "bkt_p_mastery": 0.65,
      "dkt_prediction": 0.82,
      "difficulty_tier": 3,
      "recommendation_reason": "zpd_optimal"
    }
  ],
  "latency_ms": 45
}
```

## 4.2 Internal Interface Contracts

### 4.2.1 BKT Engine Interface
```python
class BKTEngine:
    def compute_mastery(
        self,
        student_id: UUID,
        lo_id: str,
        current_params: BKTParams
    ) -> MasteryResult:
        """Compute P(mastery) given current BKT parameters."""
        pass

    def update_parameters(
        self,
        current_params: BKTParams,
        interaction: InteractionEvent
    ) -> BKTParams:
        """Update BKT parameters after observed interaction."""
        pass

    def get_spaced_interval(
        self,
        student_id: UUID,
        lo_id: str,
        performance: float
    ) -> SpacedInterval:
        """Calculate next review interval using SM2."""
        pass
```

### 4.2.2 DKT Client Interface
```python
class DKTClient:
    def predict_success_probability(
        self,
        student_id: UUID,
        lo_id: str,
        interaction_history: List[InteractionEvent]
    ) -> DKTPrediction:
        """Request DKT prediction from Triton inference server."""
        pass

    def update_hidden_state(
        self,
        student_id: UUID,
        interaction: InteractionEvent
    ) -> DKTState:
        """Update DKT hidden state with new interaction."""
        pass
```

## 4.3 Event Schema

### 4.3.1 KNOWLEDGE_STATE_UPDATED
```json
{
  "eventType": "KNOWLEDGE_STATE_UPDATED",
  "schemaVersion": "1.0",
  "timestamp": "2026-03-14T12:00:00Z",
  "payload": {
    "student_id": "uuid",
    "lo_id": "3.NF.A.1",
    "previous_p_mastery": 0.75,
    "current_p_mastery": 0.82,
    "p_learn": 0.20,
    "p_guess": 0.15,
    "p_slip": 0.10,
    "interaction": {
      "content_module_id": "uuid",
      "correctness": 1.0,
      "time_spent_seconds": 45
    },
    "mastery_threshold": 0.80,
    "is_mastered": true
  }
}
```

## Error Handling Strategy

## 5.1 Error Categories

| Category | Examples | Handling Strategy |
|----------|----------|-------------------|
| **Validation Errors** | Invalid LO ID, malformed interaction data | 400 Bad Request, detailed error message |
| **Authorization Errors** | Invalid JWT, insufficient scope | 401/403, standard OAuth error format |
| **Not Found** | Student not found, LO not found | 404, optional suggestion |
| **Dependency Failures** | Redis unavailable, Triton timeout | Fallback to degraded mode, 503 if no fallback |
| **Timeout** | Inference >100ms, DB >50ms | Circuit breaker, return last known state |
| **Internal Errors** | Unexpected exceptions | 500, log full stack, increment error counter |

## 5.2 Fallback Chain

```
Primary Path (Hybrid DKT+BKT):
  DKT inference + BKT update → Combined recommendation

Fallback 1 (BKT Only):
  If DKT unavailable → BKT-only prediction
  AUC: 0.75 (acceptable for MVP)

Fallback 2 (Cached State):
  If Redis unavailable → Return last Cassandra snapshot
  Staleness warning in response header: X-State-Stale: true

Fallback 3 (Default Parameters):
  If no state found → Return grade-level defaults
  P(L0)=0.30, P(T)=0.20, P(G)=0.15, P(S)=0.10

Emergency (Static):
  If complete failure → 503 with Retry-After: 5
```

## 5.3 Circuit Breaker Configuration

| Dependency | Failure Threshold | Recovery Timeout | Half-Open Requests |
|------------|-------------------|------------------|-------------------|
| Redis | 5 errors in 60s | 30s | 3 test requests |
| Cassandra | 10 errors in 60s | 60s | 5 test requests |
| Triton (DKT) | 3 errors in 30s | 20s | 2 test requests |
| Kafka | 10 errors in 60s | 30s | Fire-and-forget |

## 5.4 Error Response Format
```json
{
  "error": {
    "code": "DEPENDENCY_UNAVAILABLE",
    "message": "Knowledge state service temporarily unavailable",
    "details": {
      "service": "redis-cluster-1",
      "fallback_applied": "CACHED_STATE",
      "retry_after_seconds": 5
    },
    "request_id": "uuid",
    "timestamp": "2026-03-14T12:00:00Z"
  }
}
```

## Technology Stack Selection

## 6.1 Technology Choices

| Layer | Technology | Justification |
|-------|------------|---------------|
| **Runtime** | Python 3.11 + FastAPI | FastAPI provides async support for I/O-bound operations; Python ecosystem has mature BKT libraries (pyBKT) |
| **API Gateway** | Kong or AWS API Gateway | Rate limiting, auth offloading, request routing |
| **Primary DB (Hot)** | Redis Cluster 7.x | Sub-millisecond reads for real-time knowledge state; native support for hashes, sorted sets |
| **Primary DB (Persistent)** | Cassandra 4.x | Write-optimized for time-series interaction data; linear scalability |
| **Event Streaming** | Apache Kafka | At-least-once delivery guarantee; decouples AKSRE from analytics |
| **ML Inference** | NVIDIA Triton 2.x | GPU-accelerated DKT inference; <10ms latency target |
| **External Graph** | Neo4j 5.x (via Learning Graph Service) | Prerequisite graph traversal; accessed via API not direct |
| **Observability** | Prometheus + Grafana + Jaeger | Metrics, dashboards, distributed tracing |
| **Deployment** | Kubernetes + Helm | Container orchestration; autoscaling HPA/VPA |

## 6.2 Trade-off Analysis

### 6.2.1 Python vs. Go for API Layer

| Factor | Python (FastAPI) | Go |
|--------|------------------|-----|
| BKT Library Maturity | ✅ pyBKT available | ❌ Would require porting |
| Performance | ⚠️ Adequate with async | ✅ Higher throughput |
| Developer Velocity | ✅ Faster iteration | ⚠️ Slower for ML ops |
| **Decision** | ✅ **Python** - BKT library availability outweighs performance gains |

### 6.2.2 Redis + Cassandra vs. PostgreSQL

| Factor | Redis + Cassandra | PostgreSQL |
|--------|-------------------|------------|
| Read Latency | ✅ <5ms | ⚠️ ~20ms |
| Write Throughput | ✅ 10K+ writes/s | ⚠️ 2K writes/s |
| Query Flexibility | ⚠️ Limited | ✅ Full SQL |
| Operational Complexity | ⚠️ Two systems | ✅ Single system |
| **Decision** | ✅ **Redis + Cassandra** - Meets latency/throughput requirements |

### 6.2.3 Triton vs. Custom DKT Server

| Factor | NVIDIA Triton | Custom |
|--------|---------------|--------|
| GPU Optimization | ✅ Built-in TensorRT | ❌ Manual implementation |
| Model Versioning | ✅ Built-in | ❌ Custom code |
| Batch Inference | ✅ Dynamic batching | ❌ Manual implementation |
| **Decision** | ✅ **Triton** - Industry standard for GPU inference |

## 6.3 Resource Requirements

| Component | CPU | Memory | Storage | Instances |
|-----------|-----|--------|---------|-----------|
| AKSRE API | 2 cores | 4GB | - | 3 (HA) |
| Redis Cluster | 2 cores | 16GB | 100GB SSD | 3 masters + 3 replicas |
| Cassandra | 4 cores | 8GB | 500GB SSD | 3 nodes |
| Kafka | 2 cores | 4GB | 1TB HDD | 3 brokers |
| Triton (GPU) | 8 cores | 32GB | 50GB SSD | 2 (HA) |

## Deployment Architecture

## 7.1 Kubernetes Deployment

```yaml
# aksre-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aksre-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aksre-api
  template:
    spec:
      containers:
      - name: aksre
        image: aksre:v1.0.0
        resources:
          requests:
            memory: "4Gi"
            cpu: "2000m"
        env:
        - name: REDIS_CLUSTER
          value: "redis-cluster:6379"
        - name: CASSANDRA_HOSTS
          value: "cassandra-0,cassandra-1,cassandra-2"
        - name: TRITON_HOST
          value: "triton-inference:8001"
        - name: KAFKA_BOOTSTRAP
          value: "kafka:9092"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
```

## 7.2 Scaling Policies

| Metric | Threshold | Action | Cooldown |
|--------|-----------|--------|----------|
| CPU > 70% | 2 min | Scale up +1 | 60s |
| CPU < 30% | 10 min | Scale down -1 | 300s |
| Request latency p95 > 80ms | 1 min | Scale up +2 | 60s |
| Redis memory > 80% | 1 min | Alert + shard | - |

## 7.3 Health Check Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /health/live` | Liveness | 200 OK (always) |
| `GET /health/ready` | Readiness | 200 if deps healthy, 503 otherwise |
| `GET /health/dependencies` | Deep check | Status of Redis, Cassandra, Triton |

```json
{
  "status": "healthy",
  "checks": {
    "redis": {"status": "up", "latency_ms": 2},
    "cassandra": {"status": "up", "latency_ms": 15},
    "triton": {"status": "up", "latency_ms": 8}
  }
}
```

## Security Architecture

## 8.1 Data Protection

| Layer | Mechanism | Implementation |
|-------|-----------|----------------|
| **In Transit** | TLS 1.3 | All service-to-service communication |
| **At Rest** | AES-256 | Cassandra encryption, Redis AUTH |
| **PII Handling** | Tokenization | student_id is UUID, no PII in AKSRE |
| **Audit Logging** | Immutable logs | All state changes to append-only log |

## 8.2 Authentication & Authorization

- **Inbound**: JWT validation via API Gateway
- **Scopes Required**: `student:read`, `student:write`
- **Outbound to Triton**: mTLS with client certificates
- **Outbound to Learning Graph**: OAuth 2.0 client credentials

## 8.3 Privacy Compliance

| Requirement | Implementation |
|-------------|----------------|
| **COPPA** | No PII stored in AKSRE; only anonymous student_id |
| **FERPA** | Audit log of all knowledge state access; 7-year retention |
| **Data Deletion** | `/admin/purge/{student_id}` endpoint for GDPR/CCPA compliance |
| **Differential Privacy** | Noise injection on exported aggregates (handled by Analytics Service) |

## Implementation Phases

## 9.1 Phase 1: BKT-Only MVP (Months 1-3)

**Scope**:
- BKT Engine with default parameters
- Redis + Cassandra storage
- REST API: `/state`, `/update`
- SM2 spaced repetition
- No DKT integration (Triton not required)

**Success Criteria**:
- AUC ≥ 0.75 on held-out test data
- p95 latency < 50ms for updates
- 1K updates/second sustained throughput

## 9.2 Phase 2: Hybrid Integration (Months 4-6)

**Additions**:
- DKT Client integration with Triton
- Combined BKT+DKT scoring
- `/recommendations` endpoint
- Cold-start handling with IRT bridge

**Success Criteria**:
- AUC ≥ 0.85
- p95 latency < 100ms for predictions
- Graceful fallback when DKT unavailable

## 9.3 Phase 3: Production Hardening (Months 7-9)

**Additions**:
- Multi-region deployment
- Advanced monitoring and alerting
- BKT parameter online learning
- Chaos engineering tests

**Success Criteria**:
- 99.9% availability
- 10K+ updates/second
- Zero data loss on failover

## Appendix: Decision Log

| Date | Decision | Rationale | Alternatives Considered |
|------|----------|-----------|------------------------|
| 2026-03-14 | Python + FastAPI runtime | pyBKT library availability | Go (rejected due to library gap) |
| 2026-03-14 | Redis + Cassandra storage | Latency/throughput requirements | PostgreSQL (rejected due to performance) |
| 2026-03-14 | Triton for DKT inference | GPU optimization, standard tooling | Custom Flask server (rejected) |
| 2026-03-14 | BKT-only MVP first | Risk mitigation, proven foundation | Hybrid from day 1 (rejected as risky) |
| 2026-03-14 | SM2 for spaced repetition | Proven algorithm, no training data needed | LSTM-based (deferred to Phase 2) |
| 2026-03-14 | Learning Graph Service API | Service boundary preservation | Direct Neo4j access (rejected) |
