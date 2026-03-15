---
classification: Technical Validation
date: '2026-03-14'
version: '1.0'
---

# Requirements Validation: AKSRE Implementation

## Executive Summary

This document identifies ambiguities, conflicting specifications, and missing information in the AKSRE (Adaptive Knowledge State & Recommendation Engine) requirements. All identified issues have been resolved through documented assumptions with rationale. No blocking questions require user clarification at this time.

## Validation Methodology

Requirements were validated against:
- requirements-spec.md (Appendices A-E)
- research-synthesis.md
- Platform API contracts and database schemas
- Architecture specifications

Each ambiguity was classified as:
- **Resolved via Assumption**: Documented with rationale
- **Non-blocking Gap**: Acknowledged but deferrable
- **Blocking Question**: Requires user clarification (none identified)

## Ambiguities and Resolutions

## A1. BKT Parameter Defaults

**Ambiguity**: Specifications mention 4 BKT parameters (P(L0), P(T), P(G), P(S)) and "grade-level priors" but don't specify default values or initialization formulas.

**Resolution**: Assumed defaults based on research synthesis:
| Parameter | Default Value | Rationale |
|-----------|---------------|-----------|
| P(L0) - Prior Knowledge | 0.30 | Research synthesis indicates ~0.20-0.40 typical for grade-level priors; 0.30 is conservative middle |
| P(T) - Learning Rate | 0.20 | Standard BKT literature value for single skill acquisition |
| P(G) - Guess Rate | 0.15 | 4-option MCQ baseline; adjusted per content format |
| P(S) - Slip Rate | 0.10 | Typical for well-designed assessments |

**Source**: Research synthesis citing Bhattacharjee & Wayllace (2025) and standard BKT literature.

---

## A2. DKT vs API Latency Gap

**Ambiguity**: Architecture specifies DKT inference <10ms, but API contract targets <100ms for predictions. The 90ms gap accounts for network overhead but isn't explicitly documented.

**Resolution**: Assumed latency budget breakdown:
| Component | Budget | Cumulative |
|-----------|--------|------------|
| API Gateway auth | 5ms | 5ms |
| Feature fetch (Redis) | 5ms | 10ms |
| DKT inference | 10ms | 20ms |
| BKT update/combine | 5ms | 25ms |
| Response serialization | 5ms | 30ms |
| Network overhead | 20ms | 50ms |
| **Total p95** | | **<100ms** |

The <100ms API target accommodates p95 variability while <50ms is the internal processing target.

---

## A3. IRT Diagnostic Integration

**Ambiguity**: Cold-start strategy mentions "IRT-based adaptive diagnostic" but no IRT endpoints exist in the API contract.

**Resolution**: Assumed IRT is handled by a separate Assessment Service, not AKSRE. AKSRE receives diagnostic results via the `/diagnostic/initialize` endpoint. IRT implementation is OUT OF SCOPE for AKSRE.

---

## A4. Spaced Repetition Algorithm Selection

**Ambiguity**: Both SM2 (traditional) and LSTM-based spacing are referenced without clear MVP vs. Phase 2 distinction.

**Resolution**: Assumed implementation phases:
- **MVP (Phase 1)**: SM2 algorithm only - proven, interpretable, no ML training required
- **Phase 2**: Optional LSTM-based optimization if SM2 validation data collected

**Rationale**: SM2 is sufficient for MVP; LSTM requires significant interaction history to outperform SM2.

---

## A5. Prerequisite Checking Responsibility

**Ambiguity**: Boundary between AKSRE (scoring) and Recommendation Service (filtering) is unclear regarding prerequisite validation.

**Resolution**: Assumed division of responsibility:
| Function | Owner | Interface |
|----------|-------|-----------|
| Prerequisite existence check | Learning Graph Service | AKSRE queries via API |
| Prerequisite mastery status | AKSRE | Returns BKT mastery probability |
| Final prerequisite enforcement | Recommendation Service | Blocks content if prereq P(mastery) < 0.70 |

AKSRE provides `pMastery` for prerequisites; Recommendation Service applies business rules.

---

## A6. Data Store Write Strategy

**Ambiguity**: Spec mentions Redis (hot) and Cassandra (persistent) but doesn't specify write strategy.

**Resolution**: Assumed write pattern:
1. **Synchronous write**: Redis (for immediate consistency)
2. **Asynchronous write**: Cassandra (via Kafka topic for durability)
3. **Read path**: Always from Redis (hot path)
4. **Recovery**: Cassandra replay if Redis failure

**Rationale**: Optimizes for read latency while ensuring durability.

---

## A7. Mastery Threshold Definition

**Ambiguity**: Appendix B specifies 80% mastery threshold, but Appendix E doesn't explicitly confirm this for AKSRE implementation.

**Resolution**: Assumed AKSRE uses **P(mastery) >= 0.80** as the mastery threshold for:
- Progression gates
- Mastery achievement flag in events
- Prerequisite satisfaction

**Rationale**: Consistent with research synthesis citing Bloom (1968) and Sutiawan et al. (2025).

---

## A8. DKT Hidden State Ownership

**Ambiguity**: Spec says "DKT hidden state managed separately" but doesn't specify which component owns this.

**Resolution**: Assumed DKT hidden state is owned by the **ML Model Service (Triton)** not AKSRE:
- AKSRE sends interaction sequences to Triton
- Triton maintains LSTM hidden state
- AKSRE receives prediction results only
- Hidden state persistence handled by ML Pipeline

---

## A9. Neo4j Access Pattern

**Ambiguity**: Spec says AKSRE "queries prerequisite relationships" from Neo4j but doesn't specify direct DB access vs. API.

**Resolution**: Assumed AKSRE accesses Neo4j **indirectly via Learning Graph Service API**, not direct database connection:
- Direct DB access violates service boundary principles
- Learning Graph Service provides `/prerequisites/{loId}` endpoint
- AKSRE makes HTTP call with <20ms target

---

## A10. Event Schema Versioning

**Ambiguity**: Event schemas don't include version fields for backward compatibility.

**Resolution**: Assumed event schemas include `schemaVersion` field:
```json
{
  "eventType": "KNOWLEDGE_STATE_UPDATED",
  "schemaVersion": "1.0",
  ...
}
```
- MVP: Version 1.0
- Future breaking changes: Increment minor version
- Consumers must handle unknown versions gracefully

---

## A11. Batch vs. Real-Time Updates

**Ambiguity**: Spec mentions both real-time updates and batch processing without clear primary mode.

**Resolution**: Assumed **real-time is primary**, batch is supplementary:
- **Real-time**: `/knowledge-state/update` endpoint for live learning
- **Batch**: Nightly recalculation job for BKT parameter recalibration
- **Offline**: Import job for historical data migration only

---

## A12. Content Format Scoring

**Ambiguity**: Spec doesn't specify if AKSRE scoring varies by content format (video, interactive, text).

**Resolution**: Assumed **format-agnostic scoring**:
- AKSRE scores at Learning Objective level, not Content Module level
- Content format affects Delivery Service rendering, not knowledge state
- All formats contribute equally to BKT update if they assess the same LO

**Exception**: Diagnostic assessments may have different P(G)/P(S) per item type.

## Conflicting Specifications

## C1. BKT Accuracy Targets

**Conflict**: 
- Appendix B (Platform Specs) states BKT-only AUC ~0.75
- Appendix E (AKSRE Scope) requires AUC >= 0.75 (MVP)
- Research synthesis shows BKT AUC 0.70-0.78

**Resolution**: Accepted 0.75 as the MVP target. This is achievable for BKT with proper parameter fitting and represents the conservative bound from research.

---

## C2. Latency Targets

**Conflict**:
- Executive summary: <200ms end-to-end (p95)
- Appendix A: <35ms internal processing
- Appendix E: <50ms for knowledge updates, <100ms for predictions

**Resolution**: Hierarchical targets are complementary, not conflicting:
- **Internal processing**: <35ms (component)
- **AKSRE API**: <50ms (updates), <100ms (predictions)
- **End-to-end**: <200ms (includes Content Delivery, UIs)

---

## C3. Hybrid Model Timing

**Conflict**:
- Implementation roadmap (Appendix D): BKT-only Month 2, DKT Month 4
- AKSRE scope (Appendix E): Hybrid DKT+BKT in Phase 2 (Months 4-6)

**Resolution**: No conflict - timelines align. BKT-only MVP (Months 1-3), Hybrid integration (Months 4-6).

---

## C4. Cold-Start Definition

**Conflict**:
- Appendix B: Cold-start to useful predictions in <=10 interactions
- Research synthesis: AUC > 0.75 by interaction 10

**Resolution**: "Useful predictions" defined as AUC > 0.75. Both specifications align at 10 interactions.

## Missing Information (Non-Blocking)

## M1. Specific BKT Parameter Learning Algorithm

**Gap**: Specification doesn't specify how BKT parameters are learned/fitted.

**Assumption**: Use Expectation-Maximization (EM) algorithm with the following:
- Training data: Historical interaction sequences
- Update frequency: Weekly batch job
- Convergence criteria: Log-likelihood delta < 0.001
- Regularization: Add-one smoothing for P(G), P(S)

**Rationale**: EM is standard in pyBKT library and BKT literature.

---

## M2. Student Accommodation Handling

**Gap**: Spec mentions accommodations but doesn't specify how they affect knowledge state tracking.

**Assumption**: Accommodations affect Delivery Service only, not AKSRE:
- Extended time: Captured in `timeSpentSeconds` but doesn't modify BKT update
- TTS/hints: Captured in `context` field; may adjust P(G)/P(S) in future phases
- AKSRE is accommodation-agnostic for MVP

---

## M3. Multi-Language Support

**Gap**: No specification for knowledge state tracking across languages.

**Assumption**: Each language variant treated as separate Learning Objective:
- `lo_id` includes language code suffix (e.g., `3.NF.A.1-en`, `3.NF.A.1-es`)
- Knowledge states are per-LO, so per-language automatically
- Cross-language transfer (if implemented) is Phase 2+

---

## M4. Concurrent Update Handling

**Gap**: No specification for race conditions when student submits multiple responses.

**Assumption**: 
- Student sessions serialize interactions per LO
- Redis atomic operations (INCR, HINCRBY) for counters
- Last-write-wins for BKT parameter updates (eventual consistency acceptable)
- Conflict resolution: Use interaction timestamp ordering

## Explicit Assumptions Summary

| # | Assumption | Impact if Wrong | Mitigation |
|---|------------|-----------------|------------|
| A1 | BKT defaults: P(L0)=0.30, P(T)=0.20, P(G)=0.15, P(S)=0.10 | Suboptimal predictions early in student lifecycle | Make configurable; tune with production data |
| A4 | SM2 for MVP, LSTM spacing for Phase 2 | May need to accelerate LSTM if SM2 underperforms | Collect SM2 data for LSTM training baseline |
| A5 | AKSRE provides scores, Recommendation Service filters | Blurred service boundaries | Clear API contracts; integration tests |
| A7 | Mastery threshold = 0.80 | May need adjustment based on teacher feedback | Configurable threshold per deployment |
| A8 | DKT hidden state owned by Triton | Complexity if AKSRE must manage state | Confirm Triton stateful inference capability |
| A9 | Learning Graph Service API for prerequisites | Latency impact if direct DB faster | Cache prerequisite results in Redis |

All assumptions are reversible with configuration changes, not requiring architectural rework.

## Blocking Questions

**None identified.**

All identified ambiguities have been resolved through documented assumptions with research-backed rationale. The requirements are internally consistent and sufficient for architecture design and implementation.

**If clarification needed later**:
1. BKT parameter defaults can be tuned via configuration
2. Mastery threshold can be adjusted per deployment
3. Latency targets can be relaxed if hardware constraints emerge

## Requirements Consistency Confirmation

## Internal Consistency Check

| Dimension | Status | Notes |
|-----------|--------|-------|
| **Functional** | ✅ Consistent | All features map to MoSCoW Must-Have requirements |
| **Performance** | ✅ Consistent | Latency targets are hierarchical and additive |
| **Data Model** | ✅ Consistent | Domain models align across architecture and API specs |
| **Algorithm** | ✅ Consistent | Hybrid DKT+BKT is consistent recommendation throughout |
| **Security** | ✅ Consistent | COPPA/FERPA requirements align across all specs |
| **Integration** | ✅ Consistent | Service boundaries defined with clear interfaces |

## Sufficiency for Implementation

The requirements are **sufficient** for:
1. ✅ Architecture design (module structure defined)
2. ✅ API specification (endpoints and contracts documented)
3. ✅ Data model implementation (schema references provided)
4. ✅ Algorithm implementation (BKT formulas standard; DKT via Triton)
5. ✅ Testing strategy (success criteria and targets specified)

## Validation Sign-off

| Validator | Finding |
|-----------|---------|
| Technical Consistency | ✅ Pass - No contradictions found |
| Completeness | ✅ Pass - All Must-Have requirements have implementation paths |
| Measurability | ✅ Pass - Success criteria are quantifiable |
| Feasibility | ✅ Pass - Architecture proven in research synthesis |

**Conclusion**: Requirements validated. Proceed to architecture design phase.
