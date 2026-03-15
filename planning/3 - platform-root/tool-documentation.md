---
date: '2026-03-14'
tool: AKSRE - Adaptive Knowledge State & Recommendation Engine
version: 1.0.0
---

# AKSRE Documentation

## Overview

AKSRE (Adaptive Knowledge State & Recommendation Engine) is a FastAPI-based microservice that implements Bayesian Knowledge Tracing (BKT) with SM2 spaced repetition scheduling for adaptive K-12 learning platforms.

**Key Features:**
- Real-time Bayesian Knowledge Tracing for mastery prediction
- SM-2 spaced repetition algorithm for optimal review scheduling
- Hybrid storage architecture (Redis hot cache + Cassandra persistent store)
- Event streaming to Kafka for analytics integration
- Circuit breaker pattern for fault tolerance
- RESTful API for knowledge state management and recommendations

## Quick Start

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (for local development)
- Redis 7.x, Cassandra 4.x, Kafka (via Docker Compose)

## Installation

### 1. Clone and Setup

```bash
cd /Users/sfw/Development/EducationalPlatform/platform-root
pip install -e ".[dev]"
```

### 2. Start Dependencies

```bash
docker-compose up -d redis cassandra kafka
```

Wait for services to be healthy (30-60 seconds for Cassandra):

```bash
docker-compose ps
```

### 3. Run the Application

```bash
python -m src.main
```

The API will be available at `http://localhost:8080`.

### 4. Verify Installation

```bash
curl http://localhost:8080/api/v1/students/health/live
```

Expected response: `{"status": "alive"}`

## Configuration

## Configuration Sources

Configuration is loaded in priority order (highest first):
1. Environment variables
2. `config.yaml` file
3. Default values

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AKSRE_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `AKSRE_ENVIRONMENT` | Environment name | development |
| `REDIS_HOST` | Redis server hostname | localhost |
| `REDIS_PORT` | Redis server port | 6379 |
| `CASSANDRA_HOSTS` | Comma-separated Cassandra hosts | localhost |
| `CASSANDRA_KEYSPACE` | Cassandra keyspace name | aksre |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka bootstrap servers | localhost:9092 |
| `DKT_ENABLED` | Enable DKT integration (Phase 2) | false |

## config.yaml

```yaml
app:
  name: "aksre"
  version: "1.0.0"
  environment: "development"
  log_level: "INFO"

bkt:
  default_params:
    p_l0: 0.30    # Initial probability of mastery
    p_t: 0.20     # Probability of learning
    p_g: 0.15     # Probability of guessing
    p_s: 0.10     # Probability of slipping
  mastery_threshold: 0.80
  min_attempts_for_mastery: 3

sm2:
  initial_interval: 1
  initial_easiness: 2.5
  min_easiness: 1.3
  max_interval: 365

redis:
  host: "localhost"
  port: 6379
  ttl_seconds: 86400

cassandra:
  hosts:
    - "localhost"
  port: 9042
  keyspace: "aksre"
```

## API Reference

## Base URL

```
http://localhost:8080/api/v1
```

## Authentication

All endpoints require a Bearer token (JWT) in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

## Endpoints

### Get Knowledge State

Retrieve current knowledge state for a student across multiple learning objectives.

```http
GET /students/{student_id}/knowledge-state?lo_ids=3.NF.A.1,3.NF.A.2
```

**Parameters:**
- `student_id` (path): UUID of the student
- `lo_ids` (query): Comma-separated list of learning objective IDs

**Response (200 OK):**
```json
{
  "student_id": "550e8400-e29b-41d4-a716-446655440000",
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
```

### Update Knowledge State

Process a learning interaction and update the student's knowledge state.

```http
POST /students/{student_id}/knowledge-state/update
```

**Request Body:**
```json
{
  "lo_id": "3.NF.A.1",
  "interaction": {
    "content_module_id": "550e8400-e29b-41d4-a716-446655440001",
    "correctness": 1.0,
    "time_spent_seconds": 45,
    "hints_used": 0,
    "timestamp": "2026-03-14T12:00:00Z"
  }
}
```

**Response (200 OK):**
```json
{
  "student_id": "550e8400-e29b-41d4-a716-446655440000",
  "lo_id": "3.NF.A.1",
  "previous_p_mastery": 0.75,
  "current_p_mastery": 0.82,
  "is_mastered": true,
  "next_review_at": "2026-03-16T12:00:00Z",
  "processing_time_ms": 23
}
```

### Get Recommendations

Get personalized content recommendations based on current knowledge states.

```http
POST /personalization/recommendations
```

**Request Body:**
```json
{
  "student_id": "550e8400-e29b-41d4-a716-446655440000",
  "target_lo_ids": ["3.NF.A.1", "3.NF.A.2", "3.NF.A.3"],
  "limit": 5
}
```

**Response (200 OK):**
```json
{
  "student_id": "550e8400-e29b-41d4-a716-446655440000",
  "recommendations": [
    {
      "lo_id": "3.NF.A.2",
      "predicted_success_probability": 0.78,
      "bkt_p_mastery": 0.65,
      "dkt_prediction": null,
      "difficulty_tier": 3,
      "recommendation_reason": "zpd_optimal"
    }
  ],
  "latency_ms": 45
}
```

### Health Checks

#### Liveness Probe
```http
GET /students/health/live
```
Returns `{"status": "alive"}` if the service is running.

#### Readiness Probe
```http
GET /students/health/ready
```
Returns 200 if all dependencies (Redis, Cassandra) are healthy, 503 otherwise.

## Usage Examples

## Example 1: Track Student Progress

```python
import requests
import uuid

BASE_URL = "http://localhost:8080/api/v1"
HEADERS = {"Authorization": "Bearer test-token"}

# Create a student session
student_id = str(uuid.uuid4())
lo_id = "3.NF.A.1"  # Grade 3 Numbers & Fractions

# Record a correct answer
response = requests.post(
    f"{BASE_URL}/students/{student_id}/knowledge-state/update",
    headers=HEADERS,
    json={
        "lo_id": lo_id,
        "interaction": {
            "content_module_id": str(uuid.uuid4()),
            "correctness": 1.0,
            "time_spent_seconds": 60,
            "hints_used": 0
        }
    }
)
print(f"First attempt: P(mastery) = {response.json()['current_p_mastery']}")

# Record several more interactions
for _ in range(4):
    requests.post(
        f"{BASE_URL}/students/{student_id}/knowledge-state/update",
        headers=HEADERS,
        json={
            "lo_id": lo_id,
            "interaction": {
                "content_module_id": str(uuid.uuid4()),
                "correctness": 1.0,
                "time_spent_seconds": 45,
                "hints_used": 0
            }
        }
    )

# Check if mastered
state = requests.get(
    f"{BASE_URL}/students/{student_id}/knowledge-state",
    headers=HEADERS,
    params={"lo_ids": [lo_id]}
).json()

print(f"After 5 correct answers: mastered = {state['states'][0]['is_mastered']}")
```

## Example 2: Get Personalized Recommendations

```python
# Get recommendations for a student across multiple objectives
target_los = ["3.NF.A.1", "3.NF.A.2", "3.NF.A.3", "3.NF.B.1", "3.NF.B.2"]

response = requests.post(
    f"{BASE_URL}/personalization/recommendations",
    headers=HEADERS,
    json={
        "student_id": student_id,
        "target_lo_ids": target_los,
        "limit": 3
    }
)

recommendations = response.json()["recommendations"]
for rec in recommendations:
    print(f"{rec['lo_id']}: {rec['recommendation_reason']} "
          f"(success probability: {rec['predicted_success_probability']:.2f})")
```

## Example 3: Handle Incorrect Responses

```python
# Student answers incorrectly
response = requests.post(
    f"{BASE_URL}/students/{student_id}/knowledge-state/update",
    headers=HEADERS,
    json={
        "lo_id": lo_id,
        "interaction": {
            "content_module_id": str(uuid.uuid4()),
            "correctness": 0.0,  # Incorrect
            "time_spent_seconds": 30,
            "hints_used": 2
        }
    }
)

result = response.json()
print(f"After incorrect answer: P(mastery) dropped from "
      f"{result['previous_p_mastery']:.2f} to {result['current_p_mastery']:.2f}")
```

## Architecture Overview

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        AKSRE SERVICE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐ │
│  │  API Controller│    │  BKT Engine    │    │  DKT Client    │ │
│  │  (FastAPI)     │◄──►│  (Inference)   │◄──►│  (Triton)      │ │
│  │                │    │                │    │                │ │
│  │ - /state       │    │ - P(L) compute │    │ - Hidden state │ │
│  │ - /update      │    │ - Mastery gate │    │ - Prediction   │ │
│  │ - /recommend   │    │ - SM2 schedule │    │                │ │
│  └───────┬────────┘    └───────┬────────┘    └────────────────┘ │
│          │                     │                                 │
│          ▼                     ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Knowledge State Repository                 │    │
│  │                                                         │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │    │
│  │  │  Hot Cache   │  │  Persistent  │  │  Event Log   │  │    │
│  │  │  (Redis)     │  │  (Cassandra) │  │  (Kafka)     │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow: Knowledge State Update

1. Student submits answer → API Controller validates request
2. BKT Engine retrieves current parameters from Redis
3. BKT Engine computes P(correct), updates P(L) using Bayes' rule
4. SM2 Scheduler calculates next review interval
5. State Repository writes to Redis (sync) and Cassandra (async)
6. Event Publisher emits `KNOWLEDGE_STATE_UPDATED` to Kafka
7. Response returned with updated mastery probability

## Fallback Chain

When dependencies fail, AKSRE uses a 4-level fallback:

1. **Hybrid (DKT + BKT)** - Full prediction with deep learning
2. **BKT-only** - Bayesian prediction without DKT
3. **Cached State** - Last known state from Redis
4. **Default Parameters** - Grade-level defaults (P(L0)=0.30)

## BKT Algorithm

## Bayesian Knowledge Tracing

AKSRE implements the standard BKT algorithm with the following parameters:

| Parameter | Symbol | Default | Description |
|-----------|--------|---------|-------------|
| Initial mastery | P(L₀) | 0.30 | Probability student has already mastered the skill |
| Learning | P(T) | 0.20 | Probability of transitioning to mastered state |
| Guess | P(G) | 0.15 | Probability of correct answer without mastery |
| Slip | P(S) | 0.10 | Probability of incorrect answer despite mastery |

## Update Formula

When a student answers a question:

```
If correct:
  P(L|correct) = P(correct|L) * P(L) / P(correct)
               = (1 - P(S)) * P(L) / P(correct)

If incorrect:
  P(L|incorrect) = P(incorrect|L) * P(L) / P(incorrect)
                 = P(S) * P(L) / P(incorrect)

Where:
  P(correct) = P(L)*(1-P(S)) + (1-P(L))*P(G)

After observing, apply learning:
  P(L)new = P(L|observation) + (1 - P(L|observation)) * P(T)
```

## Mastery Detection

A student is considered to have **mastered** a learning objective when:
- P(mastery) ≥ 0.80 (configurable)
- AND attempt_count ≥ 3 (configurable)

## SM-2 Spaced Repetition

## Algorithm Overview

AKSRE uses the SuperMemo-2 (SM2) algorithm to calculate optimal review intervals based on performance.

## Quality Calculation

Performance (0.0-1.0) is converted to SM2 quality rating (0-5):

| Performance | Quality | Meaning |
|-------------|---------|---------|
| 0.0 - 0.2 | 0 | Complete blackout |
| 0.2 - 0.4 | 1 | Incorrect response |
| 0.4 - 0.6 | 2 | Correct with difficulty |
| 0.6 - 0.8 | 3 | Correct with hesitation |
| 0.8 - 1.0 | 4-5 | Correct with ease |

## Interval Calculation

```
if quality < 3:
    interval = 1  # Reset on failure
    repetitions = 0
else:
    if repetitions == 0:
        interval = 1
    elif repetitions == 1:
        interval = 6
    else:
        interval = round(previous_interval * easiness_factor)

# Update easiness factor
delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
new_easiness = max(1.3, easiness_factor + delta)
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| Initial interval | 1 day | First review after initial learning |
| Initial easiness | 2.5 | Starting easiness factor |
| Minimum easiness | 1.3 | Floor for easiness factor |
| Maximum interval | 365 days | Cap for review intervals |

## Running Tests

## Unit Tests

Run the test suite with pytest:

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

## Test Structure

```
tests/
├── test_bkt_engine.py    # BKT algorithm tests
├── test_api.py           # API endpoint tests
└── test_integration.py   # Integration tests
```

## Example Test Output

```
tests/test_bkt_engine.py::TestBKTEngine::test_create_initial_state PASSED
tests/test_bkt_engine.py::TestBKTEngine::test_update_parameters_correct_response PASSED
tests/test_bkt_engine.py::TestBKTEngine::test_mastery_threshold PASSED
tests/test_api.py::TestHealthEndpoints::test_liveness PASSED
tests/test_api.py::TestKnowledgeStateEndpoints::test_update_knowledge_state PASSED
```

## Deployment

## Docker Compose (Local Development)

Start all services:

```bash
docker-compose up --build
```

Services:
- AKSRE API: http://localhost:8080
- Redis: localhost:6379
- Cassandra: localhost:9042
- Kafka: localhost:9092
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

## Kubernetes

Deploy to Kubernetes:

```bash
kubectl apply -f k8s/
```

## Health Checks

- **Liveness**: `GET /api/v1/students/health/live` - Always returns 200
- **Readiness**: `GET /api/v1/students/health/ready` - Returns 200 when dependencies are healthy

## Monitoring and Logging

## Structured Logging

AKSRE uses structured JSON logging via `structlog`. Example log entry:

```json
{
  "timestamp": "2026-03-14T12:00:00.123Z",
  "level": "info",
  "logger": "aksre.api.state",
  "event": "Knowledge state updated",
  "student_id": "550e8400-e29b-41d4-a716-446655440000",
  "lo_id": "3.NF.A.1",
  "previous_p_mastery": 0.75,
  "current_p_mastery": 0.82,
  "processing_time_ms": 23
}
```

## Metrics

Prometheus metrics are exposed at `/metrics`:

- `aksre_requests_total` - Total HTTP requests
- `aksre_request_duration_seconds` - Request latency histogram
- `aksre_bkt_updates_total` - BKT update operations
- `aksre_circuit_breaker_state` - Circuit breaker state (0=closed, 1=open)

## Circuit Breaker Monitoring

Circuit breaker states are logged and metrics are exposed:

| Dependency | Failure Threshold | Recovery Timeout |
|------------|-------------------|------------------|
| Redis | 5 errors in 60s | 30 seconds |
| Cassandra | 10 errors in 60s | 60 seconds |
| DKT | 3 errors in 30s | 20 seconds |

## Troubleshooting

## Common Issues

### Redis Connection Failed

**Symptom**: `Redis connection failed` error

**Solution**:
```bash
# Check if Redis is running
docker-compose ps redis

# Restart Redis
docker-compose restart redis
```

### Cassandra Not Ready

**Symptom**: `Cassandra connection failed` or timeout

**Solution**:
```bash
# Wait for Cassandra to fully start (can take 60+ seconds)
docker-compose logs -f cassandra

# Check nodetool status
docker-compose exec cassandra nodetool status
```

### API Returns 503 Service Unavailable

**Symptom**: All requests return 503

**Cause**: Circuit breakers are open due to dependency failures

**Solution**:
1. Check dependency health: `curl /api/v1/students/health/ready`
2. Restart failing services
3. Circuit breakers will auto-recover when dependencies are healthy

### High Latency

**Symptom**: `processing_time_ms` > 100ms

**Possible causes**:
- Redis cache misses (check cache hit rate)
- Cassandra slow queries
- Insufficient connection pooling

**Solution**:
- Scale Redis cluster
- Tune Cassandra consistency level
- Increase connection pool sizes in config

## Development Guide

## Project Structure

```
aksre/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Configuration management
│   ├── models/
│   │   ├── bkt.py             # BKT data models
│   │   ├── requests.py        # API request schemas
│   │   └── responses.py       # API response schemas
│   ├── engines/
│   │   ├── bkt_engine.py      # BKT inference engine
│   │   └── sm2_scheduler.py   # SM2 spaced repetition
│   ├── repositories/
│   │   ├── knowledge_state.py # Repository interface
│   │   ├── redis_store.py     # Redis implementation
│   │   └── cassandra_store.py # Cassandra implementation
│   ├── api/
│   │   ├── state.py           # State endpoints
│   │   └── recommendations.py # Recommendation endpoints
│   ├── services/
│   │   ├── circuit_breaker.py # Fault tolerance
│   │   └── event_publisher.py # Kafka integration
│   └── utils/
│       ├── logging.py         # Structured logging
│       └── errors.py          # Error definitions
├── tests/
├── pyproject.toml
├── config.yaml
├── Dockerfile
└── docker-compose.yml
```

## Adding a New Endpoint

1. Define request/response models in `src/models/`
2. Implement endpoint in `src/api/`
3. Add tests in `tests/`
4. Update this documentation

## Code Style

Format code with Black:

```bash
black src/ tests/
```

Lint with Ruff:

```bash
ruff check src/ tests/
```

Type checking with mypy:

```bash
mypy src/
```

## Maintenance

## Regular Maintenance Tasks

### Daily
- Monitor error rates and latency
- Check circuit breaker states
- Review Kafka consumer lag

### Weekly
- Review BKT parameter distributions
- Check Redis memory usage
- Verify Cassandra compaction

### Monthly
- Review and tune BKT default parameters
- Analyze recommendation quality metrics
- Capacity planning review

## Backup and Recovery

### Redis
Redis data is ephemeral (cache). No backup required - data is reconstructed from Cassandra on cache miss.

### Cassandra
Use standard Cassandra backup procedures:

```bash
# Snapshot backup
nodetool snapshot aksre

# Restore from snapshot
nodetool refresh aksre student_knowledge_state
```

### Kafka
Configure Kafka retention policies for event replay if needed:

```properties
retention.ms=2592000000  # 30 days
```

## Upgrading

### Database Migrations

Cassandra schema is auto-created on startup. For migrations:

1. Update schema in `src/repositories/cassandra_store.py`
2. Run migration script
3. Verify with health checks

### Configuration Changes

Configuration changes take effect on restart. For zero-downtime updates:

1. Update configmap/environment variables
2. Rolling restart deployment
3. Verify new pods are healthy before terminating old pods

## API Version History

## v1.0.0 (Current)

- Initial release with BKT-only knowledge tracing
- SM2 spaced repetition scheduling
- REST API for state management and recommendations
- Redis + Cassandra hybrid storage
- Kafka event streaming
- Circuit breaker fault tolerance

## Planned for v1.1.0 (Phase 2)

- DKT integration with Triton inference
- Hybrid BKT+DKT predictions
- Cold-start handling improvements
- Enhanced recommendation ranking

## Planned for v1.2.0 (Phase 3)

- gRPC API support
- BKT parameter online learning
- Multi-region deployment support
- Advanced analytics endpoints
