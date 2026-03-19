# Classroom / Course Relationship Refactor Plan

## Why this needs to change

The current data model is not aligned with real LMS usage.

Today:

- `Classroom` stores `student_ids` and an optional `teacher_label`, but no teacher user IDs:
  - [src/dibble/models/classroom.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/models/classroom.py)
- `User` stores `teacher_id` and `classroom_ids` directly:
  - [src/dibble/models/auth.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/models/auth.py)
- classroom read models are built entirely from `classroom.student_ids` and ignore teacher membership:
  - [src/dibble/services/teacher_classroom_service.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/services/teacher_classroom_service.py)
- teacher routes return all classrooms without teacher-scoped membership checks:
  - [src/dibble/api/teacher_routes.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/api/teacher_routes.py)

That means the system currently models:

- a classroom roster
- a display label for the teacher
- separate user affiliation fields

It does **not** model the real relationship:

- courses/sections are taught by one or more teachers
- learners are enrolled in one or more sections
- assignments, reporting, and permissions should flow through those memberships

## Target domain model

For a serious LMS, the model should be:

### 1. Course

Defines the instructional container independent of a specific roster.

Suggested fields:

- `course_id`
- `title`
- `subject`
- `grade_band`
- `curriculum_package_id`
- `tags`

This is the reusable instructional entity.

### 2. Section

Represents an actual taught offering of a course in a term/cohort.

This is likely what the current `Classroom` concept wants to be.

Suggested fields:

- `section_id`
- `course_id`
- `title`
- `term_id`
- `school_id` or `organization_id`
- `status`
- `meeting_metadata` later if needed

### 3. SectionTeacherMembership

Represents which teachers teach a section.

Suggested fields:

- `section_id`
- `user_id`
- `role_in_section`
  - `lead_teacher`
  - `co_teacher`
  - `observer`

### 4. SectionLearnerEnrollment

Represents which learners are enrolled in a section.

Suggested fields:

- `section_id`
- `user_id`
- `enrollment_status`
  - `active`
  - `pending`
  - `withdrawn`

### 5. User

User keeps identity/auth concerns, not instructional ownership shortcuts.

Keep:

- `user_id`
- `role`
- `display_name`
- auth credential fields
- optional external SIS identifiers

Deprecate as core relationship fields:

- `teacher_id` as the primary teacher linkage
- `classroom_ids` as the primary membership source

If `teacher_id` remains, it should mean an external HR/SIS identifier, not “this teacher owns these learners”.

## Recommended interpretation of existing concepts

To avoid a massive rename all at once:

- current `Classroom` should evolve toward `Section`
- a new `Course` model should be introduced above it

If we need a shorter bridge:

- first add teacher memberships to the current `Classroom`
- then add `Course`
- then rename/refactor `Classroom` semantics to `Section`

## What should stop being true

The following patterns should stop being authoritative:

1. learner linked directly to a teacher through `user.teacher_id`
2. classroom teacher represented only as `teacher_label`
3. roster membership duplicated in both `classroom.student_ids` and `user.classroom_ids`
4. teacher access inferred from broad role alone instead of section membership

## What should become true

1. Teachers teach sections, not learners.
2. Learners enroll in sections, not teachers.
3. Courses define instructional structure; sections define actual delivery.
4. Permissions and reporting are scoped by section membership.
5. Assignments belong to sections and optionally to individual learners.

## Immediate schema direction

Add these new tables before deleting old fields:

- `courses`
- `sections`
- `section_teacher_memberships`
- `section_learner_enrollments`

Keep current tables temporarily:

- `classrooms`
- `users.teacher_id`
- `users.classroom_ids`

Then backfill and migrate.

## Runtime contract changes needed

### Teacher dashboard

Current teacher views should be section-scoped, not global-role-scoped.

Change needed:

- `GET /api/teachers/classrooms` should only return sections the authenticated teacher is assigned to, unless the user is admin/editor with elevated visibility

### Classroom read model

Current read model should derive learners from section enrollments, not `student_ids`.

It should also expose assigned teachers as real identities, not just a label.

### Auth identity

`AuthIdentity.classroom_ids` should become derived membership context, not a manually edited duplication field.

Longer term:

- replace with `section_ids`
- optionally include scoped course/section permissions

### Assignments

Assignments already have both `teacher_id` and `classroom_id`:
  - [src/dibble/models/assignment.py](/Users/sfw/conductor/workspaces/dibble/surabaya/src/dibble/models/assignment.py)

That should evolve to:

- `section_id` as the instructional container
- `created_by_user_id` as the teacher/staff actor
- optional `learner_user_id` target for individualized work

## Migration plan

### Phase 0: stop the conceptual bleed

Do this first:

- treat `teacher_label` as display-only legacy data
- stop designing new features around `user.teacher_id -> learner`
- stop using `user.classroom_ids` as the long-term source of truth

### Phase 1: add normalized membership tables

Backend work:

- add `Course`, `Section`, `SectionTeacherMembership`, `SectionLearnerEnrollment` models
- add SQLite tables and stores
- add admin CRUD routes
- add migration/backfill script from existing `classrooms` and `users.classroom_ids`

Bridge behavior:

- keep old fields readable
- write new membership tables as the source of truth
- optionally dual-write old fields for temporary compatibility

### Phase 2: switch teacher/classroom APIs

Change teacher APIs and services to:

- resolve accessible sections from memberships
- build section rosters from enrollments
- expose assigned teacher users on the section contract

This is the point where the teacher experience starts matching reality.

### Phase 3: fix staff/admin UI

Staff UI should manage:

- courses
- sections
- teacher assignments
- learner enrollments

Not:

- free-text teacher labels
- direct learner-to-teacher linkage fields

### Phase 4: deprecate legacy fields

Once all read paths are migrated:

- remove `teacher_label` or make it purely derived
- remove `classroom.student_ids`
- remove `users.classroom_ids` as authoritative membership
- remove `users.teacher_id` as an instructional relationship field

## Recommended first implementation slice

If we want the safest first step, do this:

1. Add `section_teacher_memberships` and `section_learner_enrollments`.
2. Keep the current `Classroom` table for now.
3. Teach `TeacherClassroomService` to prefer membership tables over `student_ids`.
4. Update teacher routes to filter by authenticated teacher memberships.
5. Update staff user/classroom management to edit memberships instead of `teacher_id`.

That gives us the real-world relationship correction without forcing an immediate course catalog build.

## Longer-term “world’s best LMS” implication

If the goal is truly world-class LMS behavior, the system should eventually support:

- course templates vs live sections
- co-teaching
- cross-listed sections
- learner enrollments across multiple sections
- term-aware roster history
- section-scoped analytics and permissions
- curriculum package attachment at the course/section level

None of that sits cleanly on the current learner-to-teacher shortcut.

## Bottom line

Yes: the current model missed the real usage connection.

The correct backbone is:

- `Course`
- `Section`
- `SectionTeacherMembership`
- `SectionLearnerEnrollment`

with user identity/auth kept separate from instructional relationships.
