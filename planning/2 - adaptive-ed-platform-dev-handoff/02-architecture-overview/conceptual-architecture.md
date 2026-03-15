---
author: Educational Technology Research Team
classification: Architecture Specification
date: '2026-03-13'
version: '1.0'
---

# Conceptual Architecture: Adaptive K-12 Learning Platform

## Executive Summary

This document defines the conceptual architecture for an evidence-based adaptive K-12 learning platform. The design synthesizes learning science research, regulatory requirements, and stakeholder needs into a coherent system organized around a **Learning Graph** metaphor for knowledge representation, a **Knowledge Tracing Student Model**, and a **5-Phase Adaptive Feedback Loop**.

**Key Architectural Principles:**
1. **Evidence-Based Design**: Reject learning styles (VARK/MI) for personalization; implement mastery-based progression, spaced retrieval, and knowledge tracing (BKT/DKT)
2. **Privacy-First**: COPPA/FERPA-compliant data architecture with data minimization by design
3. **Accessibility-First**: WCAG 2.1 Level AA compliance as non-negotiable requirement
4. **Modularity**: Clean separation between student model, content model, and delivery mechanisms to support future evolution

## System Metaphor: The Learning Graph

The central architectural metaphor is a **Learning Graph**—a directed acyclic graph (DAG) representing the universe of learnable knowledge for K-12 education.

### Graph Structure

**Nodes: Learning Objectives (LOs)**
Each node represents a single, measurable learning objective aligned to educational standards:

| Property | Description | Example |
|----------|-------------|---------|
| `lo_id` | Unique identifier | `CCSS.MATH.4.NF.A.1` |
| `standard_code` | External standard alignment | `4.NF.A.1` (CCSS) |
| `description` | Human-readable objective | "Explain why a fraction a/b is equivalent to (n×a)/(n×b)" |
| `domain` | Subject domain | `mathematics`, `ela`, `science` |
| `grade_band` | Target grade range | `4-5` |
| `difficulty_index` | Calibrated difficulty (IRT-based) | `0.65` |
| `cognitive_complexity` | Webb's Depth of Knowledge | `2` (Skill/Concept) |
| **NOT INCLUDED** | Learning style tags | **Explicitly excluded**—no VARK/MI labels |

**Edges: Prerequisite Relationships**
Directed edges represent prerequisite dependencies:
- `requires` (hard prerequisite): Must master LO-A before attempting LO-B
- `supports` (soft prerequisite): Knowledge of LO-A facilitates LO-B but not strictly required
- `is_similar_to` (transfer relationship): Knowledge of LO-A predicts performance on LO-B

**Graph Properties:**
- **Acyclic**: No circular dependencies in curriculum sequences
- **Graded**: Edge weights represent prerequisite strength (0.0-1.0) based on empirical co-occurrence
- **Multi-domain**: Cross-domain relationships (e.g., reading comprehension supports math word problems)

### Graph Traversal Metaphor
Students navigate the Learning Graph as explorers traversing a knowledge landscape:
- **Current Position**: Student's frontier of mastered and learning objectives
- **Visible Territory**: Prerequisites and next objectives within reach
- **Hidden Territory**: Future objectives beyond current knowledge horizon
- **Paths**: Multiple valid sequences through the graph to achieve mastery of a target objective

## Core Domain Models

### Model 1: Student (Learner Entity)

Represents the human learner and their persistent identity within the system.

| Attribute | Type | Description | Privacy Classification |
|-----------|------|-------------|----------------------|
| `student_id` | UUID | System-generated identifier (not PII) | Non-PII |
| `anonymous_token` | Hash | Reversible pseudonym for analytics | Pseudonymous |
| `grade_level` | Enum | Current grade enrollment (K-12) | Directory Info |
| `enrollment_context` | JSON | School, class, teacher associations | Educational Record (FERPA) |
| `iep_504_flags` | Enum[] | Accommodation categories | Educational Record |
| `language_preference` | ISO 639-1 | Primary interface language | Non-PII |
| `home_language` | ISO 639-1 | L1 for ELL support | Educational Record |
| `created_at` | Timestamp | Account creation date | Metadata |
| **NOT STORED** | VARK profile | **Excluded**—no evidence base | N/A |
| **NOT STORED** | MI scores | **Excluded**—no evidence base | N/A |

**Key Design Decision**: Student model captures developmental stage, linguistic context, and documented accommodations—not "learning styles." Personalization derives from real-time knowledge state, not static categorical assignments.

### Model 2: KnowledgeState (Dynamic Student Model)

The KnowledgeState represents the platform's evolving understanding of what the student knows—updated after every interaction. This is the core of the adaptive engine.

**Architecture: Hybrid Knowledge Tracing**

The system implements a hybrid approach combining:
1. **Deep Knowledge Tracing (DKT)** for primary skill mastery prediction (AUC target: 0.85+)
2. **Bayesian Knowledge Tracing (BKT)** for interpretable mastery thresholds and prerequisite analysis

| Component | Purpose | Data Structure |
|-----------|---------|----------------|
| `dkt_hidden_state` | LSTM hidden state vector (128-dim) capturing temporal knowledge evolution | Float[] |
| `bkt_params` | Per-skill BKT parameters: P(L₀), P(T), P(G), P(S) | Dict[lo_id → BKTParams] |
| `mastery_map` | Current mastery probability per LO | Dict[lo_id → Float(0-1)] |
| `response_history` | Compressed interaction sequence (last 1000 items) | Interaction[] |
| `forgetting_curve_params` | Individual decay rates per skill for spaced repetition | Dict[lo_id → (alpha, beta)] |
| `engagement_state` | Current cognitive load indicators, attention signals | Real-time metrics |

**State Update Trigger**: Every student interaction (problem attempt, hint request, content view, pause/resume)

**Latency Requirement**: KnowledgeState update must complete within <50ms to maintain responsive experience.

### Model 3: LearningObjective (Graph Node)

The LearningObjective represents a discrete, assessable unit of knowledge within the Learning Graph.

| Attribute | Type | Description |
|-----------|------|-------------|
| `lo_id` | String | Unique identifier (e.g., `CCSS.MATH.4.NF.A.1`) |
| `canonical_name` | String | Human-readable name |
| `full_description` | Text | Complete objective statement |
| `standard_alignment` | JSON | Aligned standards (CCSS, NGSS, state) |
| `prerequisite_ids` | String[] | Direct prerequisite LOs (hard requirements) |
| `supporting_ids` | String[] | Related LOs that facilitate learning |
| `difficulty_index` | Float | Calibrated difficulty via IRT (0-1) |
| `discrimination` | Float | IRT discrimination parameter |
| `cognitive_complexity` | Int | Webb's DoK (1-4) |
| `estimated_time_minutes` | Int | Typical time to mastery |
| `domain_tags` | String[] | Subject/topic classifications |
| `content_modules` | UUID[] | Associated content resources |

**Graph Topology Operations**:
- `get_prerequisite_closure(lo_id)` → Returns all transitive prerequisites
- `get_frontier(student_id)` → Returns LOs where all prerequisites are mastered
- `get_learning_path(start, target)` → Returns optimal sequence using DKT predictions

### Model 4: ContentModule (Delivery Unit)

The ContentModule represents a specific piece of learning content—atomic, multimodal, and metadata-rich.

| Attribute | Type | Description |
|-----------|------|-------------|
| `module_id` | UUID | Unique identifier |
| `lo_id` | String | Target learning objective |
| `module_type` | Enum | `exposition`, `worked_example`, `practice_problem`, `assessment`, `enrichment` |
| `content_format` | Enum | `interactive`, `video`, `text`, `audio`, `manipulative` |
| `difficulty_tier` | Int | 1-5 calibrated difficulty within LO |
| `cognitive_load_design` | JSON | CLT-informed design parameters |
| `accessibility_features` | Enum[] | `tts`, `captions`, `dyslexia_font`, `high_contrast` |
| `language_variants` | JSON | Available languages, cognate mappings |
| `media_assets` | UUID[] | Associated media (images, audio, video) |
| `assessment_items` | UUID[] | Embedded or associated assessments |
| `hint_sequence` | UUID[] | Progressive hint structure |
| `metadata_version` | Int | Content versioning for curriculum updates |

**Content Granularity Principles**:
- **Smallest deliverable unit**: A ContentModule should represent 2-10 minutes of student engagement
- **Single objective focus**: Each module targets exactly one LearningObjective
- **Multimodal variants**: Same learning objective, different presentation modalities (NOT based on VARK preference—universal design principle)

### Model 5: Interaction (Event Log)

The Interaction is the immutable record of every student-system touchpoint—essential for knowledge tracing, analytics, and audit compliance.

| Attribute | Type | Description |
|-----------|------|-------------|
| `interaction_id` | UUID | Unique identifier |
| `student_id` | UUID | Reference to Student |
| `module_id` | UUID | Reference to ContentModule |
| `lo_id` | String | Target learning objective |
| `timestamp` | Timestamp | ISO 8601 with millisecond precision |
| `session_id` | UUID | Grouping for session analysis |
| `interaction_type` | Enum | `attempt`, `hint_request`, `view`, `completion`, `abandon` |
| `response_data` | JSON | Student input (answer, selection, etc.) |
| `correctness` | Float | 0.0-1.0 graded correctness (partial credit supported) |
| `time_spent_seconds` | Int | Engagement duration |
| `hint_count` | Int | Hints requested before response |
| `cognitive_load_signals` | JSON | Pause patterns, scroll behavior, etc. |
| `device_context` | JSON | Screen size, input method (privacy-sanitized) |

**Event Sourcing Pattern**: All interactions are immutable, append-only events. KnowledgeState is a computed projection from the interaction stream.

## The Adaptive Feedback Loop: Assess-Diagnose-Prescribe-Deliver-Verify

The core adaptive engine operates as a continuous 5-phase feedback loop with strict latency requirements at each phase.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ADAPTIVE FEEDBACK LOOP                           │
│                    (Target: <200ms end-to-end)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐       │
│   │  ASSESS  │──→│ DIAGNOSE │──→│ PRESCRIBE│──→│  DELIVER │──┐    │
│   │          │   │          │   │          │   │          │  │    │
│   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │    │
│         ↑                                                    │    │
│         └────────────────────────────────────────────────────┘    │
│                              VERIFY                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 1: ASSESS (Target: Real-time)

**Purpose**: Capture student interaction data and update knowledge state.

**Inputs**:
- Student response to current content item
- Behavioral signals (time on task, hint usage, hesitation patterns)
- Context (device, session duration, prior interactions in session)

**Process**:
1. Validate and normalize response data
2. Compute immediate correctness (graded response)
3. Extract cognitive load indicators (pauses, revisions, abandonment signals)
4. Emit Interaction event to event stream

**Outputs**:
- Graded response (correctness score)
- Updated engagement metrics
- Real-time cognitive load estimate

**Latency**: <10ms (synchronous blocking)

### Phase 2: DIAGNOSE (Target: <50ms)

**Purpose**: Update student knowledge state and identify learning needs.

**Process**:
1. **DKT Inference**: Feed interaction through LSTM to update hidden state
   - Input: (lo_id, correctness, time_spent, hint_count)
   - Output: Updated hidden state vector, performance prediction on all LOs
2. **BKT Update**: Update Bayesian parameters for the specific LO attempted
   - Apply standard BKT update rules for P(Lₙ)
   - If mastery probability crosses threshold (e.g., 0.85), mark LO mastered
3. **Forgetting Curve Update**: Adjust individual decay parameters based on performance
4. **Anomaly Detection**: Flag unexpected performance (potential guess/slip or system error)

**Outputs**:
- Updated mastery_map: Dict[lo_id → P(mastery)]
- Updated dkt_hidden_state
- Risk flags: at_risk_lo_ids (where P(success) < 0.5 for upcoming material)
- Forgetting-sensitive items requiring review

**Latency**: <50ms (asynchronous, non-blocking preferred)

### Phase 3: PRESCRIBE (Target: <100ms cumulative)

**Purpose**: Select optimal next content based on updated knowledge state.

**Decision Algorithm**:

```
PRESCRIBE(student_id, current_context):
    
    # Priority 1: Spaced repetition items due for review
    review_queue = get_due_reviews(student_id, now())
    if review_queue.any(due_within(minutes=5)):
        return select_optimal_review(review_queue, cognitive_load_budget)
    
    # Priority 2: Prerequisite remediation if risk detected
    at_risk = get_at_risk_objectives(student_id)
    if at_risk.not_empty():
        target_prereq = get_highest_impact_prerequisite(at_risk)
        return get_remediation_content(target_prereq)
    
    # Priority 3: New content within zone of proximal development
    frontier = get_learning_frontier(student_id)  # Prerequisites met, not mastered
    zpd_candidates = filter_by_dkt_prediction(frontier, success_prob=0.5-0.85)
    
    if zpd_candidates.not_empty():
        target_lo = select_by_optimization(zpd_candidates, criteria={
            'difficulty_match': 0.3,
            'prerequisite_strength': 0.3,
            'student_interest': 0.2,
            'curriculum_sequence': 0.2
        })
        return get_new_content(target_lo, difficulty_tier=match_current_performance())
    
    # Priority 4: Enrichment content for high-performing students
    if all_frontier_mastered(student_id):
        return get_enrichment_content(get_frontier_extension(student_id))
    
    # Fallback: Diagnostic or engagement content
    return get_diagnostic_reassessment(student_id)
```

**Content Selection Factors** (weighted multi-objective optimization):
1. **Knowledge Tracing Prediction**: Target 50-85% success probability (zone of proximal development)
2. **Spaced Repetition Schedule**: Prioritize items approaching forgetting threshold
3. **Prerequisite Strength**: Select LOs with strongest mastered prerequisites
4. **Cognitive Load Management**: Monitor session load; offer worked examples if load high
5. **Teacher Constraints**: Respect teacher-assigned topics/pacing if specified

**Outputs**:
- Selected ContentModule ID
- Recommended difficulty tier
- Suggested scaffolding level (hints, worked examples)

**Latency**: <100ms cumulative from interaction

### Phase 4: DELIVER (Target: <200ms cumulative)

**Purpose**: Render selected content with appropriate accommodations and presentation.

**Process**:
1. **Content Retrieval**: Fetch ContentModule with all variants
2. **Accommodation Application** (based on student profile, NOT learning style):
   - IEP/504 accommodations (extended time, TTS, reduced animations)
   - ELL supports (cognate highlighting, visual scaffolding, native language resources)
   - Accessibility features (keyboard navigation, screen reader labels)
3. **Cognitive Load Optimization**:
   - Apply CLT principles (split-attention reduction, worked example fading)
   - Adjust element interactivity based on estimated working memory load
4. **Presentation Rendering**: Generate final HTML/interactive content

**Outputs**:
- Rendered content package (HTML, media assets, interaction handlers)
- Pre-fetched next items for seamless transition

**Latency**: <200ms cumulative (95th percentile)

### Phase 5: VERIFY (Continuous)

**Purpose**: Validate learning outcomes and system effectiveness; feed data back into model improvement.

**Verification Levels**:
1. **Immediate**: Did student engage with delivered content? (engagement metrics)
2. **Short-term**: Did student demonstrate mastery on target LO? (assessment correctness)
3. **Medium-term**: Did mastery persist after spaced interval? (retention check)
4. **Long-term**: Did learning transfer to new contexts? (cross-domain performance)

**Feedback Mechanisms**:
- **To Student**: Immediate feedback on responses; progress indicators
- **To Teacher**: At-risk alerts; mastery dashboards; intervention recommendations
- **To System**: Model drift detection; content efficacy analysis; algorithm A/B testing

## Architectural Principles

### Principle 1: Privacy-By-Design

**Data Minimization**:
- Collect only data necessary for learning personalization and regulatory compliance
- Aggregate analytics use differential privacy for small-group protection
- Student PII strictly separated from interaction data (pseudonymous analytics)

**Consent Management**:
- COPPA verifiable parental consent workflow for <13 users
- Granular consent categories (learning vs. research vs. marketing)
- One-click data export and deletion (right to portability/erasure)

**Security**:
- Encryption at rest (AES-256) and in transit (TLS 1.3)
- Zero-trust architecture; no implicit trust between services
- Audit logging of all data access with tamper-proof storage

### Principle 2: Accessibility-First

**WCAG 2.1 Level AA Compliance** (non-negotiable):
- All functionality keyboard accessible
- Screen reader compatibility (ARIA labels, semantic HTML)
- Color contrast minimum 4.5:1
- Focus indicators visible
- Pause/stop controls for animations

**Universal Design** (NOT accommodation-only):
- Text-to-speech available to all users, not just documented disabilities
- Captions on all video content
- Multiple input methods (touch, keyboard, voice where appropriate)
- Adjustable text size and spacing

### Principle 3: Modularity and Evolvability

**Service Boundaries**:
- **Student Model Service**: KnowledgeState management, DKT/BKT inference
- **Content Service**: ContentModule storage, retrieval, versioning
- **Learning Graph Service**: Topology operations, prerequisite analysis
- **Recommendation Service**: PRESCRIBE algorithm implementation
- **Delivery Service**: Content rendering, accommodation application
- **Analytics Service**: Event processing, reporting, model evaluation

**API Contracts**:
- REST/GraphQL APIs with semantic versioning
- Event-driven async communication between services
- Backward compatibility guarantees for core APIs

**Extensibility Points**:
- Pluggable recommendation algorithms (A/B testing framework)
- Custom content types via plugin architecture
- Third-party integrations via LTI 1.3, Clever, xAPI

### Principle 4: Evidence-Based Constraints

**Explicitly Excluded Features** (per learning science research):
- VARK-based content routing or labeling
- Multiple Intelligences-based curriculum tracks
- "Learning style" assessment during onboarding
- Content filtering by preferred modality

**Explicitly Required Features** (per evidence):
- Mastery-based progression gates (80-90% threshold)
- Spaced repetition scheduling (SM2 or LSTM-based)
- Worked examples for novice learners
- Retrieval practice emphasis over passive review
- Knowledge tracing (BKT/DKT) for difficulty adaptation

## High-Level Data Flow

### Student Learning Session Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         LEARNING SESSION FLOW                            │
└──────────────────────────────────────────────────────────────────────────┘

Student                    Client                     Services
────────                   ──────                     ────────
   │                          │                            │
   │  1. Login/Start Session  │                            │
   │ ────────────────────────→│                            │
   │                          │  2. Fetch KnowledgeState    │
   │                          │ ─────────────────────────→ │
   │                          │                            │
   │                          │ ←───────────────────────── │
   │                          │   (mastery_map, dkt_state) │
   │                          │                            │
   │  3. Show Dashboard       │                            │
   │ ←────────────────────────│                            │
   │                          │                            │
   │  4. Select/Start Content │                            │
   │ ────────────────────────→│                            │
   │                          │  5. PRESCRIBE next content  │
   │                          │ ─────────────────────────→ │
   │                          │                            │
   │                          │ ←───────────────────────── │
   │                          │   (module_id, params)      │
   │                          │                            │
   │                          │  6. DELIVER content         │
   │                          │ ─────────────────────────→ │
   │                          │                            │
   │  7. Render Interactive   │                            │
   │     Content              │                            │
   │ ←────────────────────────│                            │
   │                          │                            │
   │  8. Student Interacts    │                            │
   │ ────────────────────────→│                            │
   │                          │  9. ASSESS & DIAGNOSE       │
   │                          │     (async event stream)    │
   │                          │ ─────────────────────────→ │
   │                          │                            │
   │  10. Immediate Feedback  │                            │
   │ ←────────────────────────│                            │
   │                          │                            │
   │  11. Next Content Ready  │                            │
   │     (pre-fetched)        │                            │
   │ ←────────────────────────│                            │
   │                          │                            │
   │  ... Loop continues ...  │                            │
   │                          │                            │
```

### Background Data Flows

**Knowledge State Updates** (Continuous):
```
Interaction Events → Kafka/Event Hub → DKT/BKT Inference Workers → KnowledgeState Cache → Persistent Store
```

**Analytics Pipeline** (Batch + Streaming):
```
Interaction Stream → Feature Engineering → Model Training (retraining) → Model Registry → Inference Services
```

**Content Updates** (Versioned):
```
Curriculum Authoring → Content Review → Version Control → CDN Deployment → Content Service Index Update
```

## Latency and Performance Requirements

| Phase | Target Latency | Critical Path | Scaling Strategy |
|-------|----------------|---------------|------------------|
| ASSESS (response capture) | <10ms | Synchronous | Single-region, in-memory |
| DIAGNOSE (model update) | <50ms | Asynchronous preferred | Distributed inference |
| PRESCRIBE (recommendation) | <100ms cumulative | Synchronous | Cached predictions + fallback |
| DELIVER (content render) | <200ms cumulative | Synchronous | CDN + edge caching |
| End-to-End (interaction → next content) | <200ms at 95th percentile | Critical | Pre-fetching, optimistic UI |

**Scalability Targets**:
- 1,000,000+ concurrent active students
- 10,000+ interactions per second sustained
- 99.9% uptime during school hours (7am-5pm local time)

**Resilience Patterns**:
- Circuit breakers for model inference (fallback to rule-based)
- Graceful degradation: Content delivery continues even if personalization unavailable
- Cache warming for high-priority content

## Technology Stack Recommendations (High-Level)

### Data Storage

| Data Type | Primary Store | Rationale |
|-----------|---------------|-----------|
| Learning Graph (topology) | Graph database (Neo4j) or relational with recursive CTEs | Prerequisite traversal queries |
| KnowledgeState | Key-value (Redis) + Columnar (Cassandra/DynamoDB) | Fast reads, high write throughput |
| Interaction Events | Append-only log (Kafka/Kinesis) + Object storage (S3) | Event sourcing, replay capability |
| Content Modules | Document store (MongoDB) + CDN (CloudFront/Fastly) | Flexible schema, global distribution |
| Student PII | Relational (PostgreSQL) with encryption | ACID compliance, audit requirements |

### Compute

| Component | Recommendation | Rationale |
|-----------|----------------|-----------|
| DKT/BKT Inference | GPU-enabled inference service (NVIDIA Triton/TensorRT) | Low-latency model serving |
| API Services | Kubernetes + auto-scaling | Elastic scaling for school hours |
| Event Processing | Apache Flink/Spark Streaming | Stateful stream processing |
| Content Delivery | Edge CDN with dynamic content optimization | Global low-latency delivery |

### ML Infrastructure

- **Model Training**: Kubeflow/MLflow pipelines
- **Feature Store**: Feast or Tecton for feature consistency
- **Experiment Tracking**: MLflow or Weights & Biases
- **Model Registry**: Centralized model versioning and A/B testing

**Privacy-Preserving ML Options**:
- Federated learning for model improvement without centralizing raw data
- Differential privacy for aggregate analytics
- On-device inference for sensitive recommendations

## Integration Architecture

### LMS Integration (LTI 1.3 Advantage)

The platform integrates as an LTI 1.3 Tool Provider:
- Single sign-on via OIDC
- Grade passback via Assignment and Grade Services
- Deep linking for context-aware content selection
- Names and Role Provisioning Services for roster sync

### Identity and Rostering (Clever, ClassLink)

- **Clever**: Instant Login + Secure Sync for roster import
- **ClassLink**: Roster Server and OneClick SSO
- **Google Classroom**: Course and student import via Classroom API

### Standards Alignment

- **xAPI (Experience API)**: Granular learning activity tracking
- **OneRoster**: Gradebook export format
- **QTI 2.1**: Assessment item interchange

### Analytics Export

- **Data portability**: CSV/JSON export for districts
- **SIS integration**: Direct connectors for PowerSchool, Infinite Campus, Skyward
- **Research partnerships**: Differential privacy-enabled datasets for academic research

## Risk Analysis and Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Model inaccuracy** (DKT/AUC below threshold) | Medium | High | Hybrid BKT fallback; continuous model evaluation; human-in-the-loop override for teachers |
| **Algorithmic bias** | Medium | High | Bias auditing on demographic subgroups; differential performance monitoring; fairness constraints in optimization |
| **Privacy breach** | Low | Critical | Encryption at rest/transit; zero-trust network; regular penetration testing; SOC 2 Type II compliance |
| **Content efficacy gaps** | Medium | Medium | Continuous A/B testing; teacher feedback loops; rapid content iteration pipeline |
| **Latency degradation** | Medium | High | Graceful degradation to rule-based recommendations; CDN failover; circuit breakers |
| **Regulatory changes** | Medium | Medium | Modular privacy controls; legal monitoring; flexible consent architecture |

### Human-in-the-Loop Safeguards

**Teacher Override**:
- Teachers can assign specific content bypassing recommendation engine
- At-risk alerts presented to teachers for human judgment
- Content difficulty override for individual students

**Parental Controls**:
- Time limits and scheduling controls
- Content visibility settings
- Progress sharing preferences

## Summary and Next Steps

This conceptual architecture defines an evidence-based adaptive learning platform organized around:

1. **Learning Graph**: DAG representation of K-12 knowledge with prerequisite relationships
2. **Hybrid Student Model**: DKT for prediction + BKT for interpretable mastery thresholds
3. **5-Phase Adaptive Loop**: Assess → Diagnose → Prescribe → Deliver → Verify (<200ms)
4. **Core Domain Models**: Student, KnowledgeState, LearningObjective, ContentModule, Interaction

**Key Evidence-Based Decisions**:
- ✅ Implement mastery-based progression, spaced repetition, knowledge tracing
- ❌ Exclude learning styles (VARK/MI) from personalization logic
- ✅ Design for cognitive load management and retrieval practice
- ✅ Prioritize accessibility and privacy as first-class requirements

**Next Phase Dependencies**:
- Detailed personalization engine specification (algorithm pseudocode, model architectures)
- Content architecture (metadata schema, versioning strategy)
- User experience design (flows, wireframes, interaction patterns)
- Technical infrastructure specification (API contracts, security architecture)
