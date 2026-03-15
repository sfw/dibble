---
author: Adaptive Learning Platform Research Team
classification: Research & Development
date: '2026-03-13'
version: '1.0'
---

# Success Metrics Framework: Adaptive Learning Platform Efficacy Measurement

## Executive Summary

This framework defines the measurement strategy for validating the adaptive learning platform's educational efficacy through rigorous quantitative and qualitative metrics. The approach combines learning outcome measures, engagement indicators, and system performance benchmarks, organized around a structured A/B testing methodology designed to meet ESSA Tier 2 (Moderate) or Tier 3 (Promising) evidence standards.

**Key Principles:**
- **Evidence-aligned**: Metrics map to validated learning science principles (mastery learning, spaced repetition, cognitive load optimization)
- **Actionable**: Each metric has clear thresholds for go/no-go decisions at phase gates
- **Privacy-preserving**: All student-level data remains within FERPA-compliant boundaries; aggregated reporting only
- **Multi-stakeholder**: Captures value for students, teachers, parents, and administrators

## Primary Efficacy Outcomes (Learning Impact)

## Academic Achievement Metrics

| Metric | Definition | Measurement Tool | Target (Pilot) | Target (Scale) |
|--------|------------|------------------|----------------|----------------|
| **Standardized Gain Score** | Pre/post assessment normalized gain: (post-pre)/(100-pre) | Platform-embedded assessments aligned to CCSS/NGSS | ≥0.4 (medium effect) | ≥0.6 (large effect) |
| **Learning Velocity** | Skills mastered per instructional hour | Platform interaction logs | 1.2x control group | 1.5x control group |
| **Retention Rate (30-day)** | Proportion of skills retained after 30 days without practice | Delayed post-test | ≥80% | ≥85% |
| **Prerequisite Mastery Transfer** | Success rate on advanced skills after mastering prerequisites | Learning graph traversal logs | ≥75% | ≥80% |

## Competency-Based Progress Metrics

| Metric | Definition | Calculation | Target |
|--------|------------|-------------|--------|
| **Mastery Achievement Rate** | % of assigned learning objectives reaching mastery threshold | mastered / assigned × 100 | ≥70% |
| **Time-to-Mastery** | Median interactions required to reach mastery threshold | Per learning objective | ≤5 attempts |
| **Struggle Recovery Rate** | % of students recovering from 'struggling' status within 3 sessions | recovered / struggled × 100 | ≥60% |
| **Completion Rate** | % of assigned content modules completed | completed / assigned × 100 | ≥85% |

## Comparative Effectiveness (A/B Testing)

### Primary Hypothesis
Students using the adaptive platform will demonstrate significantly greater learning gains (measured by standardized gain scores) compared to students receiving traditional instruction or non-adaptive digital content.

### Study Design
- **Design**: Cluster randomized controlled trial (RCT) at classroom level
- **Duration**: 12 weeks minimum (1 semester)
- **Sample Size**: 200 students per arm (treatment, control A [traditional], control B [non-adaptive digital])
- **Power**: 80% power to detect d=0.4 effect size at α=0.05
- **Randomization**: Stratified by grade, prior achievement, school SES

### Outcome Measures
1. **Primary**: Standardized gain score on curriculum-aligned assessment
2. **Secondary**: State standardized test scores (if available within study window)
3. **Secondary**: Teacher-rated student engagement scale (5-point Likert)

## Engagement & Motivation Metrics

## Behavioral Engagement

| Metric | Data Source | Target | Leading Indicator For |
|--------|-------------|--------|----------------------|
| **Session Completion Rate** | Platform logs | ≥90% | Content appropriateness |
| **Average Session Duration** | Platform logs | 15-25 min | Sustained attention |
| **Weekly Active Users (WAU)** | Platform logs | ≥85% of enrolled | Habit formation |
| **Return Rate (Next Day)** | Platform logs | ≥70% | Motivation |
| **Help-Seeking Behavior** | Help button clicks | 1-3 per module | Self-regulated learning |

## Emotional Engagement

| Metric | Measurement Method | Target | Notes |
|--------|-------------------|--------|-------|
| **Net Promoter Score (Student)** | In-app micro-survey (1-question) | ≥+20 | Monthly sampling |
| **Enjoyment Rating** | Post-session sentiment (emoji scale) | ≥3.5/5 | Aggregate only |
| **Frustration Incidents** | Detected rage-quit patterns | <5% of sessions | Flag for review |
| **Goal-Setting Participation** | % students setting weekly goals | ≥50% | Agency indicator |

## Teacher & Administrator Engagement

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Teacher Login Frequency** | ≥3x/week | Platform analytics |
| **Intervention Response Time** | <48 hours | At-risk alert → action |
| **Override Rate** | 5-15% | Balance of trust vs. disagreement |
| **Administrator Dashboard Usage** | ≥1x/week | Feature analytics |
| **Parent Portal Activation** | ≥60% of families | Registration tracking |

## System Performance Metrics

## Technical Performance SLA

| Metric | Target | Measurement | Alert Threshold |
|--------|--------|-------------|-----------------|
| **Recommendation Latency (p95)** | <200ms | APM instrumentation | >300ms |
| **Page Load Time (p95)** | <2s | Real user monitoring | >3s |
| **Uptime** | ≥99.9% | Synthetic monitoring | <99.5% |
| **Error Rate** | <0.1% | Application logs | >0.5% |
| **Concurrent User Capacity** | 10,000+ | Load testing | <8,000 |

## Adaptive System Quality

| Metric | Definition | Target | Diagnostic Action |
|--------|------------|--------|-----------------|
| **Prediction Accuracy (AUC)** | DKT model discrimination | ≥0.85 | Retrain if <0.80 |
| **Calibration Error** | Predicted vs. actual accuracy | <0.05 | Adjust confidence thresholds |
| **Cold-Start Convergence** | Accuracy at N interactions | ≥0.75 at n=20 | Improve priors |
| **Recommendation Diversity** | % unique content in top-5 | ≥60% | Prevent filter bubbles |
| **Spaced Repetition Precision** | Due items presented on schedule | ≥95% | Review queue logic |

## Data Quality & Compliance

| Metric | Target | Verification |
|--------|--------|--------------|
| **Data Completeness** | ≥98% | Row-level validation |
| **PII Handling Compliance** | 100% | Automated audit scans |
| **Parental Consent Coverage** | 100% of <13 users | Registration workflow |
| **Accessibility Compliance** | WCAG 2.1 AA | Automated + manual audit |

## A/B Testing Methodology

## Experiment Hierarchy

### Level 1: Core Efficacy RCT (Semester-Long)
**Purpose**: Validate overall platform effectiveness vs. control

| Element | Specification |
|---------|-------------|
| **Treatment** | Full adaptive platform with DKT+BKT personalization |
| **Control A** | Traditional classroom instruction (business as usual) |
| **Control B** | Non-adaptive digital practice (same content, linear sequence) |
| **Randomization** | Classroom-level cluster randomization |
| **Blinding** | Open-label (blinding impossible); assessors blinded for standardized testing |
| **Primary Outcome** | Standardized gain score (pre/post) |
| **Analysis** | Intent-to-treat; mixed-effects models accounting for clustering |

### Level 2: Feature-Specific Experiments (2-4 weeks)
**Purpose**: Optimize specific adaptive algorithms and UX elements

| Experiment | Treatment Variation | Metric |
|------------|---------------------|--------|
| **Spaced Repetition Timing** | Short (1 day) vs. optimal (algorithmic) intervals | 30-day retention |
| **Feedback Timing** | Immediate vs. delayed (end of session) | Learning gains |
| **Modality Presentation** | Student choice vs. algorithmic suggestion | Engagement + mastery |
| **Mastery Threshold** | 3 correct vs. 5 correct consecutive | Time-to-mastery vs. retention |
| **Difficulty Calibration** | Aggressive (70% target) vs. conservative (80% target) | Persistence vs. frustration |

### Level 3: Micro-Experiments (In-session)
**Purpose**: Optimize UI/UX elements in real-time

| Experiment | Variations | Sample Size |
|------------|------------|-------------|
| **Hint Presentation** | Text vs. visual vs. worked example | 10,000 interactions |
| **Progress Visualization** | Bar vs. path vs. percentage | 5,000 users |
| **Encouragement Messages** | Growth mindset vs. neutral phrasing | 8,000 sessions |

## Statistical Framework

### Power Analysis
- **Minimum detectable effect (MDE)**: d = 0.3 (small-medium)
- **Intraclass correlation (ICC)**: ρ = 0.10 (accounting for classroom clustering)
- **Required sample**: 150 students per arm (adjusted for clustering)
- **Target sample**: 200 per arm (accounting for 20% attrition)

### Analysis Plan
1. **Descriptive statistics**: Group means, standard deviations, confidence intervals
2. **Primary analysis**: Mixed-effects linear regression with classroom random effect
3. **Sensitivity analyses**: Per-protocol, subgroup (grade, prior achievement)
4. **Multiple comparison correction**: Bonferroni for secondary outcomes

### Early Stopping Rules
- **Futility**: <20% probability of achieving primary outcome at interim analysis (n=100/arm)
- **Efficacy**: >95% probability of success AND clinically meaningful effect (d>0.5)
- **Harm**: Significantly worse outcomes in treatment (d<-0.2) at any point

## Data Collection & Reporting Cadence

## Automated Data Collection

| Data Type | Frequency | Storage | Retention |
|-----------|-----------|---------|-----------|
| **Interaction Events** | Real-time | Event store (6 months hot) | 7 years (FERPA) |
| **Knowledge State Snapshots** | Daily | Time-series database | 7 years |
| **Assessment Results** | Per-assessment | Relational database | 7 years |
| **Engagement Metrics** | Aggregated daily | Analytics warehouse | 7 years |
| **A/B Experiment Assignments** | Per-session | Experiment platform | 3 years |

## Reporting Cadence

| Report | Audience | Frequency | Content |
|--------|----------|-----------|---------|
| **Executive Dashboard** | Leadership | Real-time | KPIs, red flags, trends |
| **Efficacy Snapshot** | Research team | Weekly | A/B test progress, effect sizes |
| **Pilot Status Report** | All stakeholders | Bi-weekly | Enrollment, engagement, issues |
| **Interim Analysis** | IRB, leadership | Month 6 (pilot) | Safety, efficacy, continuation |
| **Final Evaluation Report** | Public, investors | Post-pilot | Full results, ESSA evidence level |

## Privacy-Preserving Analytics

All reporting follows these constraints:
- **Minimum group size**: n≥10 for any reported statistic
- **No individual identification**: Remove all direct and quasi-identifiers
- **Differential privacy**: Add calibrated noise to sensitive metrics (ε=1.0)
- **Role-based access**: Different dashboards for teachers (class-level) vs. researchers (aggregate)

## Go/No-Go Decision Criteria

## Phase Gate Decisions

### MVP Gate (Month 6)
| Criterion | Threshold | Decision |
|-----------|-----------|----------|
| Core features complete | 100% of must-have features | Proceed to pilot recruitment |
| System stability | 99.5% uptime, <0.5% error rate | Proceed |
| Privacy compliance | COPPA/FERPA audit passed | Proceed |
| Prediction accuracy | AUC ≥0.80 on held-out test set | Proceed |

### Pilot Launch Gate (Month 9)
| Criterion | Threshold | Decision |
|-----------|-----------|----------|
| Content coverage | ≥80% of pilot curriculum scope | Launch |
| Teacher training completion | ≥90% of pilot teachers certified | Launch |
| Parental consent | ≥95% coverage for <13 students | Launch |
| Technical readiness | Load tested at 2x projected capacity | Launch |

### Scale Decision Gate (Month 18, post-pilot)
| Criterion | Threshold | Decision |
|-----------|-----------|----------|
| Primary efficacy | Statistically significant positive effect (p<0.05) | Proceed to scale |
| Effect size | d ≥ 0.4 (medium) | Proceed with confidence |
| Engagement | ≥70% weekly active use | Proceed |
| Teacher satisfaction | ≥3.5/5.0 average | Proceed |
| Cost per student | ≤$50/year at 10K student scale | Proceed |
| **Any critical metric missed** | — | **Iterate or pivot** |

## Contingency Triggers

| Trigger | Response |
|---------|----------|
| Safety incident (data breach) | Immediate halt, incident response, regulatory notification |
| Negative efficacy signal (d<0) | Pause enrollment, data safety monitoring board review |
| <50% teacher engagement | Pause, qualitative research, UX iteration |
| Technical failures >1% of sessions | Degrade gracefully, fix-forward or rollback |
| Parent complaints >5% of families | Review consent process, enhance communication |

## Longitudinal Tracking & Follow-Up

## Cohort Retention

| Timeframe | Measurement | Purpose |
|-----------|-------------|---------|
| **Immediate** | Post-session surveys, help-seeking | UX optimization |
| **1 week** | Mastery retention on recent skills | Short-term learning |
| **1 month** | Retention test, engagement trends | Medium-term efficacy |
| **End of semester** | Standardized assessment, teacher survey | Primary efficacy |
| **1 year** | State test scores, next-grade readiness | Long-term transfer |
| **3 years** | Cohort progression, chronic absenteeism | Systemic impact |

## Sustainability Metrics

| Metric | Year 1 Target | Year 3 Target |
|--------|---------------|---------------|
| **Customer Acquisition Cost (CAC)** | <$500/school | <$300/school |
| **Lifetime Value (LTV)** | >$2,000/school | >$5,000/school |
| **LTV:CAC Ratio** | >4:1 | >5:1 |
| **Annual Churn** | <20% | <10% |
| **Net Revenue Retention** | >100% | >120% |
| **Gross Margin** | >60% | >70% |
