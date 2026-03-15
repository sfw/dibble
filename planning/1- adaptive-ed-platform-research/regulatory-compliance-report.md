---
author: Educational Technology Research Team
date: '2025-03-13'
version: '1.0'
---

# Regulatory Compliance Report: K-12 Adaptive Learning Platform

## Executive Summary

This report outlines the regulatory compliance obligations for a K-12 adaptive learning platform operating in the United States. The platform must comply with federal regulations including COPPA (Children's Online Privacy Protection Act), FERPA (Family Educational Rights and Privacy Act), and ADA Title II accessibility requirements (WCAG 2.1 Level AA). Additionally, over 130 state-level student data privacy laws impose further requirements that vary by jurisdiction.

**Key Compliance Priorities:**
1. Privacy-by-design architecture with data minimization principles
2. Verifiable parental consent mechanisms for users under 13 (COPPA)
3. School official agreements for FERPA compliance
4. WCAG 2.1 Level AA accessibility conformance (compliance deadline: April 2026-2027)
5. Multi-state privacy law mapping for deployment scalability

## COPPA Compliance Requirements

## Overview
COPPA (15 U.S.C. §6501-6506) applies to operators of websites and online services directed to children under 13 years of age. For a K-12 adaptive learning platform, COPPA compliance is essential for elementary and middle school deployments.

## Technical Requirements

### 1. Verifiable Parental Consent (VPC)
- **Requirement**: Obtain verifiable parental consent before collecting personal information from children under 13
- **Methods accepted by FTC**:
  - Signed consent form (physical or electronic)
  - Credit or debit card verification
  - Video conference with trained personnel
  - Government-issued ID verification
  - Knowledge-based challenge questions (e.g., 'challenge questions' based on public records)
- **School consent exception**: Schools may provide consent on behalf of parents for educational purposes, but the school must be fully informed about data practices

### 2. Data Minimization
- Collect only information reasonably necessary to provide the service
- Prohibit collection of:
  - Geolocation data (more precise than street-level) without additional consent
  - Persistent identifiers for behavioral advertising
  - Photos, videos, or audio files containing child's image or voice without parental consent

### 3. Privacy Policy Requirements
- Clear, comprehensive, and prominently posted privacy policy
- Must include:
  - Types of personal information collected
  - How information is used
  - Disclosure practices (third parties, service providers)
  - Parental rights (review, delete, refuse further collection)
  - Contact information for privacy inquiries

### 4. Data Security and Retention
- Maintain reasonable procedures to protect confidentiality, security, and integrity of personal information
- Retain personal information only as long as reasonably necessary
- Secure disposal procedures when retention period expires

### 5. Prohibited Practices
- No conditional participation requiring disclosure of more information than necessary
- No selling of children's personal information
- No use of children's personal information for behavioral advertising without explicit parental consent

## Compliance Checklist
- [ ] Implement VPC mechanism for users under 13
- [ ] Create COPPA-compliant privacy policy
- [ ] Establish data minimization protocols
- [ ] Implement data security controls (encryption at rest/transit)
- [ ] Create parental rights portal (access, deletion requests)
- [ ] Document data retention and deletion schedules

## FERPA Compliance Requirements

## Overview
FERPA (20 U.S.C. §1232g; 34 CFR Part 99) protects the privacy of student education records. As a third-party service provider to schools, the platform must operate under FERPA's "school official" exception or obtain written consent.

## Key Definitions

### Education Records
Records that are:
1. Directly related to a student; AND
2. Maintained by an educational agency/institution or by a party acting for the agency/institution

Includes: grades, test scores, attendance, behavioral data, learning analytics, progress data

### Personally Identifiable Information (PII)
- Direct identifiers: name, student ID, biometric records
- Indirect identifiers: date of birth, place of birth, mother's maiden name
- Metadata: interaction data, learning patterns that could identify individual students when combined with other reasonably available information

## School Official Exception Requirements
To qualify as a "school official" under FERPA §99.31(a)(1)(i), the platform must:

1. **Perform institutional service or function** that the school would otherwise use employees to perform
2. **Meet school official criteria** as defined in the school's annual FERPA notification
3. **Be under direct control** of the school/district regarding use and maintenance of education records
4. **Use records only for authorized purposes** and not re-disclose PII without authorization

## Technical Requirements for FERPA Compliance

### 1. Data Protection Agreements (DPA)
- Written contract with each school/district
- Must specify:
  - Data elements collected
  - Purpose of collection
  - Security measures
  - Data use restrictions
  - Subcontractor provisions
  - Data destruction timeline
  - Breach notification procedures

### 2. Direct Control Mechanisms
- Schools must maintain control over data use and maintenance
- Platform cannot unilaterally modify terms of service affecting data use
- Changes must be clearly communicated with explicit documentation

### 3. Data Use Restrictions
- PII may only be used for purposes specified in contract
- Prohibited uses:
  - Targeted advertising to students or parents
  - Creation of student profiles for non-educational purposes
  - Sale of student data
  - Data mining for commercial purposes

### 4. Transparency Requirements
- Contracts should be publicly accessible
- Clear documentation of data elements shared
- Explanation of data use purposes
- Data governance policy publication

### 5. Parental Rights Support
- Parents have right to access child's education records within 45 days of request
- Platform must facilitate seamless access through school/district
- Parents may request amendment of inaccurate records

### 6. Data Security and Destruction
- Comprehensive security plan with checks and controls
- Data breach response procedures (when and how notification issued)
- Data destruction plan with timeline and methodology upon contract completion
- Certification of data destruction

## Compliance Checklist
- [ ] Establish DPA template for school contracts
- [ ] Implement school control mechanisms in architecture
- [ ] Create data inventory mapping all PII elements
- [ ] Develop breach notification procedures
- [ ] Implement data retention and destruction protocols
- [ ] Create parental access facilitation process
- [ ] Document data de-identification methodologies

## Accessibility Requirements (WCAG 2.1 AA)

## Overview
The Department of Justice's April 2024 final rule establishes WCAG 2.1 Level AA as the technical standard for web content and mobile apps provided by state and local governments, including public K-12 schools. Compliance deadlines are:
- **April 24, 2026**: Governments with population ≥50,000
- **April 26, 2027**: Governments with population <50,000 and special district governments

## WCAG 2.1 Level AA Requirements

### Perceivable (Content must be presentable in ways users can perceive)

#### 1. Text Alternatives (1.1)
- **1.1.1 Non-text Content**: All non-text content has text alternative (Level A)
  - Images: descriptive alt text
  - Charts/graphs: data tables or long descriptions
  - Decorative images: empty alt attribute

#### 2. Time-based Media (1.2)
- **1.2.2 Captions (Prerecorded)**: Captions for all prerecorded audio content (Level A)
- **1.2.3 Audio Description or Media Alternative**: Alternative for video content (Level A)
- **1.2.4 Captions (Live)**: Captions for live audio content (Level AA)
- **1.2.5 Audio Description (Prerecorded)**: Audio description for video content (Level AA)

#### 3. Adaptable (1.3)
- **1.3.1 Info and Relationships**: Information structure programmatically determined (Level A)
- **1.3.4 Orientation**: Content not restricted to single display orientation (Level AA)
- **1.3.5 Identify Input Purpose**: Input field purposes programmatically identified (Level AA)

#### 4. Distinguishable (1.4)
- **1.4.3 Contrast (Minimum)**: Text contrast ratio at least 4.5:1 (Level AA)
  - Large text (18pt+ or 14pt+ bold): 3:1 minimum
- **1.4.4 Resize Text**: Text resizable up to 200% without assistive technology (Level AA)
- **1.4.5 Images of Text**: Text used rather than images of text (Level AA)
- **1.4.10 Reflow**: Content can be presented without scrolling in two dimensions (Level AA)
- **1.4.11 Non-text Contrast**: UI components and graphics have 3:1 contrast ratio (Level AA)
- **1.4.12 Text Spacing**: No loss of content when text spacing adjusted (Level AA)
- **1.4.13 Content on Hover/Focus**: Additional content dismissible and hoverable (Level AA)

### Operable (Interface components must be operable)

#### 5. Keyboard Accessible (2.1)
- **2.1.1 Keyboard**: All functionality available via keyboard (Level A)
- **2.1.2 No Keyboard Trap**: Keyboard focus not trapped (Level A)
- **2.1.4 Character Key Shortcuts**: Single-key shortcuts can be turned off or modified (Level AA)

#### 6. Enough Time (2.2)
- **2.2.1 Timing Adjustable**: Users can turn off, adjust, or extend time limits (Level A)
- **2.2.2 Pause, Stop, Hide**: Moving/blinking content can be controlled (Level A)

#### 7. Seizures and Physical Reactions (2.3)
- **2.3.1 Three Flashes or Below**: Nothing flashes more than 3 times per second (Level A)

#### 8. Navigable (2.4)
- **2.4.3 Focus Order**: Focus order preserves meaning and operability (Level A)
- **2.4.4 Link Purpose (In Context)**: Link purpose determinable from link text (Level A)
- **2.4.5 Multiple Ways**: Multiple ways to find pages (Level AA)
- **2.4.6 Headings and Labels**: Descriptive headings and labels (Level AA)
- **2.4.7 Focus Visible**: Keyboard focus indicator visible (Level AA)

#### 9. Input Modalities (2.5)
- **2.5.1 Pointer Gestures**: Complex gestures have single-pointer alternatives (Level AA)
- **2.5.2 Pointer Cancellation**: Down-event activation can be aborted or undone (Level AA)
- **2.5.3 Label in Name**: Visual label matches accessible name (Level AA)
- **2.5.4 Motion Actuation**: Motion-triggered functions have alternative controls (Level AA)

### Understandable (Information and UI operation must be understandable)

#### 10. Readable (3.1)
- **3.1.1 Language of Page**: Default language programmatically determined (Level A)
- **3.1.2 Language of Parts**: Language changes programmatically determined (Level AA)

#### 11. Predictable (3.2)
- **3.2.3 Consistent Navigation**: Navigation consistent across pages (Level AA)
- **3.2.4 Consistent Identification**: Components with same function identified consistently (Level AA)

#### 12. Input Assistance (3.3)
- **3.3.3 Error Suggestion**: Error correction suggestions provided (Level AA)
- **3.3.4 Error Prevention (Legal, Financial, Data)**: Reversible submissions for important data (Level AA)

### Robust (Content must work with current and future technologies)

#### 13. Compatible (4.1)
- **4.1.2 Name, Role, Value**: UI components have name, role, value programmatically determined (Level A)
- **4.1.3 Status Messages**: Status messages announced without moving focus (Level AA)

## Exceptions to WCAG 2.1 AA Requirements
Limited exceptions apply to:
1. Archived web content (pre-compliance date, reference/recordkeeping only)
2. Preexisting conventional electronic documents (pre-compliance date, not actively used)
3. Third-party content posted by non-contracted parties
4. Individualized password-protected documents (water bills, tax bills)
5. Preexisting social media posts

Note: Educational content posted after compliance dates generally does NOT qualify for exceptions.

## Technical Implementation Requirements
- Semantic HTML5 markup
- ARIA labels and roles where HTML semantics insufficient
- Keyboard navigation support for all interactive elements
- Focus management for dynamic content
- Screen reader compatibility testing
- Color contrast validation tools
- Responsive design supporting 200% zoom
- Captions and transcripts for all media

## State-Level Student Data Privacy Laws

## Overview
As of 2024, over 130 state-level student data privacy laws have been enacted across the United States. Many provide protections beyond FERPA and COPPA. Multi-state deployment requires compliance mapping.

## Notable State Laws

### California - SOPIPA (Student Online Personal Information Protection Act)
**Cal. Bus. & Prof. Code §22584-22585**

**Key Prohibitions:**
- Prohibits operators from:
  - Engaging in targeted advertising based on student information
  - Using student information to create profiles for non-educational purposes
  - Selling student personal information
  - Disclosing covered information unless within specific exceptions

**Data Security Requirements:**
- Implement and maintain reasonable security procedures
- Delete covered information within reasonable timeframe upon request

**Definitions:**
- "Operator": Website or online service directed to K-12 purposes with actual knowledge of student use
- "Covered information": Personally identifiable information or materials

### Connecticut
- Requires vendor contracts with specific data protection provisions
- Breach notification requirements (faster than federal timelines)
- Prohibits use of student data for advertising

### Colorado
- Student Data Transparency and Security Act
- Requirements for data sharing agreements
- Public-facing data inventory requirements
- Annual reporting on student data practices

### New York
- Education Law §2-d (2014, amended 2020)
- Requires Parent's Bill of Rights for data privacy and security
- Mandates data security and privacy protections in contracts
- Prohibits selling of student data
- Requirements for third-party contractor data deletion

### Illinois
- Student Online Personal Protection Act
- Similar to SOPIPA with targeted advertising prohibitions

### Multi-State Compliance Strategy
For national deployment, platforms should implement the strictest requirements across all jurisdictions:
1. No targeted advertising using student data
2. No sale of student personal information
3. Comprehensive data security measures
4. Transparent data practices
5. Parent/student rights to data access and deletion
6. Breach notification procedures meeting shortest state timelines

## Compliance Checklist
- [ ] Map target states' specific requirements
- [ ] Implement uniform policy meeting strictest state standards
- [ ] Create state-specific addenda for DPAs where required
- [ ] Establish breach notification procedures meeting all state timelines
- [ ] Document compliance across all jurisdictions

## Critical Data Flows and Regulatory Mapping

## Data Flow 1: Student Registration and Account Creation

**Description**: Collection of student identity information (name, grade, school, student ID) during account setup

**Regulatory Requirements:**
| Regulation | Requirement |
|------------|-------------|
| COPPA | Verifiable parental consent for users under 13; privacy policy disclosure |
| FERPA | Data collection must be under school official agreement; specify data elements in contract |
| State Laws | SOPIPA and equivalents: no data collection beyond educational necessity |
| WCAG 2.1 AA | Form accessibility: labels, error identification, keyboard navigation |

**Technical Implementation:**
- Age-gating mechanism to trigger COPPA workflow
- Multi-step consent process (school or parent)
- Form validation with accessible error messages
- Data element documentation in DPA

---

## Data Flow 2: Learning Analytics and Progress Tracking

**Description**: Collection and analysis of student performance data, interaction patterns, learning path data

**Regulatory Requirements:**
| Regulation | Requirement |
|------------|-------------|
| COPPA | Persistent identifiers permitted only for operational purposes; no behavioral advertising |
| FERPA | Performance data = education records; subject to direct control and use restrictions |
| State Laws | Prohibited uses include targeted advertising and commercial profiling |
| WCAG 2.1 AA | Analytics dashboards must be screen-reader accessible; proper color contrast |

**Technical Implementation:**
- Data minimization: collect only analytics necessary for adaptive learning
- Access controls: role-based permissions (teachers see their students only)
- Audit logging: track data access for FERPA compliance
- De-identification protocols for research/aggregate use

---

## Data Flow 3: Data Sharing and Third-Party Integration

**Description**: Sharing student data with integrated services (LMS, SIS, assessment platforms)

**Regulatory Requirements:**
| Regulation | Requirement |
|------------|-------------|
| COPPA | Third parties must provide service to operator; maintain confidentiality |
| FERPA | Re-disclosure only with school authorization; third party must be school official or under direct control |
| State Laws | Contractual requirements for subcontractor data protection |
| WCAG 2.1 AA | Integration interfaces must maintain accessibility standards |

**Technical Implementation:**
- Subcontractor vetting and DPA requirements
- API security: OAuth 2.0, scoped tokens, encryption in transit
- Data sharing audit trails
- Parental notification of integrations in privacy policy

## Common Core State Standards Alignment Requirements

## Standards Structure Overview

### Mathematics
**Domains by Grade Band:**
- K-5: Counting & Cardinality, Operations & Algebraic Thinking, Number & Operations in Base Ten, Number & Operations—Fractions, Measurement & Data, Geometry
- 6-8: Ratios & Proportional Relationships, The Number System, Expressions & Equations, Functions, Geometry, Statistics & Probability
- 9-12: Number & Quantity, Algebra, Functions, Modeling, Geometry, Statistics & Probability

**Standards Organization:**
- Standards organized by grade level
- Each standard has unique identifier (e.g., CCSS.MATH.CONTENT.3.NF.A.1)
- Progressions documents define prerequisite relationships

### English Language Arts (ELA)
**Strand Structure:**
- Reading: Literature, Informational Text, Foundational Skills (K-5)
- Writing
- Speaking & Listening
- Language

**Anchor Standards:**
- College and Career Readiness Anchor Standards define end-of-high-school expectations
- Grade-specific standards define progression toward anchor standards

## Alignment Methodology Requirements

### 1. Standards Identification
- Platform must support mapping of learning objectives to specific CCSS identifiers
- Support for state-specific variants (e.g., Texas TEKS, Virginia SOL)

### 2. Prerequisite Mapping
- Define prerequisite relationships between standards
- Support adaptive learning path generation based on prerequisite mastery
- Example: CCSS.MATH.CONTENT.3.NF.A.1 (understanding fractions) is prerequisite to CCSS.MATH.CONTENT.4.NF.B.3 (adding/subtracting fractions)

### 3. Progress Monitoring
- Track student progress toward standards mastery
- Generate standards-based progress reports
- Support standards-based grading integration

## Technical Requirements
- Standards database with unique identifiers
- Prerequisite graph data model
- Progress tracking aligned to standards proficiency levels
- Export capabilities for standards-based reporting

## Next Generation Science Standards (NGSS) Alignment Requirements

## Three-Dimensional Learning Framework

NGSS organizes science learning around three interconnected dimensions:

### 1. Disciplinary Core Ideas (DCIs)
- **Physical Sciences**: Matter, forces, energy, waves
- **Life Sciences**: Organisms, ecosystems, heredity, evolution
- **Earth and Space Sciences**: Earth's systems, space systems, Earth and human activity
- **Engineering, Technology, and Applications of Science**: Engineering design, links among engineering, technology, science, and society

### 2. Science and Engineering Practices (SEPs)
- Asking questions/defining problems
- Developing and using models
- Planning and carrying out investigations
- Analyzing and interpreting data
- Using mathematics and computational thinking
- Constructing explanations/designing solutions
- Engaging in argument from evidence
- Obtaining, evaluating, and communicating information

### 3. Crosscutting Concepts (CCCs)
- Patterns
- Cause and effect
- Scale, proportion, and quantity
- Systems and system models
- Energy and matter
- Structure and function
- Stability and change

## Performance Expectations (PEs)
- Standards defined as performance expectations combining all three dimensions
- Format: [DCI]-[SEP]-[CCC]
- Example: MS-PS1-1 (Middle School Physical Science: Matter and its Interactions)

## Alignment Methodology Requirements

### 1. Three-Dimensional Assessment
- Content must assess all three dimensions simultaneously
- Cannot assess DCIs in isolation from SEPs and CCCs

### 2. Progression Mapping
- Learning progressions show development of understanding across grade bands
- Elementary → Middle School → High School coherence

### 3. Integration Support
- Platform must support interdisciplinary connections
- Engineering design process integration

## Technical Requirements
- Performance expectation database with dimensional tagging
- Cross-dimensional assessment item tagging
- Progression visualization for students and educators
- Phenomenon-based learning scenario support

## Compliance Implementation Roadmap

## Phase 1: Foundation (MVP)
- Implement COPPA verifiable parental consent workflow
- Create FERPA-compliant DPA template
- Establish data security baseline (encryption, access controls)
- Implement WCAG 2.1 AA Level A requirements (minimum accessibility)
- Map Common Core and NGSS standards to content structure

## Phase 2: Enhanced Compliance
- Full WCAG 2.1 Level AA implementation
- Multi-state privacy law compliance mapping
- Automated data retention and deletion workflows
- Comprehensive audit logging
- Parent/student data access portal

## Phase 3: Advanced Privacy
- Differential privacy for learning analytics
- Federated learning capabilities for personalization
- Automated compliance monitoring
- State-specific DPA generation
- Accessibility conformance reporting tools

## Ongoing Requirements
- Annual privacy policy review and updates
- Regular accessibility audits (quarterly)
- COPPA Rule updates monitoring
- State law change tracking
- Security assessments (annual penetration testing)
