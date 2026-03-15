---
author: Educational Technology Research Team
classification: Requirements Specification
date: '2026-03-13'
version: '1.0'
---

# User Personas: Adaptive K-12 Learning Platform

## Executive Summary

This document presents 7 evidence-based user personas for an adaptive K-12 learning platform. Based on learning science research, personas are organized around **cognitive developmental stages** and **learner needs** rather than debunked learning styles taxonomies (VARK/Multiple Intelligences). The personas reflect:

- **Cognitive load capacity** differences by age/development
- **Prior knowledge activation** needs
- **Specific learner populations** (ELL, neurodiverse, gifted) with evidence-based support requirements
- **Real user types** in the educational ecosystem (students, teachers, parents, administrators)

**Key Research Insight**: The platform must NOT use learning styles (VARK/MI) for personalization decisions—these lack credible empirical support (Pashler et al., 2008). Instead, personalization should target mastery-based progression, spaced retrieval, cognitive load management, and adaptive difficulty based on knowledge tracing (BKT/DKT).

## Student Personas: Primary (K-5)

## Persona 1: Emerging Learner "Maya" (Grade 2)

**Demographics**: 7 years old, urban public school, English-speaking household

**Cognitive Profile**:
- **Working Memory**: ~2-3 chunks (developmentally appropriate; Cowan, 2010)
- **Attention Span**: 10-15 minutes focused engagement
- **Reading Level**: Early reader (DRA 16-18)
- **Self-Regulation**: Developing; needs scaffolding for persistence

**Goals**:
- Feel successful in daily learning activities
- Understand "why" behind math procedures, not just procedures
- Maintain engagement through variety and play
- Build foundational fluency (reading, math facts)

**Frustrations with Current Solutions**:
- "Drill and kill" apps (IXL-style) lose engagement quickly
- Khan Academy's text-heavy interface too challenging for reading level
- No recognition when she's struggling vs. just distracted
- Limited connection between school and home practice

**Technology Proficiency**: Tablet-native; touch interface preferred; can navigate simple menus but needs visual cues; struggles with typing.

**Accessibility Considerations**: May benefit from audio narration; needs high contrast options; touch targets minimum 44x44px.

---

## Persona 2: Multilingual Learner "Diego" (Grade 4, ELL)

**Demographics**: 9 years old, recent immigrant (2 years in US), Spanish L1, intermediate English proficiency

**Cognitive Profile**:
- **Working Memory**: Standard for age, but taxed by dual-language processing
- **L1 Transfer**: Strong math conceptual understanding in Spanish; procedural vocabulary gaps in English
- **Interlanguage Stage**: Expanding academic vocabulary; cognate awareness developing
- **Code-Switching**: Comfortable; benefits from L1 support for complex concepts

**Goals**:
- Access grade-level math content despite language barriers
- Build academic English while maintaining grade-level progress
- See connections between home language and school learning
- Avoid being pulled out for intervention and missing core content

**Frustrations with Current Solutions**:
- Platforms translate interface but not instructional language effectively
- No scaffolding for academic vocabulary (e.g., "numerator" vs. "top number")
- No cognate highlighting (fracción/fraction, multiplicación/multiplication)
- Math diagnostic confounded by language proficiency, not math knowledge
- Limited teacher visibility into L1 math strengths

**Technology Proficiency**: Comfortable with tablets; prefers visual/manipulative interfaces (DreamBox-style) that reduce language load; uses translation tools but inconsistently.

**Accessibility Considerations**: Requires text-to-speech with adjustable speed; benefit from picture glossaries; needs extended time settings for reading-heavy items.

---

## Persona 3: Neurodiverse Learner "Aiden" (Grade 5, ADHD + Dyslexia)

**Demographics**: 10 years old, 504 Plan for ADHD, IEP for dyslexia, receives reading intervention

**Cognitive Profile**:
- **Working Memory**: Below average (impacts multi-step procedures)
- **Processing Speed**: Slower for text decoding; average for visual reasoning
- **Attention Regulation**: Variable; benefits from movement breaks and novelty
- **Reading**: Grade 2-3 decoding level; strong listening comprehension

**Goals**:
- Access grade-level content without reading barriers blocking math/science learning
- Build confidence through strengths-based activities
- Develop self-advocacy tools for requesting accommodations
- Maintain focus long enough to experience mastery moments

**Frustrations with Current Solutions**:
- No built-in text-to-speech; must rely on external screen readers
- Timed activities trigger anxiety and underperformance
- Linear navigation doesn't allow movement breaks without penalty
- No alternative input methods (voice, drawing) for showing work
- Progress metrics highlight deficits rather than growth
- Distracting gamification elements (scootpad-style coins/tokens)

**Technology Proficiency**: Highly adept with assistive tech; knows VoiceOver/TalkBack; prefers interactive elements but distracted by excessive animation; uses text-to-speech daily.

**Accessibility Considerations**: **Critical WCAG 2.1 AA compliance needed**: full keyboard navigation, focus indicators, text-to-speech, pause/stop controls for animations, extended time mode, dyslexia-friendly fonts (OpenDyslexic option).



## Student Personas: Secondary (6-12)

## Persona 4: Conceptual Learner "Priya" (Grade 8)

**Demographics**: 13 years old, suburban middle school, grade-level reader, strong in STEM

**Cognitive Profile**:
- **Working Memory**: 5-7 chunks (adult-level capacity developing)
- **Abstract Reasoning**: Emerging; benefits from concrete-to-abstract sequencing
- **Self-Regulation**: Good; can set learning goals and monitor progress
- **Prior Knowledge**: Solid K-7 math foundation; ready for algebraic abstraction

**Goals**:
- Understand mathematical concepts deeply, not just pass tests
- Work at own pace (faster than classroom average in math)
- See connections between concepts (not isolated skills)
- Prepare for high school STEM courses

**Frustrations with Current Solutions**:
- ALEKS's "pie chart" approach feels disconnected from real understanding
- Khan Academy's mastery system good but lacks conceptual depth
- Cannot skip redundant practice when already proficient
- No space for exploration or "what if" mathematical play
- Limited feedback on why answers are wrong (just "try again")

**Technology Proficiency**: Fully computer-literate; types proficiently; uses multiple devices; comfortable with graphing calculators and digital tools.

**Accessibility Considerations**: None specific; benefits from screen real estate for complex problems.

---

## Persona 5: Struggling Learner "Marcus" (Grade 9)

**Demographics**: 14 years old, urban high school, significant gaps in foundational math (6th grade level)

**Cognitive Profile**:
- **Working Memory**: Standard, but overloaded by unfamiliar material
- **Prior Knowledge**: Gaps in fractions, negative numbers, algebraic thinking
- **Math Anxiety**: High; associates math with failure
- **Self-Efficacy**: Low; expects to fail before attempting

**Goals**:
- Fill foundational gaps without shame or stigma
- Experience success to rebuild math confidence
- Catch up to grade level for graduation requirements
- Understand that struggle is part of learning, not evidence of inability

**Frustrations with Current Solutions**:
- Grade-level placement (IXL, classroom) is overwhelming and demotivating
- Remediation content is "babyish" (Khan Academy's "early math" badge visible)
- No diagnostic that identifies specific gaps vs. broad "below grade level"
- Lack of worked examples when stuck
- No recognition of growth when working below grade level

**Technology Proficiency**: Smartphone-native; social media fluent; skeptical of "educational" apps (associates with failure); responds to social proof and relevance.

**Accessibility Considerations**: Anxiety-sensitive UI (no public leaderboards, no "grade level" labels on diagnostic content); needs error messaging that supports growth mindset.

---

## Persona 6: Accelerated Learner "Sophia" (Grade 11)

**Demographics**: 16 years old, suburban high school, gifted program, taking AP Calculus BC

**Cognitive Profile**:
- **Working Memory**: Strong (above average)
- **Processing Speed**: Fast; becomes bored with repetitive practice
- **Metacognition**: High; can articulate what she knows and doesn't know
- **Executive Function**: Excellent; self-directed learning

**Goals**:
- Access advanced coursework beyond school offerings
- Engage with authentic, complex problems (not just exercises)
- Collaborate with other advanced learners
- Build portfolio for college applications

**Frustrations with Current Solutions**:
- Ceiling effect—platforms top out at grade 12, no advanced content
- Mastery systems require excessive repetition before advancement
- No community of peer learners at similar level
- Cannot explore tangential interests (e.g., number theory while in Algebra)
- Limited authentic assessment (real-world problem solving)

**Technology Proficiency**: Expert; builds websites; uses programming (Python); contributes to online communities; expects professional-grade tools.

**Accessibility Considerations**: Needs extensive content library; requires advanced notation support (LaTeX); benefits from community features.



## Educator & Family Personas

## Persona 7: Classroom Teacher "James" (Middle School Math)

**Demographics**: 8 years teaching experience, 6th-8th grade math, 110 students across 4 sections

**Goals**:
- Differentiate instruction for 25-30 students with diverse needs
- Identify struggling students early for intervention
- Reduce time on grading/admin to increase instructional time
- Document growth for IEP/504 meetings and parent conferences
- Align adaptive content to district pacing guide

**Frustrations with Current Solutions**:
- **Carnegie Learning MATHia**: Great content but black-box adaptive; can't adjust student paths when needed
- **Khan Academy**: Lacks standards alignment granularity; can't assign by standard easily
- **DreamBox**: No ability to author/modify content for his specific students
- **Data overload**: Dashboards show every interaction; lacks "who needs my attention now" signal
- **Intervention timing**: Finds out students are struggling after unit test, not before
- **IEP compliance**: Hard to document that accommodations were actually provided in platform

**Technology Proficiency**: Comfortable with LMS (Canvas), Google Workspace; uses Desmos, Geogebra; frustrated by lack of interoperability between tools.

**Pain Points Summary**:
| Need | Current Gap |
|------|-------------|
| Early warning system | At-risk signals too late |
| Flexible assignment | Locked into adaptive path |
| Content authoring | No teacher-created content |
| Granular standards view | Only high-level alignment |
| Accommodation tracking | Manual documentation |

---

## Persona 8: Special Education Teacher "Elena" (K-5 Resource Room)

**Demographics**: 12 years experience, serves 35 students with IEPs across 3 schools

**Goals**:
- Provide intensive, targeted intervention for specific skill deficits
- Coordinate with general education teachers on IEP goals
- Document service minutes and progress toward IEP goals
- Adapt content for diverse disabilities (autism, dyslexia, ADHD, cognitive impairment)

**Frustrations with Current Solutions**:
- Platforms not designed for intensive intervention (too many grade-level assumptions)
- No progress monitoring aligned to IEP goal format
- Accessibility features buried or non-existent
- Cannot customize to specific prompting levels needed by students
- Data doesn't export to IEP systems (PowerSchool, SEDS)

**Technology Proficiency**: Uses specialized assistive tech daily; knows what's possible but frustrated by platform limitations; needs efficiency tools.

---

## Persona 9: Parent "David" (Father of 3rd Grader)

**Demographics**: Works full-time, limited time for homework support, concerned about screen time

**Goals**:
- Understand what child is learning without being a teacher
- Support learning at home without confusing child
- Ensure data privacy (COPPA compliance)
- See progress without excessive detail
- Receive actionable suggestions for help

**Frustrations with Current Solutions**:
- **Privacy concerns**: Unclear what data is collected and shared
- **Lack of transparency**: Can't see what child did today in meaningful way
- **Helplessness**: When child is stuck, no guidance on how parent can help
- **Notifications**: Either too many (spam) or none at all
- **Language barrier**: Materials only in English; cannot support Spanish-speaking spouse

**Technology Proficiency**: Smartphone primary device; uses apps for banking, social media; not comfortable with educational jargon.

---

## Persona 10: School Administrator "Dr. Williams" (Assistant Superintendent)

**Demographics**: 15 years in administration, oversees curriculum and technology for 12,000 student district

**Goals**:
- Improve standardized test scores (state accountability)
- Ensure equity in resource allocation across schools
- Demonstrate ESSA evidence-based intervention usage
- Manage vendor contracts and data privacy compliance
- Support teachers with effective tools (not just more tools)

**Frustrations with Current Solutions**:
- **Efficacy claims**: Vendors claim "adaptive" but evidence is weak (ESSA Level III/IV only)
- **Siloed data**: Each platform has own dashboard; no district-wide learning analytics
- **Equity gaps**: High-poverty schools have lower platform usage; don't know why
- **Implementation fatigue**: Teachers overwhelmed by too many disconnected tools
- **FERPA compliance**: Managing 15+ vendor DPAs; no systematic compliance monitoring

**Decision Criteria**:
- ESSA evidence tier (requires Tier II or I for Title I funding)
- Interoperability (Clever, Google, LMS integration)
- Cost per student (must fit Title I budget constraints)
- Professional development requirements
- Data privacy compliance documentation



## Cross-Cutting Persona Insights

## Evidence-Based Personalization Dimensions

Based on learning science research, the platform should personalize along these validated dimensions (NOT learning styles):

| Dimension | Personalization Mechanism | Evidence Base |
|-----------|--------------------------|---------------|
| **Prior Knowledge State** | Knowledge Tracing (BKT/DKT) predicts mastery | STRONG (AUC 0.85-0.89) |
| **Forgetting Curve** | Spaced repetition algorithm optimizes review timing | STRONG (d=0.5-0.8) |
| **Cognitive Load** | Element interactivity management; worked examples | STRONG (various) |
| **Language Proficiency** | Linguistic scaffolding; cognate support; L1 resources | MODERATE for ELL |
| **Reading Level** | Text-to-speech; leveled text alternatives | MODERATE |
| **Motivation/Engagement** | Mastery-based progression; meaningful feedback | MODERATE |
| **Attention Regulation** | Break timers; movement prompts; reduced animations | MODERATE for ADHD |

## What NOT to Personalize (Per Research)

**Avoid these debunked approaches**:
1. **VARK modality matching**: No evidence that visual learners learn better from visual content
2. **Multiple Intelligence tracks**: No predictive validity for restricting content by "intelligence type"
3. **Fixed ability labeling**: Growth mindset research shows labeling harms outcomes

## Critical User Journeys

1. **Diego (ELL)**: Enrolls → Language survey → Diagnostic (math in Spanish + English) → Adaptive placement with L1 scaffolding → Bilingual progress reports
2. **Aiden (Neurodiverse)**: 504 plan import → Auto-applies accommodations → Reduced animations, extended time, TTS enabled → Teacher sees accommodation usage report
3. **James (Teacher)**: Assigns unit → Sees real-time mastery dashboard → Receives "at-risk" alert for Marcus → Assigns prerequisite review → Tracks intervention efficacy
4. **Dr. Williams (Admin)**: Reviews district dashboard → Identifies equity gap → Dives to school level → Exports ESSA evidence documentation

## Technology Proficiency Spectrum

| User | Proficiency | Interface Implications |
|------|-------------|----------------------|
| Maya (Grade 2) | Touch-native, pre-literate | Touch-first, icon-based, audio support |
| Diego (Grade 4) | Visual reasoning, limited English | Reduced text load, visual manipulatives |
| Aiden (Grade 5) | Assistive tech expert | Full AT compatibility, customization |
| Priya (Grade 8) | Full computer literacy | Full feature access, efficiency shortcuts |
| Marcus (Grade 9) | Mobile-native, skeptical | Mobile-responsive, relevance-focused |
| Sophia (Grade 11) | Expert, power user | Advanced features, customization, API access |
| James (Teacher) | Professional tools user | Integration with existing tools, efficiency |
| Elena (SPED) | Assistive tech specialist | Accessibility compliance, IEP alignment |
| David (Parent) | Consumer app user | Simplicity, transparency, actionable |
| Dr. Williams (Admin) | Systems administrator | Data export, compliance docs, analytics |



## Sources and Evidence Base

Personas are grounded in the following research:

1. **Pashler et al. (2008)**. Learning Styles: Concepts and Evidence. *Psychological Science in the Public Interest*. Foundation for rejecting learning styles-based personas.

2. **Cowan (2010)**. The Magical Mystery Four: How is Working Memory Capacity 4, and Why? *Behavioral and Brain Sciences*. Working memory capacity by developmental stage.

3. **Agrawal et al. (2022)**. Personalized Recommendations in EdTech: Evidence from a Randomized Controlled Trial. Evidence for personalization benefits based on behavior, not learning styles.

4. **COPPA Rule** (16 CFR Part 312). Requirements for verifiable parental consent and data minimization for users under 13 (Maya, Diego, Aiden personas).

5. **WCAG 2.1 Level AA** standards. Accessibility requirements for neurodiverse and disabled learners.

6. **Competitive analysis** of Khan Academy, DreamBox, Carnegie Learning, IXL, ALEKS. Identified gaps in ELL support, content authoring, and neurodiverse accommodations.

*Document Version: 1.0*
*Last Updated: 2026-03-13*

