---
author: Educational Technology Research Team
classification: UX Specification
date: '2026-03-13'
version: '1.0'
---

# UX Design Specification: Adaptive K-12 Learning Platform

## Executive Summary

This document defines user experience specifications for an adaptive K-12 learning platform, grounded in the 10 evidence-based personas from stakeholder research. The design rejects VARK/Multiple Intelligences learning styles in favor of personalization based on knowledge state, cognitive load, and documented accommodations.

**Key Design Principles:**
1. **Accessibility-First**: WCAG 2.1 Level AA compliance is non-negotiable—not a feature
2. **Cognitive Load Management**: Interfaces reduce extraneous cognitive load for all users
3. **Universal Design**: Accommodations (TTS, keyboard nav) available to all, not just documented disabilities
4. **Agency & Transparency**: Students understand why content is selected; teachers maintain override control
5. **Privacy Transparency**: Clear data use explanations appropriate to age/developmental level

**Critical Decision**: The onboarding flow does NOT include a "learning styles assessment" (per Pashler et al., 2008—no credible evidence). Instead, it gathers: (1) developmental/grade context, (2) language/L1 information, (3) documented accommodations, (4) brief diagnostic assessment.

## User Flow 1: Student Onboarding

**Purpose**: Establish student profile, gather context for personalization, conduct initial diagnostic—without learning styles assessment.

**Entry Points**:
- Direct registration (COPPA workflow for <13)
- Clever/Google SSO (roster import)
- Teacher/class code

**Flow Steps**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        STUDENT ONBOARDING FLOW                          │
│                     (Estimated: 8-12 minutes)                           │
└─────────────────────────────────────────────────────────────────────────┘

Step 1: Welcome + Age/Gate
┌────────────────────────────────────────────────────────────────────────┐
│  "Let's set up your learning journey"                                  │
│                                                                        │
│  [Avatar selection: diverse options, no gender stereotypes]            │
│                                                                        │
│  "What grade are you in?"                                              │
│  [K] [1] [2] [3] [4] [5] [6] [7] [8] [9] [10] [11] [12]               │
│                                                                        │
│  [Continue →]                                                          │
└────────────────────────────────────────────────────────────────────────┘
│ COPPA Check: If K-5 → Trigger Parental Consent Workflow
│
▼
Step 2: Language Context (NOT learning style)
┌────────────────────────────────────────────────────────────────────────┐
│  "What language do you speak at home?"                                 │
│  [Dropdown: Spanish, English, Mandarin, Vietnamese, Arabic, Other...]  │
│                                                                        │
│  "What language do you prefer for learning?"                           │
│  [Same options, default = home language]                               │
│                                                                        │
│  [Continue →]                                                          │
└────────────────────────────────────────────────────────────────────────┘
│ → Enables cognate highlighting, L1 resources for ELL (Diego persona)
│
▼
Step 3: Accommodation Preferences
┌────────────────────────────────────────────────────────────────────────┐
│  "These tools can help everyone learn better. Which would you like?"   │
│  (Universal design—NOT disability screening)                           │
│                                                                        │
│  [☐] Read questions aloud to me                                        │
│  [☐] More time for activities                                          │
│  [☐] Fewer animations/distractions                                     │
│  [☐] Highlight words as they're read                                   │
│  [☐] Larger text                                                       │
│  [☐] High contrast colors                                              │
│                                                                        │
│  [Continue →]                                                          │
└────────────────────────────────────────────────────────────────────────┘
│ → Aiden persona: Auto-enables assistive features
│ → These are adjustable later in settings
│
▼
Step 4: Brief Diagnostic (8-12 items)
┌────────────────────────────────────────────────────────────────────────┐
│  "Let's find the right starting place for you"                         │
│  (Adaptive: items adjust based on responses; 8-12 items typical)       │
│                                                                        │
│  [Math problem with visual scaffolding]                                │
│  • TTS available on all text                                           │
│  • Progress indicator: "Question 3 of 8"                               │
│  • Skip option: "I haven't learned this yet" → Stops diagnostic        │
│                                                                        │
│  [Continue →]                                                          │
└────────────────────────────────────────────────────────────────────────┘
│ → Establishes initial KnowledgeState
│ → May offer L1 version for ELL students (Diego)
│
▼
Step 5: Personalized Dashboard Reveal
┌────────────────────────────────────────────────────────────────────────┐
│  "Your learning map is ready!"                                         │
│                                                                        │
│  [Animated visualization: "You've unlocked 3 new skills to explore"]   │
│                                                                        │
│  [Start Learning →]                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

**Accessibility Annotations**:
- All interactive elements keyboard accessible (Tab order logical)
- Focus indicators visible (3px outline, high contrast)
- Color not sole indicator (icons + text for all states)
- TTS available on all instructions
- Touch targets minimum 44x44px (iOS) / 48x48dp (Android)

## User Flow 2: Daily Learning Session

**Purpose**: Core student experience—adaptive content delivery with transparent personalization.

**Flow**:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                       DAILY LEARNING SESSION                            │
└─────────────────────────────────────────────────────────────────────────┘

Dashboard Entry
┌────────────────────────────────────────────────────────────────────────┐
│  [Header: "Hi Maya! Ready to learn?"]                                  │
│                                                                        │
│  [Learning Map Visualization]                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  🎯 Current Focus: Equivalent Fractions (Grade 4)              │   │
│  │  [Progress ring: 75% mastered]                                 │   │
│  │                                                                │   │
│  │  [Skill nodes: visual graph of connected concepts]             │   │
│  │  ●───●───🟡───○───○                                            │   │
│  │  Mastered  Learning  Available                                 │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  [🔔 2 review items ready] [📚 Continue Learning →]                   │
│                                                                        │
│  [Settings] [Help]                                                     │
└────────────────────────────────────────────────────────────────────────┘
│
▼
Content Delivery (Adaptive Loop)
┌────────────────────────────────────────────────────────────────────────┐
│  [Navigation breadcrumb: Math > Fractions > Equivalent Fractions]      │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                                                                │   │
│  │  [Problem stem with TTS button 🔊]                             │   │
│  │                                                                │   │
│  │  "Which fraction is equivalent to 2/4?"                        │   │
│  │                                                                │   │
│  │  [Visual fraction model: two circles divided]                  │   │
│  │                                                                │   │
│  │  [○] 1/2    [○] 1/4    [○] 3/4                                │   │
│  │                                                                │   │
│  │  [💡 Hint]    [📝 Work Space]    [⏸️ Take a Break]            │   │
│  │                                                                │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  [Submit Answer →]                                                     │
└────────────────────────────────────────────────────────────────────────┘
│
▼
Immediate Feedback
┌────────────────────────────────────────────────────────────────────────┐
│  [For correct answer]                                                  │
│  "Great thinking! You used what you know about simplifying fractions." │
│                                                                        │
│  [Growth-oriented, specific feedback—not just "Correct!"]              │
│                                                                        │
│  [For incorrect answer]                                                │
│  "Not quite. Let's look at this together."                             │
│  [Worked example reveals, highlighting the connection]                 │
│                                                                        │
│  [Continue →]  [Try Similar Problem →]                                 │
└────────────────────────────────────────────────────────────────────────┘
│
▼
Transition to Next Item (<200ms with prefetch)
┌────────────────────────────────────────────────────────────────────────┐
│  [Skeleton loading state while next content loads]                     │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  └────────────────────────────────────────────────────────────────┘   │
│  (Replaced instantly with actual content)                              │
└────────────────────────────────────────────────────────────────────────┘
```

**Modality Switching Interaction Pattern**:
- Students can request alternative representations (NOT based on "learning style"):
```
[🔄 Show me another way] → Dropdown:
  • Watch a video explanation
  • See a worked example
  • Try with manipulatives
  • Read the step-by-step
```
- This is learner agency, not learning style matching—encourages flexible thinking
- System tracks which representations lead to faster mastery for this specific concept

**Cognitive Load Management Features**:
- Break timer (Aiden persona): "You've been working for 15 minutes. Want a 2-minute break?"
- Progress saves automatically—no anxiety about losing work
- "I need help" escalation to teacher (not just hints)

## User Flow 3: Teacher Intervention Workflow

**Purpose**: Enable teachers to identify at-risk students early and take targeted action.

**Flow**:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TEACHER DASHBOARD + INTERVENTION                     │
└─────────────────────────────────────────────────────────────────────────┘

Teacher Dashboard (James persona)
┌────────────────────────────────────────────────────────────────────────┐
│  [Class selector: Period 3 Math ▼]    [📅 This Week] [⚙️ Settings]    │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  🚨 AT-RISK ALERTS (3 students need attention)                 │   │
│  │                                                                │   │
│  │  Marcus G. • Grade 9 • 34% predicted success on upcoming quiz │   │
│  │  [Gap: Fraction operations, Negative numbers] [View Details →]│   │
│  │                                                                │   │
│  │  Aisha K. • Grade 9 • Stuck on same skill for 3 sessions      │   │
│  │  [Skill: Linear equations] [Assign Remediation →]             │   │
│  │                                                                │   │
│  │  Diego R. • Grade 4 • Declining engagement pattern            │   │
│  │  [Last login: 2 days ago] [Send Encouragement →]              │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  CLASS MASTERY OVERVIEW                                        │   │
│  │  [Heatmap: Students × Standards, color-coded by mastery %]     │   │
│  │                                                                │   │
│  │         4.NF.1  4.NF.2  4.NF.3  4.NF.4  4.NF.5                 │   │
│  │  Maya    ████    ████    ██░░    ░░░░    ░░░░                 │   │
│  │  Diego   ████    ███░    ██░░    ░░░░    ░░░░                 │   │
│  │  ...                                                             │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  [+ Assign Content] [📊 Generate Report] [👥 IEP Progress]           │
└────────────────────────────────────────────────────────────────────────┘
│
▼
Intervention Action (Marcus case)
┌────────────────────────────────────────────────────────────────────────┐
│  Marcus G. • Intervention Planning                                     │
│                                                                        │
│  [AI-Generated Recommendation]                                         │
│  "Marcus shows gaps in 2 prerequisite skills for the upcoming unit:    │
│   • Adding fractions with unlike denominators                          │
│   • Integer operations on number line                                  │
│   Suggested: Assign 20-minute review module before Tuesday's class"    │
│                                                                        │
│  [Override Recommendation]                                             │
│                                                                        │
│  [☑️] Assign prerequisite review (auto-selected)                       │
│  [☐] Pull into small group tomorrow                                     │
│  [☐] Modify next assignment difficulty (lower one level)               │
│  [☐] Send message to student                                            │
│                                                                        │
│  [Message Preview]                                                     │
│  "Hi Marcus! I've assigned some quick practice on fractions to help    │
│   you feel ready for Tuesday. You've got this! -Mr. James"             │
│                                                                        │
│  [Send Intervention →]  [Cancel]                                       │
└────────────────────────────────────────────────────────────────────────┘
│
▼
Assignment Creation (Override Adaptive)
┌────────────────────────────────────────────────────────────────────────┐
│  + Assign Content                                                      │
│                                                                        │
│  [By Standard] [By Topic] [From My Library] [Quick Remediation]       │
│                                                                        │
│  Select Students:                                                      │
│  [☑️ All] [☐ Select Individual...]                                    │
│                                                                        │
│  Content Selection:                                                    │
│  [Search standards or topics...]                                       │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  CCSS.MATH.4.NF.A.1 - Equivalent Fractions                     │   │
│  │  [Preview] [Select →]                                          │   │
│  │  Adaptive difficulty: [Auto ▼] [Force Easy] [Force Challenge]  │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  Due Date: [Date picker]    Priority: [Normal ▼]                       │
│                                                                        │
│  [Assign →]                                                            │
└────────────────────────────────────────────────────────────────────────┘
```

**Key Features**:
- At-risk algorithm uses BKT/DKT predictions (not just low grades)
- Teacher override always available (human-in-the-loop)
- Accommodation usage tracked for IEP compliance (Elena persona)

## User Flow 4: Parent Visibility

**Purpose**: Provide meaningful, actionable insight to parents without overwhelming detail.

**Flow**:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PARENT PROGRESS CHECK-IN                           │
└─────────────────────────────────────────────────────────────────────────┘

Weekly Summary Email (David persona)
┌────────────────────────────────────────────────────────────────────────┐
│  Subject: Maya's learning this week 🌟                                  │
│                                                                        │
│  Hi David,                                                             │
│                                                                        │
│  Maya was active on [Platform] 4 days this week! Here's what           │
│  she accomplished:                                                     │
│                                                                        │
│  ✓ Mastered: Equivalent fractions (Grade 4 standard)                   │
│  ✓ Practiced: Comparing fractions with visual models                   │
│  🔄 Working on: Adding fractions with like denominators                │
│                                                                        │
│  [View Full Progress →]                                                │
│                                                                        │
│  How you can help:                                                     │
│  "Ask Maya to explain what 'equivalent' means using pizza slices!      │
│   This reinforces her learning in a fun way."                          │
│                                                                        │
│  Questions? Reply to this email or visit our Help Center.              │
└────────────────────────────────────────────────────────────────────────┘
│
▼
Parent Portal (Mobile-First Design)
┌────────────────────────────────────────────────────────────────────────┐
│  [Header: Maya's Learning]    [🔔] [⚙️]                               │
│                                                                        │
│  [Simple progress visualization—no grade-level emphasis]               │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  This Week                                                     │   │
│  │  ████████████████████░░░░  45 minutes, 4 sessions              │   │
│  │                                                                │   │
│  │  Current Focus: Equivalent Fractions                           │   │
│  │  [Progress ring: 3 of 4 skills mastered]                       │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  [What is Maya learning?]                                              │
│  "Maya is working on understanding that fractions can look different   │
│   but represent the same amount (like 1/2 and 2/4)."                  │
│                                                                        │
│  [How can I help?]                                                     │
│  • Ask her to find examples at home (slicing food, measuring)          │
│  • Praise effort and strategy, not just correct answers                │
│  • Encourage her to use the 'Hint' button when stuck                   │
│                                                                        │
│  [📊 See detailed progress] [✉️ Message teacher]                       │
│                                                                        │
│  [Privacy Settings] [Language: English ▼]                              │
└────────────────────────────────────────────────────────────────────────┘
```

**Privacy Safeguards**:
- COPPA-compliant: Parents have access to all data collected on their child
- Granular sharing controls: Parents choose what teachers can see
- Data deletion: One-click request to delete account and all data

## User Flow 5: Assessment Experience

**Purpose**: Evaluate learning outcomes while minimizing test anxiety and maintaining accessibility.

**Flow**:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ASSESSMENT EXPERIENCE                           │
└─────────────────────────────────────────────────────────────────────────┘

Pre-Assessment
┌────────────────────────────────────────────────────────────────────────┐
│  "Let's see what you've learned!"                                      │
│                                                                        │
│  • About 10-15 questions                                               │
│  • Take your time—accuracy matters more than speed                     │
│  • You can take a break anytime                                        │
│  • This helps me know what to teach you next                           │
│                                                                        │
│  [Accommodations auto-applied:]                                        │
│  ✓ Read-aloud enabled  ✓ Extended time                                 │
│                                                                        │
│  [Start Assessment →]                                                  │
└────────────────────────────────────────────────────────────────────────┘
│
▼
Assessment Item (Adaptive)
┌────────────────────────────────────────────────────────────────────────┐
│  Question 7 of 15    [Save for later] [⏸️ Pause]                       │
│  [Progress bar: ████████████████░░░░]                                  │
│                                                                        │
│  [Problem content with full accessibility features]                    │
│                                                                        │
│  [Response area with multiple input options:]                          │
│  • Multiple choice                                                     │
│  • Drag-and-drop manipulatives                                         │
│  • Equation editor (for older students)                                │
│  • Voice input (if enabled)                                            │
│                                                                        │
│  [Flag for teacher review] [Request hint (not scored)]                 │
│                                                                        │
│  [Next →]                                                              │
└────────────────────────────────────────────────────────────────────────┘
│
▼
Post-Assessment
┌────────────────────────────────────────────────────────────────────────┐
│  "Assessment Complete!"                                                │
│                                                                        │
│  [Growth-focused feedback]                                             │
│  "You showed growth in equivalent fractions!                           │
│   Next, we'll work on comparing fractions with different denominators."│
│                                                                        │
│  [Specific actionable next steps—not just a score]                     │
│                                                                        │
│  [Continue to Dashboard →]                                             │
└────────────────────────────────────────────────────────────────────────┘
```

**Accommodation Support**:
- All IEP/504 accommodations automatically applied
- Extended time mode removes visible timer
- Teacher can review flagged items (student asked for help)

## Screen Wireframes: Text-Based Specifications

## Screen 1: Student Dashboard (Primary)

**Layout Structure**:
```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Logo]  [Navigation: My Learning | Progress | Settings]  [Help] [👤]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  "Good morning, Maya! 👋"                                        │   │
│  │  "You're making great progress on fractions. Ready to continue?" │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  LEARNING MAP (Visual Graph)                                     │   │
│  │                                                                  │   │
│  │     [🟢 Mastered]───[🟡 Learning Now]───[⚪ Next Up]            │   │
│  │          │                                        │              │   │
│  │     [🟢 Mastered]                            [⚪ Locked]        │   │
│  │                                                                  │   │
│  │  Legend: 🟢 Mastered  🟡 In Progress  ⚪ Available  🔒 Locked   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────┐  │
│  │  📚 CONTINUE LEARNING           │  │  🔔 REVIEW (2 items due)    │  │
│  │  [Large primary button]         │  │  [Secondary button]         │  │
│  │  Pick up where you left off     │  │  Spaced repetition review   │  │
│  └─────────────────────────────────┘  └─────────────────────────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  RECENT ACHIEVEMENTS                                             │   │
│  │  🏆 "Fraction Master" - Completed 5 fraction skills              │   │
│  │  📈 "On a roll" - 3-day streak                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [Accessibility toolbar: 🔊 TTS] [🔍 Zoom] [🎨 Contrast]               │
└─────────────────────────────────────────────────────────────────────────┘
```

**Interaction Patterns**:
- Learning map nodes are keyboard navigable (arrow keys)
- Hover/long-press reveals skill name and mastery percentage
- Clicking locked node shows prerequisite path

---

## Screen 2: Teacher At-Risk Dashboard

**Layout Structure**:
```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Logo]  [Class: Period 3 Math ▼]  [📊 Reports | 👥 Students | ⚙️]     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [Alert Summary Bar]                                                    │
│  🚨 3 At-Risk  |  ⚠️ 6 Approaching  |  ✅ 21 On Track                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  PRIORITY ALERTS (sorted by risk score)                          │   │
│  │                                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │ Marcus G.  Risk Score: 76%  [Assign Intervention →]    │    │   │
│  │  │ • Predicted success on Tue quiz: 34%                   │    │   │
│  │  │ • Knowledge gaps: Adding fractions, Integer ops        │    │   │
│  │  │ • Last mastery: 2 days ago                             │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  │                                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │ Aisha K.   Risk Score: 62%  [View Details →]           │    │   │
│  │  │ • Stuck on linear equations for 3 sessions             │    │   │
│  │  │ • Multiple hint requests, low completion rate          │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  │                                                                  │   │
│  │  [View All Alerts →]                                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  CLASS MASTERY HEATMAP                                           │   │
│  │  [Interactive grid: Students rows × Standards columns]           │   │
│  │  [Color scale: Red <50% | Yellow 50-80% | Green 80%+ ]          │   │
│  │  [Click cell → Student detail] [Click header → Standard detail] │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [+ Quick Assign] [📥 Export Data] [📋 IEP Reports]                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Screen 3: Content Assignment (Teacher)

**Layout Structure**:
```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Logo]  [← Back to Dashboard]        [+ Create Assignment]            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Step 1: Select Students                                                │
│  [☑️ Select All (30)]  [Filter: At-Risk only ▼]                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  [☑️] Marcus G.  [☑️] Aisha K.  [☑️] Diego R.  ...               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Step 2: Select Content                                                 │
│  [Search: "equivalent fractions"]     [Browse by Standard ▼]          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │ 📚 Equivalent Fractions (CCSS.MATH.4.NF.A.1)            │    │   │
│  │  │ Difficulty: Adaptive (Default)  Duration: ~15 min     │    │   │
│  │  │ [Preview] [Select ✓]                                    │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  │                                                                  │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │ 📚 Fraction Visual Models (CCSS.MATH.4.NF.A.2)          │    │   │
│  │  │ [Preview] [Select]                                      │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Step 3: Configure                                                      │
│  Due Date: [________]  Priority: [Normal ▼]                            │
│  Adaptive Difficulty: [Auto ▼]  [Override: Force Easy ▼]               │
│  [☑️] Require mastery before advancing                                │
│                                                                         │
│  [Assign to 3 Students →]  [Save Draft]                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

## Interaction Patterns: Modality Switching

**Pattern: Representation Selector**

Location: Adjacent to all problem stems
Behavior: Click/keyboard activate reveals alternative representations

```
[Problem Stem]
"Which fraction is equivalent to 2/4?"

[🔄 See another way]
┌─────────────────────────────┐
│ Try this concept as:        │
│ • 🎥 Video explanation      │
│ • 📝 Worked example         │
│ • 🧮 Virtual manipulative   │
│ • 📖 Step-by-step text      │
│                             │
│ [Learn about these options] │
└─────────────────────────────┘
```

**Accessibility**:
- Button has aria-label="Alternative representations"
- Dropdown keyboard navigable (arrow keys, Enter to select, Escape to close)
- Focus returns to problem after selection

**Design Rationale**: This is NOT learning style accommodation. Research shows learners benefit from experiencing multiple representations (Ainsworth, 2006). The system tracks which representations correlate with faster mastery for this concept (not this student), informing content improvement.

## Interaction Patterns: Accessibility Features

**Pattern: Universal Access Toolbar**

Persistent, collapsible toolbar available on all screens:

```
┌─────────────────────────────────────────────────────────┐
│ [🔊 Text-to-Speech] [⏯️ Pause Animations] [🔍 Zoom ±]  │
│ [🎨 High Contrast] [⌨️ Keyboard Help] [❓ Help]        │
└─────────────────────────────────────────────────────────┘
```

**Implementation Details**:
- TTS: Web Speech API with word highlighting (synchronized with text)
- Pause animations: CSS `animation-play-state: paused` globally
- Zoom: Browser zoom coordination (rem-based layout)
- High contrast: CSS media query `prefers-contrast: high`

**Keyboard Navigation**:
- `Tab`: Navigate interactive elements
- `Shift+Tab`: Reverse navigation
- `Enter`/`Space`: Activate
- `Escape`: Close modals/menus
- `?`: Show keyboard shortcut help

**Screen Reader Support**:
- All images have descriptive alt text
- ARIA live regions for dynamic updates ("New problem loaded")
- Status announcements for mastery achievements
- Math content: MathML with verbose/terse reading options

## Evidence-Based Design Decisions

| Design Choice | Evidence Base | Rejected Alternative |
|---------------|---------------|---------------------|
| No learning styles assessment on onboarding | Pashler et al. (2008): "virtually no evidence" for meshing hypothesis | VARK questionnaire |
| Multiple representations available to all | Ainsworth (2006): Multiple representations support learning | Assigning single modality by "learning style" |
| Mastery-based progression | Sutiawan et al. (2025): d=1.2 effect size | Time-based progression |
| Spaced repetition prompts | Cao & Carvalho (2025): adaptive spaced retrieval improves retention | Massed practice |
| Growth-focused feedback (strategy praise) | Dweck growth mindset research | Intelligence praise ("you're smart") |
| Teacher override always available | Human-in-the-loop AI safety | Fully automated placement |
| Universal design for accessibility | WCAG 2.1 Level AA; benefits all learners | Accommodation-only design |
| Cognitive load indicators (break suggestions) | Sweller Cognitive Load Theory | No attention to cognitive load |

**Critical Exclusions**:
- ❌ No "visual/auditory/kinesthetic" learner profiles
- ❌ No Multiple Intelligences tracks
- ❌ No gamification with public leaderboards (anxiety-inducing)
- ❌ No "grade level" labels on remediation content (stigma-reducing)
