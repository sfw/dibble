import { Button } from '@/components/ui/button'

import { MetricList, Pill, SectionHeader } from '../components/primitives'
import { formatTimestamp, titleCase } from '../lib/formatters'
import type { TeacherClassroomOverview, TeacherClassroomReadModel } from '../types'

export function ClassroomView({
  classrooms,
  selectedClassroomId,
  classroom,
  loading = false,
  error = '',
  onPickClassroom,
  onOpenLearner,
  showDebugPanels = false,
}: {
  classrooms: TeacherClassroomOverview[]
  selectedClassroomId: string
  classroom: TeacherClassroomReadModel
  loading?: boolean
  error?: string
  onPickClassroom: (classroomId: string) => void
  onOpenLearner: (studentId: string) => void
  showDebugPanels?: boolean
}) {
  return (
    <section className="view-grid">
      <div className="main-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Teacher classroom view"
            title="Classroom attention and progression posture"
            description="This first classroom workspace uses the backend-owned classroom read model rather than aggregating individual learner requests on the client."
          />
          <div className="classroom-overview-grid">
            {classrooms.map((item) => {
              const isSelected = item.classroom_id === selectedClassroomId
              return (
                <button
                  key={item.classroom_id}
                  type="button"
                  className={`option-card ${isSelected ? 'option-card--selected' : ''}`}
                  onClick={() => onPickClassroom(item.classroom_id)}
                >
                  <div className="option-card__header">
                    <strong>{item.title}</strong>
                    <Pill label={`${item.learner_count} learners`} tone="neutral" />
                  </div>
                  <p>{item.teacher_label ?? 'Unassigned teacher'} • {item.subject ?? 'subject pending'}</p>
                  <div className="summary-card__grid">
                    <div>
                      <span>Attention needed</span>
                      <strong>{String(item.attention_needed_count)}</strong>
                    </div>
                    <div>
                      <span>Blocked</span>
                      <strong>{String(item.blocked_progression_count)}</strong>
                    </div>
                    <div>
                      <span>Interventions</span>
                      <strong>{String(item.intervention_available_count)}</strong>
                    </div>
                    <div>
                      <span>Missing records</span>
                      <strong>{String(item.missing_learner_count)}</strong>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Learner cards"
            title="Which learners need attention right now"
            description="Learner cards combine flow, curriculum progression, and teacher-intervention availability into one classroom-level read model."
          />
          <div className="classroom-learner-list">
            {classroom.learners.map((learner) => (
              <article key={learner.student_id} className="history-card">
                <div className="history-card__meta">
                  <div>
                    <strong>{learner.student_id}</strong>
                    <p className="muted">
                      Grade {learner.grade_level} • {titleCase(learner.attention_level)} attention
                    </p>
                  </div>
                  <div className="hero-pills">
                    <Pill label={learner.current_flow.flow_type} tone="neutral" />
                    <Pill label={learner.curriculum_progression.status} tone={toneForProgression(learner.curriculum_progression.status)} />
                    <Pill label={learner.intervention.proposal_status} tone={toneForIntervention(learner.intervention.proposal_status)} />
                  </div>
                </div>
                <div className="summary-card__grid">
                  <div>
                    <span>Current phase</span>
                    <strong>{learner.current_flow.current_phase}</strong>
                  </div>
                  <div>
                    <span>Current resource</span>
                    <strong>{learner.curriculum_progression.current_resource?.title ?? 'Not active'}</strong>
                  </div>
                  <div>
                    <span>Next content</span>
                    <strong>{learner.current_flow.next_step.content_type ?? 'monitor'}</strong>
                  </div>
                  <div>
                    <span>Recommended action</span>
                    <strong>{titleCase(learner.intervention.recommended_action_kind)}</strong>
                  </div>
                </div>
                <p>
                  {learner.curriculum_progression.rationale ??
                    learner.current_flow.rationale ??
                    'No learner-level rationale returned.'}
                </p>
                <div className="action-row">
                  {learner.attention_reasons.map((reason) => (
                    <Pill key={reason} label={reason} tone="warning" />
                  ))}
                  <Button type="button" variant="outline" size="sm" onClick={() => onOpenLearner(learner.student_id)}>
                    Open learner detail
                  </Button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>

      <aside className="side-column">
        <div className="panel">
          <SectionHeader
            eyebrow="Classroom summary"
            title="Operational snapshot"
            description="Compact counts for teacher triage and intervention planning."
          />
          <MetricList
            title={classroom.title}
            items={[
              { label: 'Teacher', value: classroom.teacher_label ?? 'Unassigned' },
              { label: 'Subject', value: classroom.subject ?? 'Unknown' },
              { label: 'Learners', value: String(classroom.learner_count) },
              { label: 'Active flows', value: String(classroom.active_flow_count) },
              { label: 'Interventions', value: String(classroom.intervention_available_count) },
              { label: 'Blocked progression', value: String(classroom.blocked_progression_count) },
              { label: 'Missing learners', value: String(classroom.missing_learner_count) },
              { label: 'Updated', value: formatTimestamp(classroom.updated_at) },
            ]}
          />
        </div>
        {classroom.missing_student_ids.length > 0 ? (
          <div className="panel">
            <SectionHeader
              eyebrow="Data gaps"
              title="Missing classroom records"
              description="These roster entries did not resolve to a learner summary."
            />
            <div className="stack">
              {classroom.missing_student_ids.map((studentId) => (
                <div key={studentId} className="history-card">
                  <strong>{studentId}</strong>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {loading ? (
          <div className="panel">
            <p className="muted">Refreshing classroom contracts…</p>
          </div>
        ) : null}
        {error ? (
          <div className="panel">
            <p className="inline-error">{error}</p>
          </div>
        ) : null}
        {showDebugPanels ? (
          <details className="panel json-panel">
            <summary>Debug classroom payload</summary>
            <pre>{JSON.stringify(classroom, null, 2)}</pre>
          </details>
        ) : null}
      </aside>
    </section>
  )
}

function toneForProgression(status: string): 'accent' | 'success' | 'warning' | 'danger' | 'neutral' {
  if (status.includes('blocked')) {
    return 'warning'
  }
  if (status.includes('active') || status.includes('ready')) {
    return 'success'
  }
  return 'neutral'
}

function toneForIntervention(status: string): 'accent' | 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'available') {
    return 'accent'
  }
  if (status.includes('unavailable')) {
    return 'neutral'
  }
  return 'warning'
}
