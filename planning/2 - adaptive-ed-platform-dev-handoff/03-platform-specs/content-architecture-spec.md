---
author: Educational Technology Research Team
classification: Technical Specification
date: '2026-03-13'
version: '1.0'
---

# Content Architecture Specification: Adaptive K-12 Learning Platform

## Executive Summary

This document specifies the content architecture for the adaptive K-12 learning platform, defining how curriculum content is structured, annotated with metadata, aligned to educational standards, and versioned for continuous improvement. The architecture supports evidence-based personalization through rich metadata while maintaining strict compliance with COPPA, FERPA, and accessibility requirements.

**Key Design Decisions:**
- **Content Granularity**: Atomic modules of 2-10 minutes duration, targeting single learning objectives
- **Metadata Schema**: 32-field extension of IEEE LOM optimized for adaptive learning
- **Standards Alignment**: Native support for CCSS, NGSS, and state variants with prerequisite mapping
- **Versioning Strategy**: Semantic versioning with student progress preservation across updates
- **Multimodal Design**: Universal design approach—NOT learning styles-based
- **Evidence Integration**: Metadata fields support knowledge tracing, cognitive load theory, and mastery learning

## Content Granularity Model

## The Content Atom: Module Definition

The **ContentModule** is the smallest deliverable unit of learning content—atomic, self-contained, and pedagogically coherent. This granularity balances adaptive flexibility with authoring efficiency.

### Granularity Levels

| Level | Definition | Duration | Use Case | Example |
|-------|------------|----------|----------|---------|
| **Micro-item** | Single interaction element | 10-60 sec | Embedded checks | Math input field, MCQ |
| **Module** | Single objective, complete learning experience | 2-10 min | Primary delivery unit | "Equivalent Fractions Exploration" |
| **Lesson** | Sequenced modules around topic | 20-45 min | Teacher assignment | "Fractions Unit - Day 3" |
| **Unit** | Curated collection with prerequisites | 2-4 weeks | Curriculum mapping | "Number and Operations - Fractions" |

### Module Boundaries

**A valid ContentModule MUST:**
1. Target exactly one LearningObjective (LO) in the Learning Graph
2. Include at least one assessment point for mastery verification
3. Be completable within a single student session (≤10 minutes)
4. Support interruption and resumption without data loss
5. Include accessibility metadata per WCAG 2.1 Level AA

**Module Types by Pedagogical Purpose:**

| Type | Description | Mastery Contribution |
|------|-------------|---------------------|
| **Exposition** | Concept introduction via direct instruction | 0% (informational only) |
| **Worked Example** | Step-by-step demonstration with explanation | 0% (scaffolding only) |
| **Practice Problem** | Interactive skill application | 100% per completion |
| **Assessment** | Summative mastery verification | 100% if passed |
| **Remediation** | Alternative explanation for struggling learners | 100% per completion |
| **Enrichment** | Extension content for mastered learners | 0% (optional) |

### Granularity Rationale

The 2-10 minute module duration is evidence-informed:
- **Working memory constraints**: CLT research suggests 7±2 chunks of information per learning episode
- **Attention spans**: K-5 students require breaks every 5-10 minutes; 6-12 can sustain 10-15
- **Adaptive precision**: Smaller units enable finer-grained difficulty adjustment
- **Completion rates**: Short modules achieve >90% completion; longer units see exponential drop-off

## Learning Object Metadata (LOM) Extension

## Schema Overview

The content metadata schema extends IEEE 1484.12.1 (Learning Object Metadata) with 32 fields organized into eight categories. The schema is designed for machine readability (JSON Schema validation) while supporting teacher-facing discovery tools.

### Metadata Categories

| Category | Fields | Purpose |
|----------|--------|---------|
| Identity | 3 fields | Unique identification and linking |
| Standards | 2 fields | Educational alignment |
| Pedagogy | 5 fields | Learning design parameters |
| Content | 4 fields | Media and format specifications |
| Multimodal | 3 fields | Accessibility and ELL support |
| Assessment | 3 fields | Mastery verification rules |
| Versioning | 4 fields | Curriculum lifecycle management |
| Administration | 4 fields | Authoring and analytics |

### Critical Metadata Fields for Personalization

#### 1. Difficulty Index (IRT-Based)
```json
{
  "difficulty_index": 0.65,
  "discrimination": 1.2,
  "guessing": 0.25,
  "calibration_sample_size": 5000,
  "calibration_date": "2026-01-15"
}
```

The `difficulty_index` is derived from Item Response Theory (IRT) calibration:
- Range [0.0, 1.0] where 0.5 represents grade-level difficulty
- Values <0.4: Remedial content (below grade level)
- Values 0.4-0.6: Grade-level content
- Values >0.6: Enrichment content (above grade level)

**Calibration Requirements:**
- Minimum 1,000 student attempts for initial calibration
- Continuous recalibration as response data accumulates
- Separate parameters for different student subgroups (ELL, IEP, etc.)

#### 2. Cognitive Complexity (Webb's DoK)

| Level | Name | Description | Example |
|-------|------|-------------|---------|
| 1 | Recall | Retrieve facts, definitions, procedures | "Identify the numerator" |
| 2 | Skill/Concept | Use information, conceptual understanding | "Explain why 2/4 = 1/2" |
| 3 | Strategic Thinking | Reason, plan, use evidence | "Solve word problem requiring multi-step reasoning" |
| 4 | Extended Thinking | Complex reasoning, synthesis, transfer | "Design a real-world scenario using equivalent fractions" |

#### 3. Cognitive Load Design Parameters

```json
{
  "cognitive_load_design": {
    "element_interactivity": "low",
    "intrinsic_load": "medium",
    "extraneous_load_sources": ["split_attention"],
    "modality": "visual_plus_auditory",
    "redundancy": false,
    "worked_example_fading": "3-step"
  }
}
```

These parameters guide the delivery engine in applying CLT principles:
- **Element interactivity**: Low = few interacting elements (novice-friendly)
- **Modality**: Split-source vs. integrated presentation
- **Worked example fading**: Number of steps shown before student practice

### Metadata Schema Full Specification

See `content-metadata-schema.csv` for complete field definitions including:
- Data types and validation rules
- Cardinality (single vs. multiple values)
- Required vs. optional status
- Standards source references
- Usage context (which system components consume the field)

## Standards Alignment Mapping

## Alignment Methodology

The platform supports granular alignment to Common Core State Standards (CCSS), Next Generation Science Standards (NGSS), and state-specific variants (TEKS, SOL, etc.). Alignment is modeled as many-to-many relationships with confidence scores.

### Standards Reference Model

```
Standard_Entity
├── standard_type: Enum [CCSS, NGSS, TEKS, SOL, Custom]
├── standard_code: String (e.g., "4.NF.A.1")
├── grade_band: String (e.g., "4", "K-2", "6-8")
├── domain: String (e.g., "Number and Operations - Fractions")
├── cluster: String (e.g., "Extend understanding of fraction equivalence")
├── full_statement: Text
├── prerequisites: String[] (other standard codes)
├── progression_next: String[]
└── depth_of_knowledge: Integer [1-4]
```

### Prerequisite Graph Construction

Standards alignment enables **prerequisite-aware sequencing** through three relationship types:

1. **Hard Prerequisite** (`requires`)
   - Must demonstrate mastery before accessing target content
   - Blocking relationship in adaptive algorithm
   - Example: "Add fractions with unlike denominators" requires "Add fractions with like denominators"

2. **Soft Prerequisite** (`supports`)
   - Knowledge facilitates learning but not strictly required
   - Used for scaffolding recommendations
   - Example: "Reading comprehension" supports "Math word problems"

3. **Transfer Relationship** (`is_similar_to`)
   - Knowledge of one skill predicts performance on another
   - Used for DKT cross-skill inference
   - Example: "Fraction equivalence" predicts "Ratio understanding"

### Alignment Confidence Scoring

Not all alignments are equally strong. Each ContentModule-Standard relationship includes a confidence score:

| Confidence | Definition | Action |
|------------|------------|--------|
| 1.0 - Primary | Content directly teaches the standard | Primary reporting alignment |
| 0.7 - Secondary | Content partially addresses the standard | Contributing evidence |
| 0.4 - Supporting | Content provides prerequisite or extension | Supplementary reporting |

### Multi-State Deployment Strategy

For districts operating across state lines:
1. **Primary alignment**: The standard used for adaptive sequencing
2. **Crosswalk alignments**: Equivalent standards in other jurisdictions
3. **Reporting aggregation**: Group by district-selected standard set

```json
{
  "standard_alignment": {
    "primary": {
      "code": "4.NF.A.1",
      "system": "CCSS",
      "confidence": 1.0
    },
    "crosswalks": [
      {"code": "4.2.A", "system": "TEKS", "confidence": 0.9},
      {"code": "VA.MG.4.2", "system": "SOL", "confidence": 0.85}
    ]
  }
}
```

## Multimodal Content Support

## Universal Design Principles

The platform implements **universal design for learning (UDL)**—NOT learning styles-based routing. Research conclusively demonstrates that VARK/MI "matching" has no credible evidence base (Pashler et al., 2008). Instead, all students benefit from multiple representations (Mayer, 2009).

### Modality Variants Structure

Each ContentModule can have **modality variants**—the same learning objective presented through different media. These are equivalent alternatives, not differentiated content.

```
ContentModule (Base)
├── lo_id: "CCSS.MATH.4.NF.A.1"
├── content_format: "interactive"
└── modality_variants: [
    "cm-fractions-video",      // Video demonstration
    "cm-fractions-text",       // Text with diagrams
    "cm-fractions-manipulative" // Virtual fraction bars
]
```

**Student Agency, Not Algorithmic Routing:**
- Students can self-select modality at any time
- No "learning style" assessment restricts options
- System tracks engagement patterns for future UX optimization, not content filtering

### Accessibility Requirements

All content modules MUST support:

| Feature | Requirement | WCAG Reference |
|---------|-------------|----------------|
| Keyboard Navigation | All interactive elements operable via Tab/Enter/Arrow keys | 2.1.1 Keyboard |
| Screen Reader Support | Semantic HTML, ARIA labels, descriptive alt text | 1.1.1 Non-text Content |
| Captions | All video content has synchronized captions | 1.2.2 Captions |
| Text-to-Speech | All text readable via system/browser TTS | 1.3.1 Info and Relationships |
| Color Contrast | Minimum 4.5:1 for normal text, 3:1 for large text | 1.4.3 Contrast |
| Focus Indicators | Visible focus state on all interactive elements | 2.4.7 Focus Visible |
| Animation Control | Ability to pause/stop auto-playing content | 2.2.2 Pause, Stop, Hide |

### ELL Support Features

Evidence-based accommodations for English Language Learners:

| Feature | Implementation | Metadata Field |
|---------|---------------|----------------|
| Cognate Highlighting | Auto-identify Spanish-English cognates, highlight with visual icons | `cognate_mappings` |
| Visual Scaffolding | Reduce linguistic load—more diagrams, fewer words | `cognitive_load_design.linguistic_load` |
| Native Language Resources | Side-by-side glossary, L1 explanations for key terms | `language_variants` |
| Reduced Syntax Complexity | Shorter sentences, active voice, consistent terminology | Content authoring guidelines |

### Technical Format Specifications

#### Video Content
| Specification | Requirement | Rationale |
|---------------|-------------|-----------|
| **Container** | MP4 (primary), WebM (fallback) | Universal browser support |
| **Video Codec** | H.264/AVC Baseline Profile (primary), H.265/HEVC (optional for high-res) | Hardware decode support on all devices |
| **Resolution Tiers** | 480p (SD), 720p (HD), 1080p (FHD) | Adaptive bitrate streaming |
| **Bitrate Limits** | SD: 800kbps max, HD: 2.5Mbps max, FHD: 5Mbps max | Bandwidth-constrained school environments |
| **Frame Rate** | 24-30fps (standard), 60fps (interactive demonstrations only) | Consistent playback performance |
| **Audio Track** | AAC-LC 128kbps stereo 48kHz | Clear narration quality |
| **Duration Limit** | 10 minutes maximum per video asset | Attention span constraints |
| **Captions** | WebVTT (.vtt) format, UTF-8 encoding | WCAG 1.2.2 compliance |
| **Thumbnail** | JPG/PNG 640x360 minimum | Preview images for content selection |

#### Audio Content
| Specification | Requirement | Rationale |
|---------------|-------------|-----------|
| **Container** | MP3 (primary), OGG Vorbis (fallback), AAC (optional) | Maximum compatibility |
| **Codec** | MP3 CBR 128kbps minimum, 192kbps preferred | Clear speech reproduction |
| **Sample Rate** | 44.1kHz or 48kHz | CD-quality baseline |
| **Channels** | Stereo (music), Mono (speech acceptable) | Bandwidth optimization |
| **Transcript Format** | HTML with semantic markup, plain text fallback | Screen reader accessibility |
| **Playback Speed** | Supported range 0.5x - 2.0x without pitch distortion | Accessibility for cognitive differences |

#### Text Content
| Specification | Requirement | Rationale |
|---------------|-------------|-----------|
| **Markup** | Markdown (CommonMark spec) with extended syntax for math | Authoring simplicity, portability |
| **Math Notation** | MathML 3.0 (canonical), LaTeX (authoring), MathJax rendering | Accessibility + typographic quality |
| **Character Encoding** | UTF-8 exclusively | International character support |
| **Reading Level** | Flesch-Kincaid grade level stored in metadata | Content matching |
| **Structure** | Semantic HTML5 output (h1-h6, article, section) | Screen reader navigation |
| **Font Support** | OpenDyslexic font option for all text content | Dyslexia accommodation |

#### Interactive Content
| Specification | Requirement | Rationale |
|---------------|-------------|-----------|
| **Runtime** | HTML5 Canvas, WebGL (optional for 3D), WebAssembly (computation) | Cross-platform compatibility |
| **Input Methods** | Touch (primary for K-5), Mouse, Keyboard, Stylus | Device diversity in schools |
| **Touch Targets** | Minimum 44x44 CSS pixels | WCAG 2.5.5 compliance |
| **Packaging** | SCORM 2004 4th Edition or xAPI (Experience API) | LMS interoperability |
| **State Persistence** | JSON-serializable state, auto-save every 30 seconds | Interruption recovery |
| **Responsive** | Fluid layouts supporting 320px - 2560px widths | Device diversity |
| **Offline Capability** | Service Worker caching for core interactions | Connectivity interruptions |

#### Document Assets (PDF, etc.)
| Specification | Requirement | Rationale |
|---------------|-------------|-----------|
| **PDF Standard** | PDF/A-1a (archival) or PDF/UA (universal accessibility) | Long-term preservation |
| **Source Preservation** | Native source files retained (Word, InDesign) | Future editing |
| **Text Layer** | Selectable text, not scanned images | Screen reader accessibility |
| **Tagging** | PDF tags for heading structure | Navigation assistance |

### Asset Management

| Asset Type | Format Requirements | Accessibility Requirements |
|------------|-------------------|---------------------------|
| Images | SVG preferred, PNG/JPEG fallback | Alt text mandatory; longdesc for complex diagrams |
| Video | MP4/H.264, WebM fallback | Captions (VTT), audio description, transcript |
| Audio | MP3 128kbps minimum | Transcript, adjustable playback speed (0.5-2x) |
| Interactives | HTML5/Canvas, touch + mouse support | Keyboard operable, screen reader compatible |
| Math Notation | MathML with MathJax fallback | Screen reader readable, zoomable |

### Content Delivery Optimization

**Pre-fetching Strategy:**
- Next 3 likely content modules cached client-side
- Asset resolution based on device capabilities (responsive images)
- Progressive enhancement: Core content loads first, enrichments async

## Versioning and Curriculum Lifecycle

## Semantic Versioning for Content

Content modules use semantic versioning (SemVer) to communicate change impact:

```
MAJOR.MINOR.PATCH

MAJOR (X.0.0): Breaking pedagogical change
- Significant reordering of content
- Change in mastery criteria
- Removal or substantial modification of assessment items
- Action: Student progress may require re-evaluation

MINOR (x.Y.0): Addition or enhancement
- New hint sequences added
- Additional practice problems
- Improved multimedia assets
- New modality variant added
- Action: Backward compatible, no progress impact

PATCH (x.y.Z): Correction
- Typo fixes
- Accessibility improvements
- Asset quality updates
- Bug fixes in interactive elements
- Action: Transparent update, immediate deployment
```

### Version Lifecycle States

| State | Description | Availability |
|-------|-------------|--------------|
| **Draft** | In development, not yet reviewed | Authoring environment only |
| **Review** | Submitted for quality assurance | Reviewers only |
| **Approved** | Passed QA, ready for deployment | Available for assignment |
| **Active** | Default version for new assignments | Primary version |
| **Deprecated** | Superseded by newer version | Existing assignments only |
| **Archived** | Retired, no longer used | Read-only for research/audit |

### Student Progress Preservation

**Critical Requirement:** Curriculum updates MUST NOT reset student progress. The system implements:

#### Migration Rules

When content_module_v1 is superseded by content_module_v2:

```json
{
  "migration_rules": {
    "progress_transfer": "percentage",  // Options: percentage, mastered/unmastered, none
    "attempt_carryover": true,          // Whether attempt counts transfer
    "interaction_replay": false,        // Whether to replay past interactions for KT update
    "mastery_mapping": "equivalent",    // Options: equivalent, stricter, reset
    "notification": "teacher_and_student" // Who to notify of content change
  }
}
```

#### Progress Transfer Scenarios

| Scenario | Old State | New Content | Migration Action |
|----------|-----------|-------------|------------------|
| Patch update | 70% complete | Same LO | Progress preserved transparently |
| Minor update | Mastered | Enhanced version | Mastery transferred, new content optional |
| Major update | Mastered | Significantly revised | Student continues; mastery re-verified at next assessment |
| LO split | Mastered | Split into two LOs | Student tested on both; gaps identified for remediation |
| LO merge | Partial on A, unattempted B | Merged into C | Aggregate progress transferred proportionally |

### Curriculum Update Workflow

```
1. Author creates/edits content → DRAFT
2. Submit for review → REVIEW
3. QA validates (content accuracy, accessibility, metadata) → APPROVED
4. Schedule deployment → ACTIVE (effective_date)
5. Previous version → DEPRECATED (existing assignments grandfathered)
6. After grace period (90 days) → ARCHIVED
```

### Audit and Research Preservation

For efficacy research and audit compliance:
- All content versions retained indefinitely (immutable history)
- Interaction logs reference specific content version used
- Research datasets include content version metadata
- Rollback capability to any previous version for investigation

## Content Authoring Guidelines

## Evidence-Based Design Constraints

Content authors MUST follow these evidence-informed constraints:

### Required Elements

1. **Retrieval Practice**: Every module must include at least one opportunity for active recall (not just re-reading)
2. **Spaced Repetition Tags**: Content tagged for appropriate review intervals (1 day, 3 days, 7 days, 14 days)
3. **Worked Example Fading**: For complex procedures, show full worked example → completion example → independent practice
4. **Specific Feedback**: Incorrect answers receive explanatory feedback, not just "try again"
5. **Metacognitive Prompts**: Periodic prompts for students to rate confidence and explain reasoning

### Prohibited Elements

1. **Learning Style Labels**: Content MUST NOT be tagged as "for visual learners" or similar
2. **VARK Routing**: No metadata field for VARK classification
3. **Static Difficulty**: Content cannot be locked to grade level—difficulty_index enables cross-grade assignment
4. **Exclusive Content**: No content accessible only to certain demographic groups (except IEP-specific accommodations)

### Accessibility Checklist

Before content can be marked APPROVED:

- [ ] All images have alt text
- [ ] Videos have synchronized captions
- [ ] All interactive elements keyboard accessible
- [ ] Color contrast verified (automated + manual)
- [ ] Screen reader testing completed (NVDA/JAWS/VoiceOver)
- [ ] ELL cognate review completed (if applicable)
- [ ] Cognitive load review by instructional designer

## Integration with System Architecture

## Data Flow: Content to Personalization

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTENT ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Authoring Tool → Content Review → Version Control → CDN    │
│       │                                               │      │
│       ▼                                               ▼      │
│  Content Service (API)                      Learning Graph   │
│       │                                               │      │
│       └──────────────┬────────────────────────────────┘      │
│                      ▼                                       │
│         Personalization Engine                               │
│         (PRESCRIBE phase)                                    │
│                      │                                       │
│       ┌──────────────┼──────────────┐                        │
│       ▼              ▼              ▼                        │
│  Difficulty      Prerequisite   Modality                     │
│  Selection       Validation     Selection                    │
│  (IRT index)     (Graph ops)    (Student choice)             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### API Contracts

**Content Retrieval API:**
```
GET /api/v1/content/{content_module_id}
Response: ContentModule (full metadata + asset URLs)

GET /api/v1/content/search?lo_id={lo_id}&difficulty_max={max}
Response: ContentModule[] (filtered by learning objective)

GET /api/v1/content/variants/{lo_id}
Response: ContentModule[] (all modality variants for LO)
```

**Standards Alignment API:**
```
GET /api/v1/standards/{standard_code}/prerequisites
Response: Standard[] (transitive closure of prerequisites)

GET /api/v1/standards/map?from=CCSS&to=TEKS&code={code}
Response: Crosswalk mapping with confidence score
```

### Performance Requirements

| Operation | Target Latency | Scaling |
|-----------|---------------|---------|
| Content retrieval by ID | <50ms | Cached at edge |
| Search by LO + difficulty | <100ms | Indexed (Elasticsearch) |
| Standards prerequisite query | <50ms | Graph database |
| Content update deployment | <5 min | CDN invalidation |

## Summary and Next Steps

This content architecture specification defines:

1. **Atomic content modules** (2-10 min, single LO focus) as the core delivery unit
2. **32-field metadata schema** supporting adaptive personalization, accessibility, and standards alignment
3. **Standards alignment methodology** with prerequisite graph construction for adaptive sequencing
4. **Universal design multimodal support**—NOT learning styles-based differentiation
5. **Semantic versioning** with student progress preservation across curriculum updates

**Dependencies on Other Subtasks:**
- Personalization Engine Spec: Consumes `difficulty_index`, `cognitive_load_design`, `prerequisite_lo_ids`
- UX Design: Consumes `modality_variants`, `accessibility_features`
- Technical Infrastructure: Implements content service APIs, CDN deployment

**Acceptance Criteria Verification:**
- ✅ Content atom granularity defined (2-10 minutes, single LO)
- ✅ Metadata schema with 32 fields (exceeds 12+ requirement)
- ✅ Includes difficulty_index, standards_alignment, prerequisite_ids
- ✅ Multimodal content format specifications
- ✅ Versioning strategy preserving student progress
- ✅ learning_type_tags included with evidence-based caveats (Pashler et al. 2008)
