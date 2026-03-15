# Requirements Specification: Adaptive K-12 Learning Platform

**Version:** 1.0  
**Date:** 2026-03-13  
**Source:** Development Handoff Package - Executive Summary Review

---

## 1. Project Overview

### 1.1 Project Name
**Adaptive K-12 Learning Platform**

### 1.2 High-Level Description
An intelligent educational platform that delivers personalized learning experiences to K-12 students through adaptive content recommendation and real-time knowledge state tracking. The platform uses a hybrid Deep Knowledge Tracing (DKT) + Bayesian Knowledge Tracing (BKT) machine learning model to predict student mastery and recommend optimal learning paths while maintaining pedagogical interpretability for teachers.

### 1.3 Core Value Proposition
- **Personalization**: Tailors content difficulty and sequence to individual student knowledge states
- **Pedagogical Transparency**: Provides interpretable recommendations that teachers can understand and override
- **Scale**: Supports 1M+ concurrent students with sub-200ms response times
- **Efficacy**: Targeting 1.5x learning velocity compared to control groups

---

## 2. Target Users

### 2.1 Primary Users

| User Type | Description | Key Needs |
|-----------|-------------|-----------|
| **K-12 Students** | Learners aged 5-18 using the platform for educational content | Engaging content, appropriate difficulty, clear progress tracking |
| **Teachers** | Educators monitoring student progress and assigning content | Dashboard visibility, interpretable recommendations, override capabilities |
| **Administrators** | School/district staff managing the platform | User management, analytics, compliance reporting |

### 2.2 Secondary Users
- **Parents/Guardians**: Viewing student progress reports
- **Content Creators**: Uploading and structuring educational materials
- **Data Scientists**: Monitoring model performance and retraining

---

## 3. Project Goals

### 3.1 Technical Goals

| Goal | Target | Measurement |
|------|--------|-------------|
| Scale | Support 1M+ concurrent students | Load testing |
| Latency | <200ms end-to-end (p95), <100ms for recommendations | Performance monitoring |
| Throughput | 10K+ recommendations/second | Benchmark testing |
| ML Accuracy | AUC ≥ 0.85 for knowledge tracing predictions | Model evaluation |
| Storage | Handle 50TB+ learning interaction data | Capacity planning |

### 3.2 Educational Goals

| Goal | Target | Measurement |
|------|--------|-------------|
| Learning Efficacy | 1.5x learning velocity vs control | Standardized assessments |
| Engagement | 70% daily active users of enrolled | Analytics tracking |
| Knowledge Retention | Measurable gain score ≥ 0.4 (medium effect) | Pre/post testing |

### 3.3 Business Goals
- **Compliance**: Meet COPPA and FERPA requirements for student data privacy
- **Accessibility**: Pass WCAG 2.1 AA audit
- **Security**: Achieve OWASP ASVS Level 3 compliance

---

## 4. Key Success Metrics

### 4.1 Performance Metrics
- **API Response Time**: p95 < 200ms, p99 < 500ms
- **Recommendation Latency**: p95 < 100ms (GPU inference)
- **System Availability**: 99.9% uptime
- **Concurrent User Capacity**: 1M+ simultaneous sessions

### 4.2 Learning Metrics
- **Knowledge Tracing AUC**: ≥ 0.85 (target 0.85-0.90)
- **Learning Velocity**: 1.5x improvement over non-adaptive control
- **Engagement Rate**: 70% daily active users
- **Standardized Gain Score**: ≥ 0.4 (medium effect size)

### 4.3 Quality Metrics
- **Accessibility**: WCAG 2.1 AA compliance
- **Security**: Zero critical vulnerabilities (penetration testing)
- **Test Coverage**: >80% unit test coverage

---

## 5. Constraints and Requirements

### 5.1 Technical Constraints

| Constraint | Requirement |
|------------|-------------|
| **ML Model** | Hybrid DKT+BKT architecture for accuracy + explainability |
| **Database Architecture** | Polyglot: Neo4j (learning topology), PostgreSQL (relational), Redis (caching), Cassandra (time-series) |
| **API Design** | Hybrid REST/GraphQL: REST for CRUD, GraphQL for complex queries |
| **Container Orchestration** | Kubernetes with NVIDIA Triton for GPU-accelerated inference |
| **Privacy** | Differential privacy + federated learning for model training |

### 5.2 Compliance Constraints
- **COPPA**: Children's Online Privacy Protection Act compliance for users under 13
- **FERPA**: Family Educational Rights and Privacy Act compliance for student records
- **Data Residency**: Support for regional data storage requirements
- **Encryption**: End-to-end encryption for all PII

### 5.3 Technology Stack (Specified)

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Next.js 14, TypeScript |
| API Gateway | Node.js, Express, GraphQL |
| ML Inference | NVIDIA Triton, PyTorch |
| Databases | PostgreSQL 14, Neo4j 5.x, Redis 7, Cassandra |
| Data Streaming | Apache Kafka |
| Containers | Docker, Kubernetes |
| Monitoring | Prometheus, Grafana, Jaeger |

---

## 6. Core Components to Build

### 6.1 Component Inventory

| Component | Priority | Description |
|-----------|----------|-------------|
| **User Authentication & Authorization** | P0 | Secure login, role-based access, session management |
| **Content Delivery System** | P0 | Serve educational content with adaptive sequencing |
| **Knowledge State Tracking** | P0 | Real-time student proficiency monitoring |
| **Personalization Engine (DKT+BKT)** | P0 | ML-powered content recommendation |
| **Teacher Dashboard** | P1 | Progress visualization, recommendation overrides |
| **Assessment Engine** | P1 | Quiz delivery, auto-grading, difficulty calibration |
| **Analytics Platform** | P2 | Learning analytics, reporting, A/B testing |

### 6.2 Implementation Phases

**Phase 1: MVP (Months 1-3)**
- User authentication & authorization
- Basic content delivery
- Knowledge state tracking
- Simple recommendation engine

**Phase 2: Adaptive Features (Months 4-6)**
- DKT model integration
- Real-time personalization
- Teacher dashboards
- Assessment engine

**Phase 3: Scale & Intelligence (Months 7-9)**
- Hybrid DKT+BKT model
- Advanced analytics
- A/B testing framework
- Production hardening

---

## 7. Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ML Model Architecture | Hybrid DKT+BKT | Balances accuracy (DKT) with explainability (BKT) for teachers |
| Database Strategy | Polyglot persistence | Optimizes for different data patterns (graph, relational, key-value, time-series) |
| API Paradigm | Hybrid REST/GraphQL | REST for simple CRUD, GraphQL for complex aggregated queries |
| ML Deployment | NVIDIA Triton on Kubernetes | GPU-accelerated real-time inference with container orchestration |
| Privacy Approach | Differential privacy + federated learning | Enables ML model improvement without centralizing sensitive student data |

---

## 8. Entry Points for Development

### 8.1 Critical Specification Files
- **API Contract**: `03-platform-specs/api-contract/openapi.yaml`
- **Database Schema**: `03-platform-specs/database-schema.sql`
- **ML Configuration**: `03-platform-specs/ml-model-configs/model-specification.yaml`
- **Architecture**: `02-architecture-overview/conceptual-architecture.md`
- **Roadmap**: `06-implementation/roadmap.md`

### 8.2 Local Development Setup
```bash
cd 07-devops/
docker-compose up -d
psql -h localhost -U postgres -f ../03-platform-specs/database-schema.sql
```

---

## 9. Success Criteria Checklist

Before production deployment, the following must be verified:

- [ ] All API endpoints respond <200ms (p95)
- [ ] Knowledge tracing accuracy AUC ≥ 0.85
- [ ] Accessibility audit passes WCAG 2.1 AA
- [ ] Security penetration test complete with zero critical findings
- [ ] Load test validates 1M concurrent users
- [ ] COPPA/FERPA compliance verified by legal
- [ ] Teacher acceptance testing passed

---

## 10. Summary

The Adaptive K-12 Learning Platform is a high-scale educational technology system requiring:

1. **Real-time ML inference** using a hybrid DKT+BKT model for personalized recommendations
2. **Polyglot data architecture** supporting graph, relational, and time-series data patterns
3. **Strict compliance** with COPPA and FERPA privacy regulations
4. **Sub-200ms latency** at 1M+ concurrent user scale
5. **Pedagogical interpretability** enabling teachers to understand and override AI recommendations

This specification serves as the foundation for architecture design and implementation planning.

---

## Appendix A: Architecture Specifications (Extracted)

### A.1 Domain Models

| Model | Description | Key Attributes |
|-------|-------------|----------------|
| **Student** | Human learner identity | `student_id`, `grade_level`, `iep_504_flags`, `language_preference` |
| **KnowledgeState** | Evolving understanding of what student knows | `dkt_hidden_state` (128-dim), `bkt_params`, `mastery_map`, `response_history` |
| **LearningObjective** | Discrete, assessable unit of knowledge (Learning Graph node) | `lo_id`, `standard_code`, `difficulty_index`, `prerequisite_ids` |
| **ContentModule** | Atomic learning content unit | `module_id`, `lo_id`, `module_type`, `difficulty_tier`, `accessibility_features` |
| **Interaction** | Immutable record of student-system touchpoint | `interaction_id`, `timestamp`, `correctness`, `time_spent_seconds` |

### A.2 The 5-Phase Adaptive Feedback Loop

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ADAPTIVE FEEDBACK LOOP                               │
│                    (Target: <200ms end-to-end)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐       │
│   │  ASSESS  │──▶│ DIAGNOSE │──▶│ PRESCRIBE│──▶│  DELIVER │──┐    │
│   │  <10ms   │   │  <50ms   │   │ <100ms   │   │ <200ms   │  │    │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │    │
│        ↑                                                    │    │
│        └────────────────────────────────────────────────────┘    │
│                              VERIFY                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Phase Details:**
- **ASSESS**: Capture interaction, validate response, extract cognitive load signals
- **DIAGNOSE**: Update DKT hidden state, BKT parameters, compute mastery probabilities
- **PRESCRIBE**: Select optimal content based on ZPD (50-85% success prob), spaced repetition
- **DELIVER**: Render content with accommodations, CLT optimization, accessibility features
- **VERIFY**: Validate outcomes, feed data back for model improvement

### A.3 Service Boundaries

| Service | Responsibility | Technology Stack |
|---------|---------------|------------------|
| **Student Model Service** | KnowledgeState management, DKT/BKT inference | Redis/Cassandra + NVIDIA Triton |
| **Learning Graph Service** | Topology operations, prerequisite analysis | Neo4j Enterprise |
| **Content Service** | ContentModule storage, versioning | MongoDB Atlas + CDN |
| **Recommendation Service** | PRESCRIBE algorithm, content selection | Python/Go + Feature Store (Feast) |
| **Delivery Service** | Content rendering, accommodation application | Node.js/Python |
| **Analytics Service** | Event processing, reporting | Apache Flink + ClickHouse |

### A.4 Data Storage Strategy (Polyglot Persistence)

| Data Type | Primary Store | Secondary Store | Purpose |
|-----------|--------------|-----------------|---------|
| Learning Graph | Neo4j | PostgreSQL (backup) | Prerequisite traversal queries |
| KnowledgeState | Redis Cluster (hot) | Cassandra (persistent) | Sub-ms reads, high write throughput |
| Interaction Events | Apache Kafka | S3 (Parquet) | Event sourcing, replay capability |
| Content Modules | MongoDB | CDN (CloudFront) | Flexible schema, edge delivery |
| Student PII | PostgreSQL (encrypted) | - | ACID compliance, audit logging |
| Analytics | ClickHouse | S3 (cold) | Columnar aggregation, cost-effective |

### A.5 ML Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Model Training | Kubeflow Pipelines | Reproducible workflows |
| Feature Store | Feast | Feature consistency (train/serve) |
| Model Registry | MLflow | Versioning, A/B testing |
| Inference Server | NVIDIA Triton | <10ms DKT inference (GPU) |
| Experiment Tracking | Weights & Biases | Hyperparameter tuning |

### A.6 Latency Breakdown (Real-Time Inference)

| Step | Component | Target |
|------|-----------|--------|
| Request routing | API Gateway | <5ms |
| Authentication | JWT validation | <5ms |
| Feature fetch | Redis | <5ms |
| Model inference | Triton/TensorRT | <10ms |
| Post-processing | Python worker | <5ms |
| Cache update | Redis | <5ms |
| **Total** | | **<35ms** |

### A.7 Integration Architecture

| External System | Protocol | Services |
|-----------------|----------|----------|
| LMS (Canvas, Blackboard) | LTI 1.3 Advantage | SSO, grade passback, deep linking |
| Clever | OAuth 2.0 + Webhooks | Instant Login, roster sync |
| Google Classroom | Google API | Course import, grade posting |
| SIS | OneRoster CSV/API | Grade export |

### A.8 Evidence-Based Design Constraints

**Explicitly Required:**
- Hybrid DKT+BKT knowledge tracing (AUC ≥ 0.85)
- Mastery-based progression gates (80-90% threshold)
- Spaced repetition scheduling
- Worked examples for novices
- Retrieval practice emphasis

**Explicitly Excluded:**
- VARK-based content routing
- Multiple Intelligences tracks
- Learning style assessments
- Content filtering by modality preference

---

## Appendix B: Platform Specifications

### B.1 API Contract Summary (from openapi.yaml)

#### Core REST Endpoints

| Category | Endpoint | Method | Purpose | Auth Scope |
|----------|----------|--------|---------|------------|
| **Auth** | `/auth/token` | POST | Obtain JWT access token | Public |
| **Auth** | `/auth/refresh` | POST | Refresh access token | Bearer |
| **Auth** | `/auth/revoke` | POST | Revoke token | Bearer |
| **Students** | `/students/me` | GET | Get current student profile | student:read |
| **Students** | `/students/me/knowledge-state` | GET | Get knowledge state | student:read |
| **Students** | `/students/me/progress` | GET | Get learning progress | student:read |
| **Students** | `/students/me/learning-path` | GET | Get personalized path | student:read |
| **Teachers** | `/teachers/{id}/classes` | GET | Get teacher's classes | teacher:read |
| **Teachers** | `/teachers/{id}/at-risk` | GET | Get at-risk alerts | teacher:read |
| **Teachers** | `/teachers/{id}/interventions` | POST | Create intervention | teacher:write |
| **Content** | `/content/modules/{id}` | GET | Get content module | content:read |
| **Content** | `/content/search` | GET | Search content | content:read |
| **Personalization** | `/personalization/recommendations` | POST | Get recommendations | student:read |
| **Personalization** | `/personalization/knowledge-update` | POST | Update from interaction | student:write |
| **Assessments** | `/assessments/diagnostic` | POST | Start diagnostic | student:read |
| **Assessments** | `/assessments/{id}/responses` | POST | Submit response | student:write |
| **Assessments** | `/assessments/{id}/results` | GET | Get results | student:read |
| **Analytics** | `/analytics/class/{id}/progress` | GET | Class analytics | teacher:read |
| **Parents** | `/parents/{id}/children` | GET | Get children | parent:read |
| **Parents** | `/parents/{id}/children/{sid}/progress` | GET | Child progress | parent:read |
| **GraphQL** | `/graphql` | POST | GraphQL query | Bearer |

#### Authentication & Authorization

**JWT Token Lifecycle:**
- Access Token: 15 minutes expiry
- Refresh Token: 7 days (rotate on use)
- Device fingerprint validation required

**OAuth 2.0 / OIDC Scopes:**
| Scope | Description |
|-------|-------------|
| `student:read` | Access own profile and progress |
| `student:write` | Update preferences |
| `teacher:read` | View assigned students |
| `teacher:write` | Assign content, override recommendations |
| `parent:read` | View child's progress |
| `admin:read` | District-wide analytics |
| `admin:write` | User provisioning, settings |

#### Key Data Models (API Schemas)

| Model | Key Fields |
|-------|------------|
| **Student** | id, email, first_name, last_name, grade_level (0-12), home_language, accommodations[] |
| **KnowledgeState** | student_id, skills[], updated_at |
| **SkillMastery** | skill_id, mastery_probability (0-1), attempts_count, last_attempt_at |
| **Progress** | student_id, time_spent_minutes, skills_mastered, skills_in_progress, current_streak_days |
| **ContentModule** | content_module_id, lo_id, title, module_type (instruction/practice/assessment/review), difficulty_tier (1-5), format_variants[] |
| **Recommendation** | module_id, lo_id, content_url, difficulty_tier, predicted_success_probability (0-1), recommendation_reason |
| **AtRiskAlert** | student_id, student_name, risk_score (0-1), risk_factors[], knowledge_gaps[], last_login_days_ago |
| **InteractionEvent** | student_id, module_id, event_type, timestamp, correctness (0-1), time_spent_seconds |

### B.2 Content Architecture Requirements

#### Content Granularity Model

| Level | Duration | Use Case |
|-------|----------|----------|
| Micro-item | 10-60 sec | Embedded checks |
| Module | 2-10 min | Primary delivery unit |
| Lesson | 20-45 min | Teacher assignment |
| Unit | 2-4 weeks | Curriculum mapping |

**Module Requirements:**
- Target exactly one LearningObjective
- Include at least one assessment point
- Completable within single session (≤10 min)
- Support interruption/resumption without data loss
- Include WCAG 2.1 Level AA accessibility metadata

#### Module Types by Pedagogical Purpose

| Type | Description | Mastery Contribution |
|------|-------------|---------------------|
| Exposition | Concept introduction | 0% (informational) |
| Worked Example | Step-by-step demonstration | 0% (scaffolding) |
| Practice Problem | Interactive skill application | 100% per completion |
| Assessment | Summative mastery verification | 100% if passed |
| Remediation | Alternative explanation | 100% per completion |
| Enrichment | Extension content | 0% (optional) |

#### Standards Alignment

**Supported Standards:**
- CCSS (Common Core State Standards)
- NGSS (Next Generation Science Standards)
- TEKS (Texas Essential Knowledge and Skills)
- SOL (Virginia Standards of Learning)
- Custom district standards

**Prerequisite Relationship Types:**
1. **Hard Prerequisite (`requires`)**: Must master before accessing
2. **Soft Prerequisite (`supports`)**: Facilitates learning, not blocking
3. **Transfer Relationship (`is_similar_to`)**: Used for DKT cross-skill inference

### B.3 Personalization Engine Specifications

#### Algorithm Selection

**Primary Algorithm: Hybrid DKT+BKT**
- **DKT (Deep Knowledge Tracing)**: LSTM-based for performance prediction
- **BKT (Bayesian Knowledge Tracing)**: Interpretable mastery thresholds
- **Combined AUC**: 0.85-0.90

**Performance Targets:**
| Metric | Target |
|--------|--------|
| End-to-end recommendation latency | <100ms |
| Knowledge state update | <50ms |
| Prediction AUC | ≥0.85 |
| Cold-start to useful predictions | ≤10 interactions |

#### Difficulty Adjustment Heuristics

| Student State | DKT P(success) | Difficulty Tier |
|---------------|----------------|-----------------|
| At-risk (struggling) | <0.50 | Tier 1 (easiest) |
| ZPD low | 0.50-0.65 | Tier 2 |
| ZPD optimal | 0.65-0.80 | Tier 3 |
| ZPD high | 0.80-0.85 | Tier 4 |
| Mastered | >0.85 | Tier 5 or advance |

#### Cold-Start Strategy

**Stage 1 (Interactions 1-3):** Grade-Level Priors
- Initialize BKT from historical cohort data
- P(L0): ~0.20-0.40 typical

**Stage 2 (Interactions 4-7):** Rapid Diagnostic
- IRT-based adaptive diagnostic
- Target: SE(θ) < 0.3 within 4 items per domain

**Stage 3 (Interactions 8-10):** Hybrid Warm-Up
- BKT provides mastery estimates
- DKT begins accumulating hidden state
- By interaction 10: AUC >0.75

#### Graceful Degradation Chain

1. **Primary**: Hybrid DKT+BKT with full personalization
2. **Fallback 1**: BKT only (if DKT unavailable)
3. **Fallback 2**: IRT-based ability-matched content
4. **Fallback 3**: Rule-based curriculum sequence
5. **Emergency**: Static content delivery

### B.4 Content Metadata Schema (32 Fields)

#### Identity Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| content_module_id | UUID | Yes | System-generated unique identifier |
| lo_id | String | Yes | Learning objective identifier |
| title | String | Yes | Human-readable title (max 120 chars) |
| description | Text | Yes | Full learning objective statement (max 2000 chars) |

#### Standards Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| standard_alignment | JSON | Yes | Aligned educational standards (CCSS, NGSS, TEKS) |

#### Pedagogy Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| prerequisite_ids | String[] | No | Learning objectives that must be mastered first |
| difficulty_index | Float | Yes | IRT-calibrated difficulty [0.0-1.0] |
| difficulty_tier | Integer | Yes | Discrete difficulty level [1-5] |
| cognitive_complexity | Integer | Yes | Webb's DoK level [1-4] |
| cognitive_load_design | JSON | Yes | CLT-informed design parameters |
| content_type | Enum | Yes | exposition, worked_example, practice_problem, assessment, enrichment, remediation |

#### Content Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| content_format | Enum | Yes | interactive, video, text, audio, manipulative, mixed |
| modality_variants | UUID[] | No | Content modules offering same objective in different formats |
| estimated_duration_minutes | Integer | Yes | Typical completion time [2-30] |
| learning_type_tags | String[] | No | Discovery tags (NOT for VARK/MI routing) |

#### Assessment Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| mastery_criteria | JSON | Yes | Conditions for mastery (min_correctness, min_attempts, time_threshold) |
| hint_sequence | JSON | Yes | Progressive hint structure (max 5 hints) |
| assessment_items | UUID[] | No | Embedded assessment item IDs |

#### Accessibility Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| accessibility_features | Enum[] | Yes | tts, captions, dyslexia_font, etc. |
| language_variants | JSON | No | Available language localizations |
| cognate_mappings | JSON | No | Cross-language cognate pairs for ELL |

#### Versioning Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| metadata_version | Integer | Yes | Content schema version |
| content_version | String | Yes | Semantic version (SemVer) |
| version_effective_date | Date | Yes | When version became default |
| supersedes_content | UUID | No | Previous content module this replaces |
| migration_rules | JSON | No | Rules for migrating student progress |

#### Administrative Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| authoring_metadata | JSON | Yes | Creation and modification tracking |
| keywords | String[] | No | Search and discovery tags (max 10) |
| interoperability_ids | JSON | No | External system identifiers (LTI, QTI, LOM) |
| analytics_tags | String[] | No | A/B testing and efficacy analysis tags |

### B.5 Database Schema Summary

#### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| **users** | User authentication | user_id, email, user_type, auth_provider |
| **students** | Student profile | student_id, grade_level, home_language, accommodations |
| **teachers** | Teacher profile | teacher_id, school_id, department |
| **parents** | Parent profile | parent_id, notification_preferences |
| **classes** | Class management | class_id, name, subject, grade_level, teacher_id |
| **class_enrollments** | Student-class links | enrollment_id, class_id, student_id |
| **learning_objectives** | Learning graph nodes | lo_id, code, title, grade_bands, cognitive_level |
| **content_modules** | Content storage | content_module_id, lo_id, module_type, difficulty_tier |
| **content_prerequisites** | Module dependencies | module_id, prerequisite_module_id, is_strict |
| **lo_prerequisites** | Learning objective graph | lo_id, prerequisite_lo_id, relationship_type |
| **standards** | Educational standards | standard_id, framework_id, code, description |
| **student_knowledge_state** | BKT parameters | student_id, lo_id, mastery_probability, p_guess, p_slip, p_learn |
| **learning_interactions** | Event log | interaction_id, student_id, content_module_id, event_type, correctness |
| **recommendations** | ML recommendations | recommendation_id, student_id, content_module_id, predicted_success_probability |
| **assessments** | Assessment sessions | assessment_id, student_id, assessment_type, status |
| **interventions** | Teacher interventions | intervention_id, student_id, teacher_id, intervention_type, status |
| **at_risk_alerts** | Risk notifications | alert_id, student_id, teacher_id, risk_score, risk_factors |

#### Key Indexes
- `idx_knowledge_state_student`: Fast knowledge state lookups
- `idx_interactions_student`: Interaction history queries
- `idx_content_search`: Full-text search on content
- `idx_recommendations_student`: Recommendation retrieval

### B.6 LTI 1.3 Integration Requirements

**Required Endpoints:**
| Endpoint | Purpose |
|----------|---------|
| `GET /lti/login` | Login initiation |
| `POST /lti/launch` | Launch endpoint |
| `GET /lti/jwks.json` | JWKS endpoint |
| `GET /lti/services/nrps/v2/context/{id}/memberships` | Names and Roles Service |
| `POST /lti/services/ags/v2/course/{id}/lineItems` | Assignment and Grade Services |

**Supported Flows:**
- Authorization Code flow for web apps
- PKCE for mobile apps
- Scope restrictions: `progress:read`, `content:write`, `admin:full`

### B.7 Multimodal Content Specifications

**Universal Design Principle:** All content has 2+ modalities available; students can self-select.

| Format | Technical Requirements |
|--------|----------------------|
| **Video** | MP4/H.264 primary, WebM fallback, WebVTT captions, 480p/720p/1080p tiers |
| **Audio** | MP3 128kbps minimum, transcript required, 0.5x-2x playback speed |
| **Text** | Markdown (CommonMark), MathML 3.0, UTF-8, OpenDyslexic font option |
| **Interactive** | HTML5 Canvas, touch + mouse + keyboard support, 44x44px touch targets |

**Accessibility Requirements (WCAG 2.1 AA):**
- Keyboard navigation (Tab/Enter/Arrow)
- Screen reader support (ARIA labels, semantic HTML)
- Captions for all video
- Color contrast 4.5:1 minimum
- Focus indicators visible
- Animation control (pause/stop)

### B.8 Error Handling Standards

**HTTP Status Codes:**
| Status | Usage |
|--------|-------|
| 200 | Successful GET/PUT/PATCH |
| 201 | Successful POST (resource created) |
| 204 | Successful DELETE |
| 400 | Invalid request format |
| 401 | Missing/invalid authentication |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Resource state conflict |
| 422 | Valid JSON but failed business rules |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

**Common Error Codes:**
- `INVALID_PARAMETER`: Parameter validation failed
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `INSUFFICIENT_PERMISSIONS`: User lacks required role/scope
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `CONTENT_VERSION_MISMATCH`: Content has been updated
- `MASTERY_THRESHOLD_NOT_MET`: Cannot advance without mastery

---

## Appendix C: UX Specifications and Security Requirements

### C.1 User Flow Specifications

#### C.1.1 Core User Flows Overview

| Flow ID | Flow Name | Primary Actor | Entry Points | Exit Points |
|---------|-----------|---------------|--------------|-------------|
| UF-01 | Student Onboarding | New Student | Direct registration, Clever SSO, Teacher class code, Parent invitation | Personalized dashboard ready |
| UF-02 | Daily Learning Session | Student | Dashboard continue, Teacher assignment, Spaced repetition reminder | Session summary/return to dashboard |
| UF-03 | Teacher Intervention | Teacher | At-risk alert, Dashboard priority alerts, Student flag | Intervention sent/tracked |
| UF-04 | Parent Check-In | Parent | Weekly email, Direct login, Child share | Action taken or portal closed |
| UF-05 | Assessment Experience | Student | Diagnostic (onboarding), Progress check, Spaced repetition | Results view/dashboard return |

#### C.1.2 Student Onboarding Flow (UF-01)

**Entry Points:**
| Entry | Trigger | Special Handling |
|-------|---------|------------------|
| Direct Registration | Student visits platform directly | COPPA age-gating for <13 |
| Clever SSO | District-rostered student | Skip account creation, import accommodations |
| Teacher Class Code | Student enters code from teacher | Auto-enroll in class, inherit settings |
| Parent Invitation | Email link from parent consent | Pre-populate parent contact |

**Flow Steps:**
```
[Start] → <Check for existing session> → {Existing?}
    ├─(yes)→ [Resume previous session] → [Dashboard]
    └─(no) → [Landing Page: Welcome message, value prop]
                    ↓
        [Select grade level: K-12 buttons]
                    ↓
        <COPPA Check: Grade K-5?> → {Under 13?}
            ├─(yes)→ [Parental Consent Workflow] → {Consent granted?}
            │           ├─(no) → [Access denied, email sent to parent]
            │           └─(yes)→ Continue below
            └─(no) → Continue below
                    ↓
        [Language Selection: Home language + Learning language]
                    ↓
        [Accommodation Preferences: Universal design checklist]
                    ↓
        [Brief Diagnostic: 8-12 adaptive items]
        <Initialize KnowledgeState based on responses>
                    ↓
        {Diagnostic completed?}
            ├─(no/student skipped)→ [Skip confirmation] → [Dashboard with default placement]
            └─(yes)→ [Diagnostic results: "You can start learning X, Y, Z!"]
                    ↓
        [Personalized Dashboard Reveal]
                    ↓
        [End: Student ready to learn]
```

#### C.1.3 Daily Learning Session Flow (UF-02)

**Entry Points:** Dashboard [Continue Learning], Teacher assignment notification, Spaced repetition reminder, New skill unlocked

**Flow Steps:**
```
[Start] → [Student Dashboard]
    ├─[Select "Continue Learning"] → <Fetch current learning path>
    ├─[Select "Review Items (n)"] → <Fetch spaced repetition queue>
    └─[Select specific skill from map] → <Fetch skill content>
                ↓
        [Content Loading State] → <PRESCRIBE algorithm runs>
        (Skeleton UI, <200ms target)
                ↓
        [Content Delivery Screen]
        (Problem stem + interaction area + support tools)
                ↓
        [Student interacts: attempts, requests hint, takes break]
                ↓
        <ASSESS: Capture interaction> → <DIAGNOSE: Update KnowledgeState>
                ↓
        [Immediate Feedback Screen]
            ├─Correct → [Growth-focused feedback] → [Next item ready]
            └─Incorrect → [Worked example/hint] → [Try again or continue]
                ↓
        {Continue session?}
            ├─(yes)→ [Transition to next content] → [Content Delivery Screen]
            └─(no) → [Session summary] → [Return to Dashboard]
```

#### C.1.4 Teacher Intervention Flow (UF-03)

**Entry Points:** At-risk alert notification, Dashboard priority alerts, Student flag from content, Scheduled review

**Flow Steps:**
```
[Start] → [Teacher Dashboard] → <Fetch at-risk scores for all students>
                ↓
        [Priority Alerts Section (sorted by risk score)]
            ├─[Click alert: Student X] → [Student Detail View]
            ├─[Click "Assign Intervention"] → [Intervention Composer]
            └─[Dismiss alert] → <Record dismissal reason>
                ↓
        [Student Detail View]
            ├─[View knowledge gaps] → [Learning graph with weak areas highlighted]
            ├─[View recent activity] → [Interaction timeline]
            └─[View accommodation usage] → [IEP compliance report]
                ↓
        [Intervention Composer]
            ├─[Accept AI recommendation]
            ├─[Modify recommendation]
            └─[Create custom assignment]
                ↓
        [Review & Send]
            ├─[Send to student] → <Notify student> → [Confirmation]
            └─[Schedule for later] → <Queue for delivery>
                ↓
        [Track Intervention]
            ├─[View student progress on assigned content]
            ├─[Adjust if needed]
            └─[Mark resolved / escalate]
                ↓
        [End: Return to dashboard]
```

#### C.1.5 Key UX Design Principles

| Principle | Implementation | Evidence Base |
|-----------|----------------|---------------|
| **No Learning Styles** | Onboarding gathers grade, language, accommodations, diagnostic - NOT VARK/MI | Pashler et al. (2008): "virtually no evidence" for meshing hypothesis |
| **Universal Design** | TTS, keyboard nav, high contrast available to all users | WCAG 2.1 Level AA compliance |
| **Modality Switching** | Students can request alternative representations (video, worked example, manipulative, text) | Ainsworth (2006): multiple representations support learning |
| **Growth Mindset** | Strategy praise, effort recognition, no public comparisons | Dweck growth mindset research |
| **Cognitive Load Management** | Break suggestions, progress saves automatically, hint system | Sweller Cognitive Load Theory |

#### C.1.6 Accessibility Requirements (WCAG 2.1 Level AA)

**Keyboard Navigation:**
| Element | Behavior |
|---------|----------|
| All interactive elements | Reachable via Tab/Shift+Tab |
| Modal dialogs | Trap focus, Escape to close |
| Dropdown menus | Arrow keys navigate, Enter selects |
| Learning map | Arrow keys move between nodes |
| Skip link | "Skip to main content" first focusable element |

**Screen Reader Support:**
| Element | Requirement |
|---------|-------------|
| Images | Descriptive alt text or aria-label |
| Dynamic updates | aria-live regions for notifications |
| Math content | MathML with alt text fallback |
| Progress indicators | aria-valuenow, aria-valuemax |
| Error messages | aria-describedby association |

**Visual Design:**
| Requirement | Implementation |
|-------------|----------------|
| Color contrast | 4.5:1 minimum for text |
| Focus indicators | 3px outline, high contrast |
| Text resizing | Supports 200% zoom without loss |
| Animation control | Pause/stop for auto-playing content |
| Touch targets | Minimum 44x44px (iOS) / 48x48dp (Android) |

### C.2 Security Requirements

#### C.2.1 Threat Model Summary

**Risk Distribution:**
- Critical: 8 threats
- High: 15 threats
- Medium: 22 threats
- Low: 12 threats

**Critical Threats:**
| Threat ID | Threat | Category | Mitigation |
|-----------|--------|----------|------------|
| AUTH-01 | Account Takeover - Brute force on student/teacher accounts | Spoofing | Rate limiting, MFA, breach detection |
| AUTH-03 | Privilege Escalation - Student gains teacher/admin access | Elevation | RBAC, principle of least privilege |
| DATA-01 | PII Exposure - Student PII leaked in breach | Info Disclosure | AES-256 encryption at rest/transit |
| DATA-02 | SQL Injection - Attacker extracts student database | Info Disclosure | Parameterized queries, ORM, WAF |
| DATA-05 | Cross-Tenant Data Leak - Student sees other school data | Info Disclosure | Row-level security, tenant ID validation |
| ADAPT-01 | Recommendation Manipulation - Attacker pushes harmful content | Tampering | Content moderation, teacher override |
| COMP-01 | COPPA Violation - Collecting data from <13 without consent | Compliance | Age verification, parental consent workflow |
| COMP-02 | FERPA Violation - Educational records disclosed without authorization | Compliance | Access controls, audit logging |

#### C.2.2 Authentication Requirements

**Multi-Factor Authentication:**
| User Type | Primary | Secondary | Tertiary |
|-----------|---------|-----------|----------|
| Students (K-5) | Picture password | Device binding | N/A |
| Students (6-12) | Password | Email/SMS OTP | N/A |
| Teachers | Password | Authenticator app | Hardware key (optional) |
| Admins | Password | Hardware key | Biometric |

**Session Management:**
- Access Token: 15 minutes expiry
- Refresh Token: 7 days (rotate on use)
- Device fingerprint validation required
- Session binding to IP address (optional)
- Automatic logout after 15 minutes inactivity

**Rate Limiting:**
| Endpoint | Rate Limit |
|----------|------------|
| Login attempts | 5 per 10 minutes per IP |
| Password reset | 3 per hour per email |
| API requests (student) | 100 per minute |
| API requests (teacher) | 1000 per minute |

#### C.2.3 Authorization Requirements

**Role-Based Access Control (RBAC):**
| Role | Permissions | Data Access |
|------|-------------|-------------|
| student | read:own, write:preferences | Own data only |
| teacher | read:class, write:assignments | Assigned classes |
| parent | read:children | Linked children |
| school_admin | read:school, write:users | School scope |
| district_admin | read:district, write:settings | District scope |
| system_admin | read:all, write:system | All (with audit) |

**Context-Aware Authorization:**
- Time-based: Access restricted during non-school hours for some roles
- Location-based: Geo-fencing for sensitive operations
- Device-based: Trusted device lists for high-privilege actions
- Behavioral: Anomaly detection for unusual access patterns

#### C.2.4 Data Protection Requirements

**Encryption Standards:**
| Layer | Method | Key Management |
|-------|--------|----------------|
| Database (PII) | AES-256 TDE | AWS KMS with automatic rotation |
| Database (Graph) | AES-256 GCM | HashiCorp Vault integration |
| In Transit | TLS 1.3 | Let's Encrypt with auto-renewal |
| Field-level PII | AES-256-GCM | Per-column keys |
| Backups | Encrypted | SSE-KMS with CMK |

**Key Management:**
- 90-day automatic rotation for data encryption keys
- Key hierarchy: Root key → DEK → Field-level keys
- HashiCorp Vault for key unseal
- AWS KMS as root of trust

**Sensitive Field Encryption:**
| Field | Encryption | Searchable |
|-------|------------|------------|
| student.name | AES-256-GCM | No (tokenized) |
| student.email | AES-256-GCM | No (hashed) |
| student.address | AES-256-GCM | No |
| iep.accommodations | AES-256-GCM | Yes (blind index) |

#### C.2.5 Privacy-Preserving Architecture

**Data Minimization:**
- Collect only data necessary for learning personalization
- 7-year maximum retention (K-12 span + audit requirements)
- PII pseudonymized within 30 days of account closure

**Differential Privacy:**
| Report Type | Epsilon | K-Anonymity |
|-------------|---------|-------------|
| District summary | 0.1 | n≥100 |
| School-level | 0.5 | n≥20 |
| Class-level | 1.0 | n≥10 |
| Individual | N/A (prohibited) | N/A |

**Federated Learning (Future):**
- Raw student data never leaves school premises
- Encrypted gradients for model updates
- Secure aggregation server

#### C.2.6 Compliance Requirements

**COPPA Compliance (16 CFR Part 312):**
- Verifiable parental consent for users under 13
- Age verification triggers parental consent workflow
- Electronic consent form, credit card verification, or school-mediated consent
- Parental rights portal: view data, delete account, download export
- Data minimization for minors

**FERPA Compliance (20 U.S.C. §1232g):**
- "School official" exception maintained
- Written Data Protection Agreement (DPA) with each school
- Direct control by educational institution
- No re-disclosure without authorization
- Audit logging of all data access

**State Privacy Laws:**
| State | Key Requirements | Implementation |
|-------|------------------|----------------|
| California (SOPIPA) | No targeted ads, no selling data | Ad-free platform, data use restrictions |
| Connecticut | Enhanced security, third-party contracts | Encryption, DPA enforcement |
| Colorado | Transparency, deletion rights | Privacy portal, data retention policies |
| New York (Ed Law 2-d) | Data encryption, breach notification | Encryption at rest/transit, incident response |

#### C.2.7 Audit and Monitoring

**Access Logging:**
```json
{
  "timestamp": "2026-03-13T10:30:00Z",
  "event_type": "student_data_access",
  "actor": {
    "type": "teacher",
    "id": "tch-12345",
    "school_id": "sch-789"
  },
  "resource": {
    "type": "student_progress",
    "student_id": "stu-99999"
  },
  "action": "read",
  "result": "success",
  "justification": "legitimate_educational_interest"
}
```

**Anomaly Detection:**
| Pattern | Alert Threshold | Response |
|---------|-----------------|----------|
| Bulk data export | >1000 records | Require admin approval |
| After-hours access | Outside 6am-10pm | Flag for review |
| New device login | First access | Require MFA |
| Failed login attempts | >5 in 10 min | Lock account |
| Privilege escalation | Any admin grant | Immediate notification |

**Security Testing Program:**
| Test Type | Frequency | Responsible |
|-----------|-----------|-------------|
| Penetration Testing | Quarterly | External vendor |
| Vulnerability Scanning | Weekly | Automated + security team |
| Dependency Scanning | Every build | CI/CD pipeline |
| Static Analysis (SAST) | Every commit | Git hooks + CI |
| Dynamic Analysis (DAST) | Weekly | Security team |

#### C.2.8 Incident Response

**Severity Classification:**
| Severity | Criteria | Response Time |
|----------|----------|---------------|
| Critical | Data breach, system compromise | 15 minutes |
| High | Unauthorized admin access, malware | 1 hour |
| Medium | Policy violation, suspicious activity | 24 hours |
| Low | Scanning, failed attempts | 72 hours |

**Data Breach Response Timeline:**
1. Detect (0-15 min): Automated alerts, manual report
2. Contain (15-60 min): Isolate affected systems, revoke access
3. Assess (1-4 hours): Determine scope, affected records
4. Notify (24-72 hours): Law enforcement, school contacts, parents (COPPA requirement for <13)
5. Recover (1-7 days): Restore from backups, patch vulnerabilities
6. Post-Incident (1-30 days): Root cause analysis, policy updates

---

*Document generated from executive summary, architecture review, platform specifications, UX specifications, and security architecture.*
## Appendix D: Implementation Roadmap and Priorities

## Appendix D: Implementation Roadmap and Priorities

### Implementation Phases Overview

| Phase | Timeline | Focus | Key Deliverables |
|-------|----------|-------|------------------|
| **Phase 1 (MVP)** | Months 1-6 | Core platform with BKT-only baseline | 13 Must-Have requirements; <500ms latency; 200+ learning objectives |
| **Phase 2 (Pilot)** | Months 7-12 | Controlled efficacy study | 3-5 schools, 600-1,000 students; DKT beta; A/B test framework |
| **Phase 3 (Scale)** | Months 13-18 | Multi-state rollout | 50K+ students; full DKT deployment; ELA/Science subjects |
| **Phase 4 (Optimize)** | Months 19-24 | Full feature set & international prep | Ensemble models; content automation; UK/AU expansion |

### MVP Month-by-Month Plan (Phase 1)

| Month | Focus | Key Deliverables |
|-------|-------|------------------|
| **1** | Foundation | Architecture decision records; CI/CD pipeline; data model implementation |
| **2** | Core Backend | User management; BKT engine (4 parameters: prior, learn, slip, guess); learning graph schema |
| **3** | Content & UX | Content ingestion pipeline; student dashboard; multimodal player; teacher assignment creation |
| **4** | Adaptive Loop | Recommendation engine (rule-based); spaced repetition scheduler; diagnostic assessment flow |
| **5** | Integration | LTI 1.3 launch; Clever rostering; WCAG 2.1 AA audit; load testing |
| **6** | Hardening | Security penetration test; bug bash; documentation; pilot school onboarding prep |

### Requirements Prioritization (MoSCoW Analysis)

#### Must Have (13 requirements) - Critical for MVP

| ID | Category | Requirement | Acceptance Criteria | Persona |
|----|----------|-------------|---------------------|---------|
| REQ-001 | Personalization | Real-time knowledge state tracking | BKT/DKT with AUC ≥ 0.80; <200ms updates | All Students |
| REQ-002 | Personalization | Spaced repetition engine | SM2 or LSTM-based algorithm; forgetting curve scheduling | All Students |
| REQ-003 | Personalization | Mastery-based progression | 80% mastery threshold; remediation loop | All Students |
| REQ-004 | Accessibility | Full keyboard/screen reader support | WCAG 2.1 AA; ARIA labels; NVDA/JAWS tested | Aiden, Elena |
| REQ-005 | Accessibility | Text-to-speech on all content | Speed 0.5x-2x; MathML equation reading | Aiden, Diego |
| REQ-006 | ELL Support | Cognate highlighting and visual scaffolding | Identifies cognates; picture glossary | Diego |
| REQ-007 | Teacher Tools | Early warning system for at-risk students | <50% success prediction; daily updates; filterable | James |
| REQ-008 | Teacher Tools | Standards-aligned assignment creation | CCSS/NGSS selection; gradebook export | James |
| REQ-009 | Privacy | Verifiable parental consent (COPPA) | VPC workflow for <13; electronic/credit card consent | David, Maya |
| REQ-010 | Privacy | FERPA-compliant Data Protection Agreements | DPA template; use restrictions; destruction timeline | Dr. Williams |
| REQ-017 | Infrastructure | <200ms page load times | p95 API response <200ms; CDN; progressive loading | All |
| REQ-018 | Infrastructure | LTI 1.3 / Clever / Google Classroom integration | SSO; rostering; OneRoster export | Dr. Williams, James |
| NFR-001 | Non-Functional | 99.9% uptime during school hours | Monthly measurement; auto failover; status page | All |
| NFR-002 | Non-Functional | AES-256 encryption at rest; TLS 1.3 in transit | Key rotation; no plaintext PII; audit logging | All |
| NFR-003 | Non-Functional | WCAG 2.1 Level AA compliance | Automated testing; manual screen reader validation | All |

#### Should Have (5 requirements) - Important for full launch

| ID | Category | Requirement | Rationale |
|----|----------|-------------|-----------|
| REQ-011 | Content | Teacher content authoring tool | Major competitive gap; differentiation feature |
| REQ-012 | Student Experience | Growth mindset progress visualization | Reduces math anxiety; Dweck research support |
| REQ-013 | Student Experience | Enrichment content for high achievers | Engagement for ceiling students |
| REQ-014 | Admin | District-wide learning analytics | ESSA evidence generation; equity gap identification |
| REQ-015 | Parent | Weekly progress summaries | COPPA transparency; parent engagement correlation |

#### Could Have (2 requirements) - Nice to have

| ID | Category | Requirement | Rationale |
|----|----------|-------------|-----------|
| REQ-016 | SPED | IEP goal progress monitoring | Compliance requirement; integration gap |
| REQ-019 | ELL | Native language diagnostics | Improved validity; significant content cost |

#### Won't Have (Phase 1) - Deferred

| ID | Category | Requirement | Deferred Rationale |
|----|----------|-------------|-------------------|
| REQ-020 | Advanced | AI conversational tutor | Evidence base emerging; safety/compliance complexity |

### MVP Technical Architecture Summary

```
┌──────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                            │
│  React Web App (Chromebook-optimized) + iOS/Android wrappers │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                    API GATEWAY (Kong)                        │
│  Authentication, Rate Limiting, Request Routing              │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────┬───────────────────────────────────────┐
│   ADAPTIVE SERVICE   │         CONTENT SERVICE               │
│   - BKT Engine       │         - Module Delivery             │
│   - Recommendation   │         - Progress Tracking           │
│   - Knowledge State  │         - Standards Alignment         │
├──────────────────────┼───────────────────────────────────────┤
│   GRAPH DB (Neo4j)   │         DOCUMENT STORE (MongoDB)      │
│   Learning topology  │         Content modules               │
├──────────────────────┴───────────────────────────────────────┤
│              RELATIONAL DB (PostgreSQL)                      │
│              Users, Classes, Assignments, Events             │
└──────────────────────────────────────────────────────────────┘
```

### MVP Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| Feature completeness | 100% must-have (13/13) | Requirements traceability matrix |
| System uptime | ≥99.5% | Synthetic monitoring |
| End-to-end latency | <500ms (p95) | APM instrumentation |
| BKT prediction accuracy | AUC ≥0.75 | Held-out validation set |
| Content coverage | ≥200 learning objectives | CMS audit |
| Security audit | Zero critical vulnerabilities | Third-party penetration test |
| Privacy compliance | COPPA/FERPA checklist pass | Legal review |

### Critical Path Items (Must Be Built First)

1. **Month 1-2**: Core backend infrastructure + BKT engine (REQ-001)
2. **Month 2**: User management and authentication (prerequisite for all features)
3. **Month 3**: Content ingestion and delivery pipeline (prerequisite for learning loop)
4. **Month 4**: Adaptive recommendation engine integrating BKT + content (REQ-001, REQ-002, REQ-003)
5. **Month 5**: LTI/Clever integration for school deployment (REQ-018)
6. **Month 6**: Security hardening and privacy compliance (REQ-009, REQ-010, NFR-002)

### Go/No-Go Decision Gates

| Gate | Timing | Criteria |
|------|--------|----------|
| **MVP Complete** | Month 6 | 100% must-have features; AUC ≥0.75; security audit pass; privacy compliance |
| **Pilot Launch** | Month 9 | Content coverage ≥80%; teacher training ≥90%; consent ≥95%; load test pass |
| **Scale Decision** | Month 18 | Significant efficacy (p<0.05, d≥0.4); ≥70% engagement; viable unit economics |

---

---

## Appendix E: Target Tool Scope Definition

### E.1 Tool Identity: Adaptive Knowledge State & Recommendation Engine (AKSRE)

Based on synthesis of the architecture specifications, platform requirements, UX flows, and implementation roadmap, the **specific tool to be built** is the **Adaptive Knowledge State & Recommendation Engine (AKSRE)**—the core personalization microservice that powers the adaptive learning loop.

**Why This Tool?**
- It is the **#1 Must-Have requirement** (REQ-001: Real-time knowledge state tracking)
- It sits on the **critical path** for all other adaptive features (Months 2-4 of roadmap)
- It implements the **5-Phase Adaptive Feedback Loop** central to the platform value proposition
- It is the **differentiating technology** (Hybrid DKT+BKT) with no off-the-shelf equivalent

### E.2 Tool Boundaries

**IN SCOPE (What This Tool Does):**

| Capability | Description | Boundaries |
|------------|-------------|------------|
| **Knowledge State Management** | Track student proficiency per learning objective using BKT parameters | Stores only BKT parameters (P(L), P(T), P(G), P(S)); DKT hidden state managed separately |
| **Real-Time Inference** | Compute mastery probabilities and predict success on unseen content | Returns P(mastery) and P(success) only; does NOT select final content |
| **Learning Interaction Processing** | Update knowledge states from student responses | Consumes correctness + time spent; emits updated state events |
| **Spaced Repetition Scheduling** | Calculate optimal review intervals per skill | SM2 algorithm implementation; returns due timestamps |
| **Recommendation Scoring** | Rank content candidates by predicted success probability | Returns scored list; does NOT apply final filtering (done by Recommendation Service) |
| **Cold-Start Handling** | Initialize knowledge states for new students | Grade-level priors + IRT diagnostic integration |

**OUT OF SCOPE (What Other Components Do):**

| Capability | Responsibility | Interface |
|------------|----------------|-----------|
| Content Selection | Recommendation Service | Accepts scored list, applies business rules |
| Content Delivery | Delivery Service | Renders content; AKSRE provides mastery thresholds |
| User Authentication | Auth Service | JWT validation happens at API Gateway |
| Teacher Dashboard | Analytics Service | Reads knowledge state via API |
| LTI/Clever Integration | Integration Service | Handles external LMS protocols |
| Graph Storage | Learning Graph Service (Neo4j) | AKSRE queries prerequisite relationships |
| ML Model Training | ML Pipeline (Kubeflow) | Trains DKT; AKSRE only runs inference |

### E.3 Input/Output Contracts

#### E.3.1 Primary API Endpoints

| Endpoint | Method | Input | Output | Latency Target |
|----------|--------|-------|--------|----------------|
| `/knowledge-state/{studentId}` | GET | Student ID, optional skill filter | Knowledge state vector (BKT params per LO) | <50ms |
| `/knowledge-state/update` | POST | Student ID, LO ID, correctness, timeSpent | Updated mastery probability, next review date | <50ms |
| `/predictions/{studentId}` | GET | Student ID, content candidate IDs | Array of {contentId, pSuccess, pMastery} | <100ms |
| `/recommendations/score` | POST | Student ID, learning objective ID, count | Ranked content modules with scores | <100ms |
| `/spaced-repetition/due` | GET | Student ID, horizon (default 24h) | Array of LOs due for review with priority | <50ms |
| `/diagnostic/initialize` | POST | Student ID, grade level | Initialized BKT parameters for all grade-level LOs | <200ms |

#### E.3.2 Event Interfaces

**Consumes (Input Events):**
```json
{
  "eventType": "LEARNING_INTERACTION",
  "studentId": "uuid",
  "learningObjectiveId": "string",
  "contentModuleId": "uuid",
  "correctness": 0.0-1.0,
  "timeSpentSeconds": integer,
  "timestamp": "ISO-8601",
  "context": { "hintUsed": boolean, "attempts": integer }
}
```

**Produces (Output Events):**
```json
{
  "eventType": "KNOWLEDGE_STATE_UPDATED",
  "studentId": "uuid",
  "learningObjectiveId": "string",
  "bktParams": {
    "pLearned": 0.0-1.0,
    "pLearn": 0.0-1.0,
    "pGuess": 0.0-1.0,
    "pSlip": 0.0-1.0
  },
  "masteryProbability": 0.0-1.0,
  "masteryAchieved": boolean,
  "nextReviewDate": "ISO-8601"
}
```

#### E.3.3 Data Store Contracts

**Reads From:**
| Store | Data | Purpose |
|-------|------|---------|
| Redis (Hot) | Current knowledge states | Sub-millisecond state retrieval |
| Cassandra | Historical interaction events | BKT parameter recalculation |
| Neo4j (via Graph Service) | Prerequisite relationships | Determine learning frontier |
| PostgreSQL | Grade-level priors, IRT parameters | Cold-start initialization |

**Writes To:**
| Store | Data | Purpose |
|-------|------|---------|
| Redis (Hot) | Updated knowledge states | Real-time availability |
| Cassandra | Interaction events | Persistent audit trail |
| Kafka | Knowledge state update events | Downstream consumption |

### E.4 Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              ADAPTIVE KNOWLEDGE STATE & RECOMMENDATION ENGINE    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │  API Controller │◄──►│  BKT Engine     │◄──►│  State Store│  │
│  │  (REST/gRPC)    │    │  (Core Logic)   │    │  (Redis)    │  │
│  └─────────────────┘    └────────┬────────┘    └─────────────┘  │
│           │                       │                              │
│           │              ┌────────┴────────┐    ┌─────────────┐  │
│           │              │  DKT Inference  │◄──►│  Model Svc  │  │
│           │              │  (Optional)     │    │  (Triton)   │  │
│           │              └─────────────────┘    └─────────────┘  │
│           │                                                      │
│           ▼                       ┌─────────────────┐            │
│  ┌─────────────────┐              │  Spaced Rep     │            │
│  │  Event Handler  │◄────────────►│  Scheduler      │            │
│  │  (Kafka Consumer)│             │  (SM2 Algorithm)│            │
│  └─────────────────┘              └─────────────────┘            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                             │
│  │  Cassandra      │                                             │
│  │  (Event Store)  │                                             │
│  └─────────────────┘                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌─────────┐          ┌─────────┐          ┌─────────┐
   │Neo4j    │          │Analytics│          │Recommend│
   │(Graph)  │          │Service  │          │Service  │
   └─────────┘          └─────────┘          └─────────┘
```

### E.5 Success Criteria for This Tool

| Criterion | Target | Measurement Method |
|-----------|--------|-------------------|
| **BKT Update Latency** | <50ms p95 | Synthetic monitoring on `/knowledge-state/update` |
| **Prediction Latency** | <100ms p95 | Load testing on `/predictions` endpoint |
| **BKT Accuracy** | AUC ≥ 0.75 (MVP), ≥ 0.85 (Phase 2) | Held-out validation set on historical data |
| **Hybrid DKT+BKT Accuracy** | AUC ≥ 0.85 | Same as above with DKT enabled |
| **Cold-Start Performance** | Useful predictions by interaction 10 | AUC > 0.75 after 10 interactions |
| **Spaced Repetition Validity** | 80%+ retention at 30 days | A/B test vs. control |
| **System Availability** | 99.9% uptime | Synthetic health checks |
| **Concurrent Capacity** | 10K+ updates/second | Load testing with 1M simulated students |

### E.6 Technology Stack (Tool-Specific)

| Layer | Technology | Justification |
|-------|------------|---------------|
| **Language** | Python 3.11+ | Rich ML ecosystem (PyTorch, NumPy, SciPy) |
| **Web Framework** | FastAPI | Async support, auto-generated OpenAPI docs |
| **BKT Implementation** | Custom + `pyBKT` library | Proven BKT algorithms with customization |
| **DKT Inference** | PyTorch + ONNX Runtime | GPU acceleration via NVIDIA Triton |
| **State Storage** | Redis Cluster | Sub-millisecond reads/writes |
| **Event Store** | Apache Cassandra | High write throughput, time-series optimized |
| **Message Bus** | Apache Kafka | Event streaming for downstream consumers |
| **Observability** | Prometheus + Jaeger | Metrics and distributed tracing |

### E.7 Implementation Phases for This Tool

**Phase 1: BKT-Only MVP (Months 1-3)**
- [ ] BKT 4-parameter model implementation (P(L0), P(T), P(G), P(S))
- [ ] Redis-based knowledge state storage
- [ ] REST API for state updates and queries
- [ ] Grade-level prior initialization
- [ ] SM2 spaced repetition scheduler
- [ ] Unit test coverage >80%

**Phase 2: Hybrid DKT+BKT Integration (Months 4-6)**
- [ ] DKT LSTM model inference endpoint
- [ ] Hybrid scoring algorithm (BKT for mastery, DKT for ranking)
- [ ] Cold-start diagnostic integration
- [ ] Performance optimization (<100ms target)
- [ ] A/B testing framework integration

**Phase 3: Production Hardening (Months 7-9)**
- [ ] Multi-region deployment
- [ ] Graceful degradation (BKT-only fallback)
- [ ] Comprehensive observability
- [ ] Load testing at 1M student scale
- [ ] Security audit and penetration testing

### E.8 Integration Checkpoints

| Checkpoint | Dependencies | Validation |
|------------|--------------|------------|
| **Month 2** | User Service, PostgreSQL | Can initialize knowledge states for new students |
| **Month 3** | Content Service, Neo4j | Can query prerequisites for recommendation context |
| **Month 4** | Recommendation Service | Can provide scored content candidates |
| **Month 5** | Delivery Service | Can influence content sequencing in real-time |
| **Month 6** | Analytics Service | Can export knowledge states for teacher dashboards |

---

*Document Version: 1.0 | Last Updated: March 14, 2026*
