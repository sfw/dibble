---
author: Educational Technology Research Team
classification: Technical Specification
date: '2026-03-13'
version: '1.0'
---

## Executive Summary

This specification defines the algorithmic architecture for the adaptive personalization engine of the K-12 learning platform. The engine implements a **hybrid DKT+BKT approach** that balances prediction accuracy (AUC 0.85-0.90) with interpretability required for educational stakeholders.

**Key Design Decisions:**
1. **Hybrid Knowledge Tracing**: Deep Knowledge Tracing (LSTM-based) for performance prediction + Bayesian Knowledge Tracing for interpretable mastery thresholds
2. **Explicit Rejection of Learning Styles**: Per the learning science research and architectural principles, VARK/MI-based personalization is excluded
3. **Zone of Proximal Development Targeting**: Content recommendation targets 50-85% predicted success probability
4. **Spaced Repetition Integration**: SM2-based review scheduling combined with DKT forgetting curve modeling

**Performance Targets:**
- End-to-end recommendation latency: <100ms (cumulative from interaction)
- Knowledge state update: <50ms
- Prediction AUC: ≥0.85
- Cold-start to useful predictions: ≤10 interactions

## 1. Algorithm Selection Rationale

## 1.1 Comparative Analysis

| Algorithm | AUC | Inference Complexity | Interpretability | Cold Start | Recommendation |
|-----------|-----|---------------------|------------------|------------|----------------|
| **BKT** | 0.70-0.78 | O(1) - constant | High | Grade-level priors | Mastery gates |
| **DKT (LSTM)** | 0.82-0.89 | O(n) - linear | Low | Population init | Primary predictions |
| **Transformer-KT** | 0.85-0.91 | O(n²) - quadratic | Low | Pre-trained | Phase 2 enhancement |
| **IRT-3PL** | 0.75-0.82 | O(1) - constant | High | Population θ | Diagnostics |
| **Hybrid DKT+BKT** | **0.85-0.90** | **O(n)** | **Medium** | **Hierarchical** | **RECOMMENDED** |

## 1.2 Why Hybrid DKT+BKT?

**Rationale per Learning Science Evidence:**
- DKT captures complex temporal patterns and skill relationships automatically (Piech et al., 2015; Mai et al., 2025)
- BKT provides transparent mastery thresholds required for teacher trust and regulatory compliance (Ben David et al., 2016)
- BKT handles cold-start scenarios with grade-level priors while DKT warms up (Bhattacharjee & Wayllace, 2025)

**Computational Feasibility:**
- LSTM inference: ~5-10ms on GPU for 100-step sequence
- BKT update: <1ms per skill
- Combined: Meets <50ms target for knowledge state updates

## 1.3 Why NOT Learning Styles (VARK/MI)?

Per Pashler et al. (2008): "Virtually no evidence" supports the "meshing hypothesis" that matching instruction to preferred learning modality improves outcomes. The platform explicitly:
- Does NOT assess VARK preferences
- Does NOT route content by "learning style"
- Does NOT label students by modality preference
- DOES provide multimodal content universally (not selectively)

## 2. Core Recommendation Algorithm (Pseudocode)

```python
function PRESCRIBE(student_id, context):
    """
    Core recommendation algorithm with <100ms latency target.
    Returns: (content_module_id, difficulty_tier, scaffolding_level)
    """
    
    # Phase 1: Retrieve current knowledge state (<10ms)
    knowledge_state = get_knowledge_state(student_id)
    dkt_hidden = knowledge_state.dkt_hidden_vector
    mastery_map = knowledge_state.bkt_mastery_probs  # Dict[lo_id, P(mastery)]
    
    # Phase 2: Priority 1 - Spaced Repetition Review (<20ms)
    due_reviews = get_due_reviews(student_id, horizon_minutes=30)
    if due_reviews.has_critical_items(due_within_minutes=5):
        target_lo = select_by_forgetting_priority(due_reviews)
        content = select_content(
            lo_id=target_lo,
            difficulty=REVIEW_DIFFICULTY,
            format_variants=get_all_modalities()  # Universal, not filtered
        )
        return (content.module_id, content.difficulty_tier, SCAFFOLD_MINIMAL)
    
    # Phase 3: Priority 2 - Prerequisite Remediation (<20ms)
    at_risk = identify_at_risk_objectives(student_id, threshold=0.50)
    if at_risk:
        # Use BKT for transparent prerequisite chain analysis
        weakest_prereq = get_highest_impact_prerequisite(at_risk, mastery_map)
        if mastery_map[weakest_prereq] < MASTERY_THRESHOLD:
            content = select_content(
                lo_id=weakest_prereq,
                difficulty=REMEDIATION_DIFFICULTY,
                include_worked_examples=True  # CLT for struggling learners
            )
            return (content.module_id, content.difficulty_tier, SCAFFOLD_HIGH)
    
    # Phase 4: Priority 3 - Zone of Proximal Development (<30ms)
    frontier = get_learning_frontier(student_id)  # Prereqs met, not mastered
    
    # DKT predicts success probability for each candidate
    zpd_candidates = []
    for lo in frontier:
        p_success = dkt_predict_success(dkt_hidden, lo)
        if 0.50 <= p_success <= 0.85:  # ZPD definition: challenging but achievable
            zpd_candidates.append((lo, p_success))
    
    if zpd_candidates:
        # Multi-objective optimization for final selection
        target_lo = optimize_selection(zpd_candidates, criteria={
            'dkt_prediction': 0.30,      # Accuracy of challenge level
            'prerequisite_strength': 0.25, # Solid foundation
            'curriculum_sequence': 0.20,   # Teacher/standards alignment
            'engagement_diversity': 0.15,  # Variety in recent content
            'time_since_last_attempt': 0.10 # Spacing consideration
        })
        
        difficulty = match_difficulty_to_prediction(target_lo, mastery_map)
        content = select_content(target_lo, difficulty, format_variants=get_all_modalities())
        return (content.module_id, content.difficulty_tier, SCAFFOLD_MEDIUM)
    
    # Phase 5: Priority 4 - Enrichment or Diagnostic (<20ms)
    if all_frontier_mastered(student_id):
        extension = get_frontier_extension(student_id)
        content = get_enrichment_content(extension)
        return (content.module_id, content.difficulty_tier, SCAFFOLD_MINIMAL)
    
    # Fallback: Diagnostic assessment
    return get_diagnostic_content(student_id)
```

## 2.1 Difficulty Adjustment Heuristics

| Student State | DKT P(success) | Action | Difficulty Tier |
|---------------|----------------|--------|-----------------|
| At-risk (struggling) | <0.50 | Remediation with worked examples | Tier 1 (easiest) |
| ZPD low | 0.50-0.65 | Guided practice with hints | Tier 2 |
| ZPD optimal | 0.65-0.80 | Standard difficulty | Tier 3 |
| ZPD high | 0.80-0.85 | Challenge problems | Tier 4 |
| Mastered | >0.85 | Enrichment or next objective | Tier 5 or advance |

## 3. Cold-Start Handling Strategy

## 3.1 New Student Onboarding (0-10 interactions)

**Stage 1: Grade-Level Priors (Interactions 1-3)**
```python
def initialize_cold_start_student(grade_level, subject):
    """Initialize BKT priors from historical cohort data"""
    return {
        'P(L0)': COHORT_PRIORS[grade_level][subject],  # ~0.20-0.40 typical
        'P(T)': 0.30,  # Standard learning rate
        'P(G)': 0.20,  # Guess probability
        'P(S)': 0.10   # Slip probability
    }
```

**Stage 2: Rapid Diagnostic (Interactions 4-7)**
- Use IRT-based adaptive diagnostic to quickly estimate ability
- Select items to maximize information gain (Fisher information)
- Target: SE(θ) < 0.3 within 4 items per domain

**Stage 3: Hybrid Warm-Up (Interactions 8-10)**
- BKT provides mastery estimates from sparse data
- DKT begins accumulating hidden state
- By interaction 10: DKT predictions achieve AUC >0.75

## 3.2 New Content/Skills

When new Learning Objectives are added to the curriculum:
- Initialize BKT parameters from similar existing skills (transfer learning)
- Use DKT skill embeddings to predict relationships
- Cold-start content treated as medium difficulty until calibrated (n≥100 responses)

## 4. Learning Path Optimization

## 4.1 Graph-Based Path Planning

The learning path is computed over the Learning Graph (DAG of Learning Objectives):

```python
function COMPUTE_OPTIMAL_PATH(student_id, target_lo_id, max_steps=20):
    """
    A* search variant using DKT predictions as heuristic.
    Returns: Ordered list of LOs to master.
    """
    start = get_current_frontier(student_id)
    target = target_lo_id
    
    # A* with DKT-informed cost function
    def path_cost(path):
        expected_time = sum(
            estimated_time_to_master(lo, student_id) 
            for lo in path
        )
        return expected_time
    
    def heuristic(lo_id):
        # DKT estimates success probability on target from current state
        return dkt_estimate_steps_to_target(student_id, lo_id, target)
    
    return a_star_search(start, target, path_cost, heuristic)
```

## 4.2 Multi-Objective Path Optimization

For students with multiple learning goals (e.g., catch-up on prerequisites + advance in current topic):

```python
function MULTI_GOAL_PATH(student_id, target_lo_ids, constraints):
    """
    Genetic algorithm-based optimization (Wu, 2025)
    """
    population = generate_initial_paths(target_lo_ids)
    
    for generation in range(MAX_GENERATIONS):
        fitness_scores = [
            evaluate_path_fitness(path, criteria={
                'total_time': 0.30,
                'prerequisite_coverage': 0.25,
                'engagement_predicted': 0.20,
                'teacher_alignment': 0.15,
                'review_efficiency': 0.10
            })
            for path in population
        ]
        
        population = evolve_population(population, fitness_scores)
    
    return select_pareto_optimal(population)
```

## 4.3 Dynamic Replanning

Path is recomputed when:
- Mastery achieved faster/slower than predicted (>20% deviation)
- New at-risk skills identified
- Teacher assigns new priority standards
- Student performance anomaly detected (sudden drop/gain)

## 5. Data Requirements for Personalization

## 5.1 Training Data (DKT Model)

| Requirement | Specification | Purpose |
|-------------|---------------|---------|
| Minimum samples | 100,000 interaction sequences | Basic pattern learning |
| Recommended | 1,000,000+ sequences | Robust cross-skill transfer |
| Sequence length | 50-500 interactions per student | Temporal pattern capture |
| Demographic coverage | Representative of target population | Fairness across subgroups |
| Temporal span | 6+ months per sequence | Forgetting curve modeling |

## 5.2 Calibration Data (IRT/BKT)

| Requirement | Specification | Purpose |
|-------------|---------------|---------|
| Per-item responses | n≥100 for difficulty estimation | Stable IRT parameters |
| Per-skill mastery | n≥50 students with full sequences | Reliable BKT priors |
| Validation holdout | 20% of students | AUC estimation |

## 5.3 Real-Time Data (Production)

| Data Type | Update Frequency | Retention |
|-----------|------------------|-----------|
| Interaction events | Real-time | 90 days hot, 2 years cold |
| Knowledge state | Per interaction | Current state only |
| Mastery map | Per interaction | Historical snapshots (weekly) |
| Review schedule | Daily recalculation | 30-day horizon |

## 6. Learning Type Accommodations (Evidence-Based)

## 6.1 Explicit Position on "Learning Styles"

Per the foundational research (Pashler et al., 2008; Kirschner, 2017):
- **NO VARK-based content routing**: Students are NOT assessed or categorized by VARK preferences
- **NO MI-based curriculum tracks**: Content is NOT filtered by "intelligence type"
- **NO modality matching**: "Visual learners" do NOT receive more visual content

## 6.2 What IS Implemented (Universal Design)

Instead of selective modality matching, the platform provides **multimodal content for all students**, with accommodations based on documented needs (not preference):

| Accommodation | Trigger | Implementation |
|---------------|---------|----------------|
| **Text-to-Speech** | IEP/504 flag OR universal availability | All text content; speed 0.5x-2x; word highlighting |
| **Captions/Transcripts** | Universal + ELL support | All video/audio content |
| **Visual Scaffolding** | ELL, low literacy, or universal | Diagrams, graphic organizers, color coding |
| **Manipulatives/Interactive** | Universal + conceptual learners | Virtual manipulatives for math; interactive simulations |
| **Reduced Visual Load** | IEP/504 (ADHD), high cognitive load | Simplified layouts; chunking; progress indicators |

## 6.3 How Content Format Selection Actually Works

Content format is selected based on:

1. **Cognitive Load Theory** (NOT learning style):
   - Novices → Worked examples (visual + textual)
   - Developing → Faded examples
   - Expert → Problem-solving only

2. **Content Nature**:
   - Fraction concepts → Visual area models + symbolic
   - Phonemic awareness → Audio + visual letter-sound
   - Procedures → Step-by-step with demonstration

3. **Universal Design Principles**:
   - All content has 2+ modalities available
   - Student can switch formats at any time
   - Format history informs (not determines) default presentation

## 6.4 Content Metadata Schema (Format-Related)

```json
{
  "module_id": "uuid",
  "lo_id": "CCSS.MATH.4.NF.A.1",
  "format_variants": [
    {
      "format": "interactive_visual",
      "assets": ["manipulative_canvas", "fraction_bar"],
      "wcag_compliant": true
    },
    {
      "format": "textual_explanation",
      "assets": ["readable_text", "tts_enabled"],
      "wcag_compliant": true
    },
    {
      "format": "worked_example_video",
      "assets": ["video_mp4", "captions_vtt"],
      "wcag_compliant": true
    }
  ],
  "default_format": "adaptive",  // System selects based on CLT, not preference
  "format_switching": "always_available"
}
```

## 7. Computational Complexity Analysis

## 7.1 Inference Complexity Breakdown

| Component | Operation | Complexity | Latency (GPU) | Latency (CPU) |
|-----------|-----------|------------|---------------|---------------|
| DKT LSTM forward | Hidden state update | O(h × s) where h=128, s=seq_len | ~5ms | ~25ms |
| BKT update | Bayesian belief update | O(k) where k=skills | <1ms | <1ms |
| Path planning | A* search on DAG | O(E + V log V) | <10ms | <20ms |
| Content selection | Database query | O(1) with index | <5ms | <10ms |
| **TOTAL** | End-to-end | - | **<25ms** | **<60ms** |

*Target: <100ms cumulative; GPU recommended for production*

## 7.2 Training Complexity

| Model | Training Data | Training Time | Hardware |
|-------|--------------|---------------|----------|
| DKT (LSTM) | 1M sequences | 4-8 hours | Single V100 GPU |
| Transformer-KT | 10M sequences | 24-48 hours | 4x A100 GPUs |
| BKT priors | Cohort statistics | Minutes | CPU |

## 7.3 Scalability Projections

| Concurrent Users | QPS | Infrastructure | Latency p95 |
|------------------|-----|----------------|-------------|
| 1,000 | 100 | Single GPU instance | <50ms |
| 10,000 | 1,000 | 3x GPU + load balancer | <75ms |
| 100,000 | 10,000 | 10x GPU + Redis cache | <100ms |
| 1,000,000 | 100,000 | Auto-scaling (50x GPU) + CDN | <150ms |

## 8. Algorithm Fallback and Safety

## 8.1 Graceful Degradation Chain

If primary algorithms fail, the system falls back through:

1. **Primary**: Hybrid DKT+BKT with full personalization
2. **Fallback 1**: BKT only (if DKT service unavailable) - interpretable, less accurate
3. **Fallback 2**: IRT-based ability-matched content - no personalization, grade-appropriate
4. **Fallback 3**: Rule-based curriculum sequence - no adaptation, standards-aligned
5. **Emergency**: Static content delivery - minimal functionality, always available

## 8.2 Teacher Override Capability

Teachers can:
- Force specific content (bypass recommendation)
- Lock difficulty tier for student
- Disable automatic advancement
- Flag algorithmic errors for review

## 8.3 Bias Monitoring

Continuous monitoring for:
- Demographic performance disparities in recommendations
- Unequal advancement rates by subgroup
- Content access patterns that indicate algorithmic bias

Alert threshold: >10% performance differential across protected groups triggers review.

## 9. References

1. Agrawal, K., Athey, S., Kanodia, A., & Palikot, E. (2022). Personalized Recommendations in EdTech: Evidence from a Randomized Controlled Trial. *arXiv preprint*.

2. Ben David, Y., Segal, A., & Gal, Y. (2016). Sequencing educational content in classrooms using Bayesian knowledge tracing. *Proceedings of LAK '16*.

3. Bhattacharjee, I., & Wayllace, C. (2025). Cold Start Problem: An Experimental Study of Knowledge Tracing Models with New Students. *arXiv preprint*.

4. Cao, M., & Carvalho, P.F. (2025). Adaptive Spaced Retrieval Practice in Algebra I: A Classroom-Based Study. *OSF Preprints*.

5. Mai, N.T., Cao, W., & Liu, W. (2025). Interpretable Knowledge Tracing via Transformer-Bayesian Hybrid Networks. *Applied Sciences*, 15(17).

6. Pashler, H., McDaniel, M., Rohrer, D., & Bjork, R. (2008). Learning Styles: Concepts and Evidence. *Psychological Science in the Public Interest*, 9(3), 105-119.

7. Piech, C., et al. (2015). Deep Knowledge Tracing. *Advances in Neural Information Processing Systems*, 28.

8. Wu, Y. (2025). Learning Path Analysis of Optimizing Educational Data Mining Based on Genetic Algorithm. *SHS Web of Conferences*.
