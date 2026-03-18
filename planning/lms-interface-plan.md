# LMS Interface Plan

Last updated: 2026-03-17

## Purpose

This document reframes the current frontend direction from a backend contract workbench into a comprehensive learning management system interface that can sit on top of the existing Dibble backend.

Use it to answer:

- what product surfaces a real LMS needs around the current backend
- how the current frontend maps to that target
- which interfaces should be learner-facing versus teacher/admin-facing
- what we can build now with existing contracts
- what should land in what order

## Current Product Reality

The current frontend is primarily an integration shell for:

- learner summary and current flow inspection
- generation, Socratic, and remediation workflow control
- teacher explainability and intervention review
- classroom triage
- live-versus-demo contract verification

That work has been valuable because it hardened the backend-facing read models and workflow semantics.

But it is not yet the right product shape for a learner-facing LMS because:

- learners are not moving through a guided lesson shell
- the UI is organized around workflows and contracts instead of learning tasks
- teachers are seeing system posture and triage surfaces before they see instructional workflows
- the frontend still exposes orchestration inputs that should usually be backend-owned or hidden

## Product Goal

Build a three-layer LMS around the Dibble backend:

1. Learner experience:
   A focused, student-safe learning environment for daily work, adaptive lessons, Socratic checks, remediation, review, and progress.
2. Teacher experience:
   A classroom workflow for assigning, monitoring, intervening, reviewing learner reasoning, and handling exceptions.
3. Staff / operator experience:
   A smaller internal workspace for QA, contract inspection, fallback debugging, and workflow validation.

The current frontend should evolve toward layer 1 and 2 as the primary product.
Layer 3 should remain available, but as an internal tool rather than the default app shell.

## Product Principles

- Backend-owned progression:
  The LMS should not invent lesson sequencing, mastery gating, or intervention policy locally.
- Learner-first interaction model:
  Students should see tasks, prompts, supports, feedback, and progress, not routing metadata.
- Teacher clarity over telemetry:
  Teachers should see actionable summaries, not raw system internals.
- Explainability without overload:
  Rationale should exist where needed, but not dominate every screen.
- One app, role-aware shells:
  Learners, teachers, and staff should share a design system and contracts, but not the same navigation.
- Safe degradation:
  Demo fallback and diagnostics can exist, but should be clearly marked and separated from normal product use.

## Target Users

### Learners

Primary jobs:

- resume the next learning task quickly
- complete adaptive lesson activities
- respond to Socratic checks
- work through remediation when needed
- review progress and recent work

Needs:

- a clean, distraction-light interface
- obvious next step
- visible progress and confidence
- supportive feedback and pacing
- continuity across sessions

### Teachers

Primary jobs:

- see who needs attention
- understand why a learner is blocked or being held
- assign or launch learning sessions
- review current learner state and recent work
- approve, defer, or redirect backend-proposed interventions

Needs:

- class-level visibility
- learner-level drill-in
- explainable progression
- clear intervention actions
- low-friction navigation between class and learner detail

### Staff / operators

Primary jobs:

- validate contracts
- inspect generation quality and fallback posture
- test adaptive flows end to end
- debug live integration problems

Needs:

- raw contract visibility
- debug toggles
- live/demo posture
- test data controls

## Information Architecture

### 1. Learner App

Primary navigation:

- Home
- Continue Learning
- Assignments
- Progress
- History
- Help

Core learner surfaces:

#### Learner Home

Purpose:

- show the current backend-owned next step
- show the current unit / lesson / target concept
- let the learner resume instantly

Uses current backend contracts:

- `GET /api/learners/{student_id}/workspace`
- `GET /api/learners/{student_id}/summary`
- `GET /api/learners/{student_id}/progression`

UI modules:

- current lesson card
- resume CTA
- today’s focus
- confidence / support posture in learner-safe language
- recent achievements or streak

#### Continue Learning

Purpose:

- deliver the active backend-owned artifact in a focused instructional shell

Delivery modes to support:

- generated lesson content
- practice problem
- worked example
- Socratic turn
- remediation step

Uses current backend contracts:

- learner workspace active artifact
- generation `workflow_summary`
- Socratic session summary
- remediation session summary

UI modules:

- lesson header
- content canvas
- response area
- support rail
- progress rail
- next-step CTA

#### Socratic Check

Purpose:

- present conversational understanding checks as part of learning, not as a QA console

Uses current backend contracts:

- `POST /api/assessments/socratic`
- `GET /api/assessments/socratic/{session_id}`

UI modules:

- prompt card
- learner response composer
- confidence picker
- conversation history
- scaffolded support panel

#### Remediation Session

Purpose:

- guide the learner through a backend-owned repair arc

Uses current backend contracts:

- `POST /api/remedial/trigger`
- `GET /api/remedial/sessions/{session_id}`
- `POST /api/remedial/sessions/{session_id}/advance`

UI modules:

- phase header
- misconception-friendly explanation
- current step content
- learner input area
- continue CTA
- “why this lesson” disclosure

#### Assignments

Purpose:

- package learning work into teacher-visible and learner-visible containers even if early versions are thin

Phase 1 stance:

- start as a presentation layer around learner workspace and current progression
- avoid inventing an assignment engine if the backend does not own it yet

Likely initial modules:

- active work
- ready next work
- recently completed work

#### Progress

Purpose:

- show learner-friendly progress without overwhelming with system terminology

Uses current backend contracts:

- learner summary
- learner progression
- learner history

UI modules:

- current concept progress
- course / unit progress
- recent wins
- “what to practice next”

#### History

Purpose:

- let learners revisit prior generated artifacts, Socratic checks, and remediation sessions

Uses current backend contracts:

- generation history
- Socratic history
- remediation history

### 2. Teacher App

Primary navigation:

- Dashboard
- Classrooms
- Learners
- Interventions
- Assignments
- Reports

Core teacher surfaces:

#### Teacher Dashboard

Purpose:

- daily at-a-glance class posture

Uses current backend contracts:

- `GET /api/teachers/classrooms`

UI modules:

- classrooms summary
- attention-needed queue
- blocked progression queue
- intervention-ready queue
- quick links into learner drill-in

#### Classroom Detail

Purpose:

- manage one classroom as a teaching workflow, not just as a triage list

Uses current backend contracts:

- `GET /api/teachers/classrooms/{classroom_id}`

UI modules:

- class roster
- learner status bands
- current lesson focus
- intervention needs
- resume / review / message actions

#### Learner Detail

Purpose:

- give teachers a coherent learner story: progress, current task, reasoning, intervention options, and recent history

Uses current backend contracts:

- learner summary
- learner workspace
- learner history
- intervention-action
- learner progression

UI modules:

- learner overview
- current assignment / activity
- recent evidence
- current backend recommendation
- intervention decision panel
- artifacts timeline

#### Intervention Workspace

Purpose:

- make backend-owned intervention proposals actionable and comprehensible

Uses current backend contracts:

- `GET /api/learners/{student_id}/intervention-action`
- `POST /api/learners/{student_id}/intervention-action`

UI modules:

- proposed action summary
- alternative options
- rationale panel
- approval / defer / escalate controls

#### Assignment Management

Purpose:

- let teachers launch, pin, or frame learning work even if deep assignment ownership is not yet in backend scope

Phase 1 stance:

- begin with lightweight assignment wrappers and launch points
- keep backend progression authoritative for what comes next inside a learner flow

Early capabilities:

- launch lesson for learner
- open learner at current step
- save teacher-curated notes or context later if contracts allow

### 3. Staff / Operator Workspace

Purpose:

- preserve the value of the current control-room UI without making it the default product

Primary navigation:

- Contracts
- Generation QA
- Fallback / connectivity
- Session inspector
- Debug tools

This shell should host:

- the existing workflow workbench surfaces
- raw payload debugging
- live/demo toggles
- connectivity posture

## Recommended Shell Strategy

We should split the app into role-aware shells:

### Learner shell

- full-screen, task-first
- minimal navigation
- no raw workflow labels
- no system-level metadata

### Teacher shell

- class and learner management oriented
- moderate density
- rationale visible where needed
- artifact and intervention review built in

### Staff shell

- current tabbed integration workspace
- explicit internal-tool framing

This lets us keep the current frontend investment while moving it to the right product tier.

## Mapping Current Frontend To Target LMS

### Keep, but reposition

- `OverviewView` becomes a teacher learner-detail summary and parts of learner home
- `GenerationView` becomes:
  - learner delivery canvas for students
  - separate QA / authoring tool for staff
- `SocraticView` becomes:
  - learner conversational check flow
  - staff inspector for prompt/evidence diagnostics
- `RemediationView` becomes:
  - learner remediation flow
  - teacher review of remediation state
- `TeacherView` remains teacher-facing, but should shift from contract explanation to learner action
- `ClassroomView` remains teacher-facing and should become the core teacher dashboard slice

### De-emphasize in the primary product

- live/demo source switching
- raw workflow vocabulary as user-facing labels
- direct editing of target KCs, LOs, session IDs, and intent on primary learner screens
- stream event traces outside staff tools
- contract-level quality and moderation metadata on learner pages

## UX Direction By Surface

### Learner UX tone

- warm
- clear
- confidence-building
- low-density
- one next action at a time

### Teacher UX tone

- information-rich
- clear prioritization
- action-oriented
- trustworthy rationale

### Staff UX tone

- explicit internal tooling
- dense but inspectable
- optimized for debugging and validation

## Backend Contract Readiness For This Plan

### Strong enough now

- learner summary
- learner flow
- learner workspace
- learner progression
- generation workflow summary
- Socratic session summary
- remediation session summary
- learner history
- teacher classroom read models
- teacher intervention contract

### Notable gaps for a fuller LMS

- assignment model and assignment lifecycle
- teacher-to-learner messaging / comments
- course / unit shell beyond current progression snapshots
- authentication and role-aware app shell UX at product level
- notifications / inbox concepts
- richer learner profile settings and parent-facing views if desired later

These are product-expansion gaps, not reasons to delay the shell redesign.

## Delivery Roadmap

### Phase 0: stabilize and reposition the current frontend

Goal:

- keep the current app working while changing its role in the product

Work:

- relabel the current app as a staff or internal workspace
- keep current tabs available for QA and integration work
- remove it as the implied end-state learner app
- document which surfaces are internal versus product-facing

### Phase 1: build the learner shell

Goal:

- create a student-safe LMS around existing learner contracts

Work:

- learner home
- continue learning canvas
- learner Socratic experience
- learner remediation experience
- learner progress and history
- learner-safe copy layer over backend vocabulary

Definition of done:

- a student can log in, resume work, complete a learning step, continue into Socratic or remediation, and review progress without seeing internal contract concepts

### Phase 2: build the teacher shell

Goal:

- convert the current classroom and teacher drill-in into a true teacher workflow

Work:

- teacher dashboard
- improved classroom detail
- learner detail page
- intervention workspace
- teacher artifact review

Definition of done:

- a teacher can see class posture, open a learner, understand why the learner is where they are, and act on intervention recommendations without using the staff tool

### Phase 3: add assignment and reporting layers

Goal:

- make the LMS feel operationally complete

Work:

- assignment framing layer
- teacher reporting
- trend views
- class-level progress review
- role-aware navigation polish

### Phase 4: expand product depth

Potential work:

- richer artifacts
- course maps
- family portal
- messaging
- notifications
- standards mastery views

## Suggested Route Structure

### Learner app

- `/learn`
- `/learn/continue`
- `/learn/socratic/:sessionId`
- `/learn/remediation/:sessionId`
- `/learn/progress`
- `/learn/history`

### Teacher app

- `/teacher`
- `/teacher/classrooms`
- `/teacher/classrooms/:classroomId`
- `/teacher/learners/:studentId`
- `/teacher/learners/:studentId/intervention`
- `/teacher/reports`

### Staff app

- `/staff`
- `/staff/contracts`
- `/staff/generation`
- `/staff/socratic`
- `/staff/remediation`
- `/staff/classrooms`

## Frontend Architecture Guidance

- keep typed API adapters centered on backend contracts
- add a role-aware router and shell layout layer
- keep a translation layer from backend vocabulary to learner-safe and teacher-safe copy
- separate delivery components from inspection components
- preserve demo fallback only in staff mode by default
- treat debug payload panels as staff-only

## Design System Guidance

- shared primitives can remain repo-owned
- learner surfaces should use larger type, stronger focus hierarchy, and calmer pacing
- teacher surfaces should emphasize queueing, comparison, and action panels
- staff surfaces can remain denser and more technical

## Open Questions

- Do we want one app with role-aware routing or separate deployable frontends with a shared component system?
- How much assignment ownership should the frontend provide before the backend owns more of that lifecycle?
- Should learners see any rationale for adaptive moves, or only simple learner-safe explanations?
- How should authentication map to learner, teacher, and staff roles in the product shell?
- What level of offline resilience matters for the learner experience?

## Recommended Immediate Next Moves

1. Declare the current frontend an internal staff workspace, not the final learner app.
2. Design and implement a dedicated learner shell around `workspace`, `summary`, `progression`, and session contracts.
3. Rework the current classroom and teacher detail surfaces into a teacher shell with clearer day-to-day workflow framing.
4. Keep the current contract workbench alive for QA, fallback diagnosis, and backend validation.
5. Use this document as the parent plan for future frontend execution notes.

## Relationship To Existing Planning Docs

- `planning/front-end-work-plan.md` remains the implementation work log for the current frontend codebase.
- `planning/from-front-to-back-needs.md` remains the frontend-informed backend marching-orders note.
- This document defines the broader product direction for the LMS interface that should wrap the current backend and gradually replace the current frontend’s role as the main product shell.
