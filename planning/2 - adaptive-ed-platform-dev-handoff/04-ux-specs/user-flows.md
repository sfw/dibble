---
author: Educational Technology Research Team
classification: UX Flow Specification
date: '2026-03-13'
version: '1.0'
---

# User Flows: Detailed Specifications

## Overview

This document provides detailed flow specifications for the 5 core user journeys of the adaptive K-12 learning platform. Each flow includes: entry points, step-by-step screen transitions, decision logic, error handling, and accessibility considerations.

**Core Flows Covered**:
1. Student Onboarding (New User Registration)
2. Daily Learning Session (Core Student Experience)
3. Teacher Intervention (At-Risk Student Identification & Action)
4. Parent Check-In (Progress Visibility & Support)
5. Assessment Experience (Diagnostic & Progress Monitoring)

**Flow Notation**:
- `[]` = User action (click, tap, input)
- `<>` = System action (calculation, data fetch)
- `{}` = Decision point
- `→` = Flow direction
- `(alt)` = Alternative path

## Flow 1: Student Onboarding

## Entry Points
| Entry | Trigger | Special Handling |
|-------|---------|------------------|
| Direct Registration | Student visits platform directly | COPPA age-gating for <13 |
| Clever SSO | District-rostered student | Skip account creation, import accommodations |
| Teacher Class Code | Student enters code from teacher | Auto-enroll in class, inherit settings |
| Parent Invitation | Email link from parent consent | Pre-populate parent contact |

## Complete Flow Diagram

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
        (Diego persona: Enables ELL supports, cognate highlighting)
                    ↓
        [Accommodation Preferences: Universal design checklist]
        (Aiden persona: TTS, reduced animations, extended time)
                    ↓
        [Brief Diagnostic: 8-12 adaptive items]
        <Initialize KnowledgeState based on responses>
                    ↓
        {Diagnostic completed?}
            ├─(no/student skipped)→ [Skip confirmation] → [Dashboard with default placement]
            └─(yes)→ [Diagnostic results: "You can start learning X, Y, Z!"]
                    ↓
        [Personalized Dashboard Reveal]
        <Learning graph populated with frontier nodes>
                    ↓
        [End: Student ready to learn]
```

## Screen Specifications

### Screen: Landing Page
**Purpose**: First impression, establish trust, initiate registration
**Content**:
- Platform logo + tagline ("Your personal learning journey")
- Trust indicators (COPPA certified, FERPA compliant badges)
- Primary CTA: [Start Learning] (large, high contrast)
- Secondary: [I'm a Teacher] [I'm a Parent]
- Background: Subtle animated learning graph visualization

**Accessibility**:
- Focus starts on [Start Learning] button
- Skip to main content link (hidden until focused)
- Reduced motion alternative for animated background

### Screen: Grade Selection
**Purpose**: COPPA compliance trigger, developmental context
**Layout**: 4x3 grid of grade buttons (K, 1, 2, ... 12)
**Interactions**:
- Hover/Focus: Scale 1.05x, highlight border
- Click: Immediate transition to next screen
- Keyboard: Arrow keys navigate, Enter selects

**Decision Logic**:
```
IF grade IN [K, 1, 2, 3, 4, 5] THEN
    TRIGGER parental_consent_workflow
    SET coppa_required = true
ELSE
    SET coppa_required = false
ENDIF
```

### Screen: Parental Consent Workflow (COPPA)
**Purpose**: Verifiable parental consent per 16 CFR Part 312
**Steps**:
1. [Collect parent email address]
2. <Send consent request email with verification link>
3. [Inform student: "Ask a parent to check their email"]
4. {Wait for parent action (async)}
5. (Parent) [Open email] → [Click verification link] → [Review data use] → [Grant consent]
6. <System: Record consent with timestamp, IP, method>
7. [Notify student: "You're all set!"]

**Alternative Consent Methods**:
- Credit card verification (small charge, refunded)
- Phone/video call with staff (documented)
- Signed form upload (scanned)

### Screen: Language Context
**Purpose**: ELL support configuration
**Fields**:
1. "What language do you speak at home?" (Dropdown: 15+ languages)
2. "What language do you prefer for learning?" (Same options, defaults to home language)
3. "Would you like help with English words?" (Yes/No - enables cognate highlighting)

**System Actions**:
```
SET home_language = selected
SET interface_language = selected
IF home_language != English THEN
    ENABLE cognate_highlighting
    ENABLE picture_glossary
    OFFER diagnostic_in_l1
ENDIF
```

### Screen: Accommodation Preferences
**Purpose**: Universal design—not disability screening
**Copy**: "These tools can help everyone learn better. Pick what works for you:"

**Options** (checkboxes, all default OFF):
- ☐ Read questions aloud to me (TTS)
- ☐ More time for activities (extended_time)
- ☐ Fewer animations and distractions (reduced_motion)
- ☐ Highlight words as they're read (word_highlighting)
- ☐ Larger text (font_scale: 1.25x)
- ☐ High contrast colors (high_contrast_mode)

**Accessibility Note**: Each option has [Preview] button showing the effect immediately.

### Screen: Diagnostic Assessment
**Purpose**: Establish initial KnowledgeState
**Duration**: 8-12 items (adaptive—may terminate early if precision reached)
**Item Presentation**:
- One item per screen
- Full accessibility features available
- Skip option: "I haven't learned this yet" → ends diagnostic
- Progress indicator: "Question 3 of 8"

**Adaptive Logic**:
```
FOR each response:
    UPDATE irt_ability_estimate
    CALCULATE standard_error
    IF standard_error < 0.3 OR item_count >= 12 THEN
        BREAK
    ELSE
        SELECT next_item (max information at current estimate)
    ENDIF
ENDFOR
```

**Error Handling**:
- Connection lost: Auto-save progress, resume on reconnect
- Student abandons: Save partial diagnostic, mark as incomplete
- Timeout: Gentle prompt "Still there?" after 5 minutes inactivity

### Screen: Dashboard Reveal
**Purpose**: Celebrate readiness, show learning map
**Content**:
- Animated learning graph visualization
- 3-5 "unlocked" skills highlighted
- Message: "Based on your responses, you're ready to learn..."
- [Start Learning Now] primary CTA

**Personalization**:
- Maya (Grade 2): Simple map, fewer nodes, bigger touch targets
- Sophia (Grade 11): Detailed graph, advanced topics visible
- Diego (ELL): Bilingual welcome, cognate examples

## Flow 2: Daily Learning Session

## Entry Points
| Entry | Context |
|-------|---------|
| Dashboard [Continue Learning] | Resumes interrupted session |
| Teacher assignment notification | Assigned content due |
| Spaced repetition reminder | Review items queued |
| New skill unlocked | Completed prerequisite |

## Complete Flow Diagram

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
                ↓
        [End: Dashboard with updated progress]
```

## Screen Specifications

### Screen: Student Dashboard
**Purpose**: Orientation, progress visibility, session initiation
**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ Header: "Good [time], [Name]!" + Streak indicator          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Learning Map Visualization - center focus]               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ●───●───🟡───⚪───⚪  (Graph of skill nodes)        │   │
│  │  🟡 = Currently learning  ⚪ = Available next        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [📚 CONTINUE LEARNING] [🔄 REVIEW (n items)]              │
│                                                             │
│  [Recent Achievements strip]                               │
│                                                             │
│  [Accessibility toolbar - collapsible]                     │
└─────────────────────────────────────────────────────────────┘
```

**Interactions**:
- Learning map: Click/tap node → Zoom to skill details
- Long-press (mobile) / Right-click (desktop) → Context menu
- Keyboard: Tab through nodes, Enter to select

**Real-time Updates**:
- WebSocket connection for live progress sync
- Teacher intervention notifications appear as toast
- Spaced repetition items update count when due

### Screen: Content Delivery
**Purpose**: Present adaptive content with full support tools
**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ [Breadcrumb: Math > Fractions > Equivalent Fractions]      │
│ [Progress: ████████░░ 8 of 10 toward mastery]              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Problem Stem - with TTS button 🔊]                       │
│                                                             │
│  [Visual scaffolding / manipulative area]                  │
│                                                             │
│  [Response area: Multiple choice / Input / Drag-drop]      │
│                                                             │
│  [💡 Hint] [🔄 See another way] [📝 Work space]           │
│                                                             │
│  [Submit Answer →]                                         │
│                                                             │
│  [⏸️ Take a break] [🚩 Ask teacher for help]              │
└─────────────────────────────────────────────────────────────┘
```

**Hint System**:
- Progressive disclosure: 3 levels per problem
- Level 1: General prompt ("Think about what 'equivalent' means")
- Level 2: Specific strategy ("Try simplifying both fractions")
- Level 3: Worked example ("Here's how to solve it...")
- Each hint request logged for teacher analytics

**Modality Switching**:
- [🔄 See another way] dropdown:
  - 🎥 Video explanation (2-3 min)
  - 📝 Worked example (step-by-step)
  - 🧮 Virtual manipulative (interactive)
  - 📖 Text explanation (concise)

**Break Handling**:
- [⏸️ Take a break] → Optional: 2, 5, or 10 minutes
- Progress auto-saved
- Gentle return notification when break ends
- Aiden persona: Breaks suggested every 15 minutes

### Screen: Feedback & Transition
**Correct Answer Path**:
```
[Animation: Success indicator] 
[Message: Specific, growth-oriented feedback]
  "You used the strategy of simplifying fractions. 
   That's the key insight for equivalent fractions!"
[Next Action Options]:
  • [Continue →] (pre-fetched next item)
  • [Try a harder problem]
  • [Practice more like this]
```

**Incorrect Answer Path**:
```
[Animation: Neutral indicator (not red X)]
[Message: "Not quite. Let's look at this together."]
[Worked example reveals with connection to student's error]
[Options]:
  • [Try Again] (new similar problem)
  • [I need more help] → Escalate to teacher
  • [Let me review first] → See hints again
```

**Knowledge State Update**:
```
IF correctness > 0.8 THEN
    INCREASE mastery_probability(skill)
    IF mastery_probability > 0.85 THEN
        MARK skill_mastered
        SHOW mastery_animation
    ENDIF
ELSEIF correctness < 0.5 THEN
    FLAG for_spaced_repetition_soon
    CHECK prerequisites_for_remediation
ENDIF
```

### Screen: Session Summary
**Purpose**: Closure, progress recognition, next steps
**Content**:
- Time spent this session
- Skills practiced / mastered
- Items completed
- Streak updates
- [Return to Dashboard] [Continue Learning]

**Growth Mindset Messaging**:
- "You mastered equivalent fractions!" (not "You're smart at fractions")
- "You worked hard on comparing fractions—let's practice more tomorrow"
- No comparison to other students

## Flow 3: Teacher Intervention

## Entry Points
| Entry | Context |
|-------|---------|
| At-risk alert notification | Email/push: "3 students need attention" |
| Dashboard priority alerts | Daily check-in workflow |
| Student flag from content | Student clicked "I need help" |
| Scheduled review | Weekly at-risk review meeting |

## Complete Flow Diagram

```
[Start] → [Teacher Dashboard] → <Fetch at-risk scores for all students>
                ↓
        [Priority Alerts Section (sorted by risk score)]
            ├─[Click alert: Marcus G.] → [Student Detail View]
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

## Screen Specifications

### Screen: Teacher Dashboard - At-Risk Alerts
**Purpose**: Triage students needing attention
**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ [Class Selector ▼] [📊 Reports] [👥 Students] [⚙️ Settings]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🚨 PRIORITY ALERTS (3)                                     │
│  [Sort by: Risk Score ▼] [Filter ▼]                        │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Marcus G.                    Risk Score: 76% 🔴       │ │
│  │ • Predicted success on upcoming quiz: 34%             │ │
│  │ • Knowledge gaps: Adding fractions, Integer ops       │ │
│  │ • Last login: 2 days ago                              │ │
│  │ [View Details] [Assign Intervention →] [Dismiss]      │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Aisha K.                     Risk Score: 62% 🟡       │ │
│  │ • Stuck on linear equations (3 sessions)              │ │
│  │ • Multiple hint requests, low completion              │ │
│  │ [View Details] [Assign Intervention →] [Dismiss]      │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  [View All 12 At-Risk Students →]                          │
└─────────────────────────────────────────────────────────────┘
```

**Risk Score Calculation**:
```
risk_score = weighted_average(
    0.4 * (1 - predicted_success_on_upcoming),
    0.3 * (1 - recent_engagement_rate),
    0.2 * (knowledge_gap_count / total_upcoming_prerequisites),
    0.1 * (days_since_last_login / 7)
)
```

### Screen: Student Detail View
**Purpose**: Deep dive into individual student needs
**Tabs**:
1. **Overview**: Current knowledge state, recent trajectory
2. **Knowledge Map**: Visual graph with mastered/learning/gap areas
3. **Activity Log**: Recent interactions, time on task, help requests
4. **Accommodations**: IEP/504 status, usage tracking
5. **Communication**: Message history with student/parent

**Knowledge Map Visualization**:
- Interactive graph showing student's position
- Red nodes: Knowledge gaps
- Yellow nodes: Currently learning
- Green nodes: Mastered
- Gray nodes: Prerequisites not yet met
- Click any node → See detailed skill breakdown

### Screen: Intervention Composer
**Purpose**: Create targeted support for at-risk student
**AI Recommendation Panel** (left side):
```
┌─────────────────────────────────────────┐
│ 🤖 AI Recommendation                    │
│                                         │
│ Marcus shows gaps in 2 prerequisite    │
│ skills for Tuesday's quiz:             │
│ • Adding fractions with unlike         │
│   denominators (mastery: 34%)          │
│ • Integer operations on number line    │
│   (mastery: 28%)                       │
│                                         │
│ Suggested: Assign 20-minute review     │
│ module before Tuesday's class.         │
│                                         │
│ [Accept Suggestion] [Modify →]         │
└─────────────────────────────────────────┘
```

**Intervention Options** (checkboxes):
- ☑️ Assign prerequisite review content
- ☐ Pull into small group (schedule time)
- ☐ Modify next adaptive assignment (lower difficulty)
- ☐ Send encouraging message
- ☐ Notify parent of support being provided
- ☐ Escalate to specialist (SPED, ELL coordinator)

**Message Composer**:
- Template library: "Encouragement", "Check-in", "Assignment reminder"
- Personalization tokens: [Student Name], [Skill], [Due Date]
- Preview before send

### Screen: Intervention Tracking
**Purpose**: Monitor effectiveness of interventions
**Metrics Tracked**:
- Assignment completion rate
- Post-intervention mastery improvement
- Time to mastery (compared to non-intervened peers)
- Student engagement (login frequency, session duration)

**Status Options**:
- 🟡 In Progress
- 🟢 Resolved (student back on track)
- 🔴 Escalated (requires additional support)
- ⚪ No Response (student hasn't engaged with intervention)

### Flow 4: Parent Check-In

## Entry Points
| Entry | Context |
|-------|---------|
| Weekly email summary | Automated digest sent every Friday |
| Push notification | "Maya mastered a new skill!" |
| Child's request | "Can you check my progress?" |
| Concern about performance | Teacher communication triggers review |

## Complete Flow Diagram

```
[Start]
    ├─[Email notification] → [Open email] → [Click "View Progress"] → [Parent Portal]
    ├─[Direct login] → [Parent Portal Login] → [Parent Portal]
    └─[Child shares from platform] → [Pre-authenticated parent view]
                ↓
        [Parent Dashboard Overview]
            ├─[View weekly summary] → [Detailed progress view]
            ├─[View specific skill] → [Skill explanation + home activities]
            ├─[Message teacher] → [Compose message] → [Send]
            └─[Adjust settings] → [Notification preferences, privacy]
                ↓
        [Take Action]
            ├─[Print practice activities]
            ├─[Schedule learning time]
            └─[Request parent-teacher conference]
                ↓
        [End: Close portal or continue browsing]
```

## Screen Specifications

### Screen: Weekly Email Summary
**Purpose**: Low-friction progress visibility
**Content**:
```
Subject: Maya's learning this week 🌟

Hi David,

Maya was active on [Platform] 4 days this week.
Here's what she accomplished:

✓ MASTERED: Equivalent fractions (Grade 4)
  - Can identify fractions that represent the same amount
  - Completed 5 practice items with 80% accuracy

🔄 PRACTICED: Comparing fractions with visual models
  - Still working toward mastery
  - Encourage her to keep trying!

📅 NEXT UP: Adding fractions with like denominators
  - This builds on her equivalent fractions knowledge

[View Full Progress →] [Message Teacher →]

---
How you can help at home:
Ask Maya to explain what "equivalent" means using 
pizza slices or cookies. This reinforces her learning!

Questions? Reply to this email or visit our Help Center.
```

**Design Principles**:
- Mobile-friendly (most parents read on phone)
- No educational jargon
- Specific, actionable suggestions
- No comparison to other students
- Privacy-conscious (no PII in subject line)

### Screen: Parent Portal Dashboard
**Purpose**: On-demand, detailed progress visibility
**Layout** (Mobile-first):
```
┌─────────────────────────────────────────────────────────────┐
│ [Child Selector ▼ if multiple]  [🔔]  [⚙️]                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  THIS WEEK                                                  │
│  ████████████████████░░░░  45 min, 4 sessions              │
│                                                             │
│  CURRENT FOCUS                                              │
│  [Progress ring: 3 of 4 skills mastered]                   │
│  Equivalent Fractions                                       │
│                                                             │
│  [📊 See detailed progress]                                │
│                                                             │
│  ─────────────────────────────────────────────────────    │
│                                                             │
│  WHAT IS MAYA LEARNING?                                     │
│  "Maya is working on understanding that fractions          │
│   can look different but represent the same amount         │
│   (like 1/2 and 2/4)."                                      │
│                                                             │
│  [Watch a 2-min video about this concept]                  │
│                                                             │
│  ─────────────────────────────────────────────────────    │
│                                                             │
│  HOW CAN I HELP?                                            │
│  • Ask her to find fraction examples at home               │
│  • Praise effort and strategies, not just answers          │
│  • Encourage her to use hints when stuck                   │
│                                                             │
│  [💬 Message Teacher]  [📅 Schedule Conference]            │
│                                                             │
│  ─────────────────────────────────────────────────────    │
│                                                             │
│  [Privacy Settings]  [Language: English ▼]                 │
└─────────────────────────────────────────────────────────────┘
```

**Detailed Progress View**:
- Calendar heatmap: Days active this month
- Skills mastered (with dates)
- Skills in progress
- Time spent by subject
- Comparison to personal goals (not peers)

### Screen: Teacher Communication
**Purpose**: Easy parent-teacher coordination
**Features**:
- Quick message templates
- Photo attachment (for home practice evidence)
- Read receipts
- Translation (if teacher and parent prefer different languages)
- Scheduling integration for conferences

### Screen: Privacy & Data Controls
**Purpose**: COPPA/FERPA compliance transparency
**Options**:
- View all data collected on my child
- Download data (portability)
- Delete account and all data
- Manage sharing permissions (what teachers can see)
- Consent history (what was agreed to when)

## Flow 5: Assessment Experience

## Entry Points
| Entry | Context |
|-------|---------|
| Diagnostic (onboarding) | Initial placement |
| Progress check | End of unit (teacher-initiated) |
| Spaced repetition mastery check | Verify retention |
| State test prep | Standards-aligned benchmark |

## Complete Flow Diagram

```
[Start] → {Assessment type?}
    ├─Diagnostic → [Brief, adaptive: 8-12 items]
    ├─Progress check → [Unit-aligned: 10-15 items]
    └─Benchmark → [Comprehensive: 25-40 items]
                ↓
        [Pre-Assessment Screen]
            ├─[Accept and start] → [Assessment items]
            └─[Request accommodations] → [Modify settings] → [Start]
                ↓
        [Assessment Items] (Loop until complete)
            ├─[Answer question] → <Grade> → [Feedback] → [Next]
            ├─[Request hint] → <Mark as partially assisted> → [Hint shown]
            ├─[Flag for review] → <Add to review queue> → [Continue]
            └─[Pause/Save] → <Save progress> → [Resume later]
                ↓
        {Complete?}
            ├─(no/more items)→ [Next Item]
            └─(yes)→ [Post-Assessment Summary]
                ↓
        [Results]
            ├─[View detailed results]
            ├─[Share with teacher]
            └─[Return to dashboard]
                ↓
        [End: KnowledgeState updated]
```

## Screen Specifications

### Screen: Pre-Assessment
**Purpose**: Set expectations, confirm accommodations
**Content**:
```
┌─────────────────────────────────────────────────────────────┐
│  Let's check what you've learned!                          │
│                                                             │
│  • About 10-15 questions                                   │
│  • Take your time—accuracy matters more than speed         │
│  • You can take a break anytime                            │
│  • This helps me know what to teach you next               │
│                                                             │
│  Your accommodations:                                      │
│  ✓ Read-aloud enabled                                      │
│  ✓ Extended time (no visible timer)                        │
│                                                             │
│  [Start Assessment →]  [Adjust Settings]                   │
└─────────────────────────────────────────────────────────────┘
```

**Accommodation Auto-Application**:
- All IEP/504 accommodations pre-enabled
- Student can add/remove for this session
- Settings persist for future assessments

### Screen: Assessment Item
**Purpose**: Evaluate learning with minimal anxiety
**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│  Question 7 of 15    [⏸️ Pause] [🔖 Flag for review]       │
│  [Progress: ████████████████░░░░]                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Problem stem - with TTS 🔊]                              │
│                                                             │
│  [Visual / interactive content]                            │
│                                                             │
│  [Response area]                                           │
│  ○ Option A  ○ Option B  ○ Option C  ○ Option D           │
│                                                             │
│  [💡 Hint (not scored)] [🚩 I don't know]                 │
│                                                             │
│  [Submit →]                                                │
└─────────────────────────────────────────────────────────────┘
```

**Anti-Anxiety Features**:
- No countdown timer visible (unless requested)
- Progress shows items completed, not remaining
- "I don't know" option (no penalty for honesty)
- Hint available (marks item as assisted)
- Skip and return later

### Screen: Post-Assessment
**Purpose**: Growth-focused closure
**Correct Completion**:
```
┌─────────────────────────────────────────────────────────────┐
│  🎉 Assessment Complete!                                    │
│                                                             │
│  You showed growth in:                                     │
│  ✓ Equivalent fractions                                   │
│  ✓ Comparing fractions                                    │
│                                                             │
│  Next, we'll work on:                                      │
│  → Adding fractions with different denominators           │
│                                                             │
│  [View Details →]  [Return to Dashboard →]                │
└─────────────────────────────────────────────────────────────┘
```

**Incomplete/Challenging**:
```
┌─────────────────────────────────────────────────────────────┐
│  Assessment Complete                                        │
│                                                             │
│  Good effort! You worked hard on:                          │
│  • Equivalent fractions (mastered!)                        │
│  • Comparing fractions (let's practice more)              │
│                                                             │
│  I've added some practice to help you grow.               │
│                                                             │
│  [See Practice Plan →]  [Return to Dashboard →]           │
└─────────────────────────────────────────────────────────────┘
```

**No scores shown to students** (Marcus persona: avoids shame), only:
- Skills mastered
- Skills in progress
- Next steps

### Assessment Analytics (Teacher View)
- Class-wide standards mastery heatmap
- Individual student detailed results
- Item analysis (which questions were hardest)
- Accommodations used vs. granted (IEP compliance)
- Time-on-item analysis (flag unusually fast/slow)

## Cross-Cutting Accessibility Requirements

## WCAG 2.1 Level AA Compliance

### Keyboard Navigation
| Element | Behavior |
|---------|----------|
| All interactive elements | Reachable via Tab/Shift+Tab |
| Modal dialogs | Trap focus, Escape to close |
| Dropdown menus | Arrow keys navigate, Enter selects |
| Learning map | Arrow keys move between nodes |
| Skip link | "Skip to main content" first focusable element |

### Screen Reader Support
| Element | Requirement |
|---------|-------------|
| Images | Descriptive alt text or aria-label |
| Dynamic updates | aria-live regions for notifications |
| Math content | MathML with alt text fallback |
| Progress indicators | aria-valuenow, aria-valuemax |
| Error messages | aria-describedby association |
| Form fields | Associated labels (not placeholder-only) |

### Visual Design
| Requirement | Implementation |
|-------------|----------------|
| Color contrast | 4.5:1 minimum for text |
| Focus indicators | 3px outline, high contrast |
| Text resizing | Supports 200% zoom without loss |
| Animation control | Pause/stop for auto-playing content |
| Touch targets | Minimum 44x44px (iOS) / 48x48dp (Android) |

### Cognitive Accessibility
| Feature | Implementation |
|---------|----------------|
| Consistent navigation | Same patterns across all screens |
| Clear error messages | Explain what went wrong + how to fix |
| No time limits | Or ability to extend time |
| Reading level | UI text at grade-appropriate level |
| Reduce distractions | Option to hide non-essential elements |
