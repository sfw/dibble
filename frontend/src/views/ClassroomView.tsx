import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'

import { labelForView, resolveContinueActionView } from '../app/workspace'
import {
  ClassroomFilterBar,
  type AttentionFilter,
  type InterventionFilter,
  type LayoutMode,
} from '../components/ClassroomFilterBar'
import { CollapsibleTriageSection } from '../components/CollapsibleTriageSection'
import { CompactLearnerCard } from '../components/CompactLearnerCard'
import { EmptyState, MetricList, PanelNotice, Pill, SectionHeader } from '../components/primitives'
import {
  formatAttentionReason,
  formatContinueAction,
  formatContractLabel,
  formatTimestamp,
} from '../lib/formatters'
import type { TeacherSectionOverview, TeacherSectionReadModel, TeacherLearnerCard } from '../types'

export function ClassroomView({
  classrooms,
  selectedSectionId,
  classroom,
  loading = false,
  error = '',
  onPickClassroom,
  onOpenTeacher,
  onContinueLearner,
  handoffLoadingStudentId = null,
  showDebugPanels = false,
}: {
  classrooms: TeacherSectionOverview[]
  selectedSectionId: string
  classroom: TeacherSectionReadModel
  loading?: boolean
  error?: string
  onPickClassroom: (classroomId: string) => void
  onOpenTeacher: (studentId: string) => void
  onContinueLearner: (studentId: string, continueActionKind: string) => void
  handoffLoadingStudentId?: string | null
  showDebugPanels?: boolean
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [attentionFilter, setAttentionFilter] = useState<AttentionFilter>('all')
  const [interventionFilter, setInterventionFilter] = useState<InterventionFilter>('all')
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('card')

  const triageSections = buildTriageSections(classroom.learners)
  const resumeReadyCount = classroom.learners.filter(
    (learner) => resolveContinueActionView(learner.current_flow.continue_action.kind) !== null,
  ).length

  const filteredSections = useMemo(() => {
    return triageSections.map((section) => ({
      ...section,
      learners: section.learners.filter((learner) => {
        if (searchQuery && !learner.student_id.toLowerCase().includes(searchQuery.toLowerCase())) {
          return false
        }
        if (attentionFilter !== 'all' && learner.attention_level !== attentionFilter) {
          return false
        }
        if (
          interventionFilter === 'has_intervention' &&
          learner.intervention.proposal_status !== 'available'
        ) {
          return false
        }
        return true
      }),
    }))
  }, [triageSections, searchQuery, attentionFilter, interventionFilter])

  const totalCount = classroom.learners.length
  const filteredCount = filteredSections.reduce((sum, s) => sum + s.learners.length, 0)

  return (
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.92fr)]">
      <div className="flex flex-col gap-6">
        <div className="panel">
          <SectionHeader
            eyebrow="Teacher section view"
            title="Section attention and progression posture"
            description="This first section workspace uses the backend-owned section read model rather than aggregating individual learner requests on the client."
          />
          <div className="grid gap-4 md:grid-cols-2">
            {classrooms.map((item) => {
              const isSelected = item.section_id === selectedSectionId
              return (
                <button
                  key={item.section_id}
                  type="button"
                  className={`option-card ${isSelected ? 'option-card--selected' : ''}`}
                  onClick={() => onPickClassroom(item.section_id)}
                >
                  <div className="option-card__header">
                    <strong>{item.title}</strong>
                    <Pill label={`${item.learner_count} learners`} tone="neutral" />
                  </div>
                  <p>
                    {item.teacher_label ?? 'Unassigned teacher'} • {formatContractLabel(item.subject, 'Subject pending')}
                  </p>
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
            eyebrow="Teacher triage queue"
            title="Move from section posture to learner action handoff"
            description="This queue stays summary-first: teachers can review backend-owned intervention readiness, see blocked progression separately from active work, and hand off directly into the right learner surface."
          />
          <ClassroomFilterBar
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            attentionFilter={attentionFilter}
            onAttentionFilterChange={setAttentionFilter}
            interventionFilter={interventionFilter}
            onInterventionFilterChange={setInterventionFilter}
            layoutMode={layoutMode}
            onLayoutModeChange={setLayoutMode}
            filteredCount={filteredCount}
            totalCount={totalCount}
          />
          <div className="mt-4 flex flex-col gap-4">
            {filteredSections.map((section) => (
              <CollapsibleTriageSection
                key={section.key}
                title={section.title}
                description={section.description}
                tone={section.tone}
                count={section.learners.length}
                defaultExpanded={section.key !== 'on-track'}
              >
                {section.learners.length === 0 ? (
                  <EmptyState
                    title="No learners in this queue"
                    description="The backend section contract did not return any learners for this triage bucket."
                  />
                ) : layoutMode === 'compact' ? (
                  section.learners.map((learner) => (
                    <CompactLearnerCard
                      key={learner.student_id}
                      learner={learner}
                      isOpening={learner.student_id === handoffLoadingStudentId}
                      onOpenTeacher={onOpenTeacher}
                      onContinueLearner={onContinueLearner}
                    />
                  ))
                ) : (
                  section.learners.map((learner) => {
                    const continueView = resolveContinueActionView(learner.current_flow.continue_action.kind)
                    const isOpening = learner.student_id === handoffLoadingStudentId

                    return (
                      <article key={learner.student_id} className="history-card triage-card">
                        <div className="history-card__meta">
                          <div>
                            <strong>{learner.student_id}</strong>
                            <p className="muted">
                              Grade {learner.grade_level} • {formatContractLabel(learner.attention_level)} attention
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-3">
                            <Pill label={formatContractLabel(learner.current_flow.flow_type)} tone="neutral" />
                            <Pill
                              label={formatContractLabel(learner.curriculum_progression.status)}
                              tone={toneForProgression(learner.curriculum_progression.status)}
                            />
                            <Pill
                              label={formatContractLabel(learner.intervention.proposal_status)}
                              tone={toneForIntervention(learner.intervention.proposal_status)}
                            />
                          </div>
                        </div>
                        <div className="summary-card__grid">
                          <div>
                            <span>Current phase</span>
                            <strong>{formatContractLabel(learner.current_flow.current_phase)}</strong>
                          </div>
                          <div>
                            <span>Current outcome</span>
                            <strong>{learner.curriculum_progression.current_outcome?.title ?? 'Not active'}</strong>
                          </div>
                          <div>
                            <span>Recommended teacher action</span>
                            <strong>{formatContinueAction(learner.intervention.recommended_action_kind)}</strong>
                          </div>
                          <div>
                            <span>Next learner handoff</span>
                            <strong>{continueView ? labelForView(continueView) : 'Teacher review first'}</strong>
                          </div>
                        </div>
                        <p>{describeLearnerRationale(learner)}</p>
                        <div className="flex flex-wrap items-center gap-3">
                          {learner.attention_reasons.map((reason) => (
                            <Pill key={reason} label={formatAttentionReason(reason)} tone="warning" />
                          ))}
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => onOpenTeacher(learner.student_id)}
                            disabled={isOpening}
                          >
                            {isOpening ? 'Opening learner…' : 'Open teacher triage'}
                          </Button>
                          {continueView ? (
                            <Button
                              type="button"
                              size="sm"
                              onClick={() =>
                                onContinueLearner(learner.student_id, learner.current_flow.continue_action.kind)
                              }
                              disabled={isOpening}
                            >
                              {isOpening ? 'Opening learner…' : `Continue ${labelForView(continueView)}`}
                            </Button>
                          ) : null}
                        </div>
                      </article>
                    )
                  })
                )}
              </CollapsibleTriageSection>
            ))}
          </div>
        </div>
      </div>

      <aside className="flex flex-col gap-6">
        <div className="panel">
          <SectionHeader
            eyebrow="Section summary"
            title="Operational snapshot"
            description="Compact counts for teacher triage and intervention planning."
          />
          <MetricList
            title={classroom.title}
            items={[
              { label: 'Teacher', value: classroom.teacher_label ?? 'Unassigned' },
              { label: 'Subject', value: formatContractLabel(classroom.subject, 'Unknown') },
              { label: 'Learners', value: String(classroom.learner_count) },
              { label: 'Active flows', value: String(classroom.active_flow_count) },
              { label: 'Interventions', value: String(classroom.intervention_available_count) },
              { label: 'Blocked progression', value: String(classroom.blocked_progression_count) },
              { label: 'Resume-ready learners', value: String(resumeReadyCount) },
              { label: 'Missing learners', value: String(classroom.missing_learner_count) },
              { label: 'Updated', value: formatTimestamp(classroom.updated_at) },
            ]}
          />
        </div>
        {classroom.missing_student_ids.length > 0 ? (
          <div className="panel">
            <SectionHeader
              eyebrow="Data gaps"
              title="Missing section records"
              description="These roster entries did not resolve to a learner summary."
            />
            <div className="flex flex-col gap-4">
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
            <PanelNotice message="Refreshing section contracts…" />
          </div>
        ) : null}
        {error ? (
          <div className="panel">
            <PanelNotice message={error} tone="error" />
          </div>
        ) : null}
        {showDebugPanels ? (
          <details className="panel json-panel">
            <summary>Debug section payload</summary>
            <pre>{JSON.stringify(classroom, null, 2)}</pre>
          </details>
        ) : null}
      </aside>
    </section>
  )
}

function buildTriageSections(learners: TeacherLearnerCard[]): Array<{
  key: string
  title: string
  description: string
  tone: 'accent' | 'success' | 'warning' | 'danger' | 'neutral'
  learners: TeacherLearnerCard[]
}> {
  // Group by backend-provided attention_level and intervention status.
  // The backend owns the decision about which learners need attention.
  const teacherAction = learners.filter((learner) => learner.intervention.proposal_status === 'available')
  const needsAttention = learners.filter(
    (learner) =>
      learner.intervention.proposal_status !== 'available' &&
      (learner.attention_level === 'high' || learner.attention_level === 'medium'),
  )
  const onTrack = learners.filter(
    (learner) => !teacherAction.includes(learner) && !needsAttention.includes(learner),
  )

  return [
    {
      key: 'teacher-action',
      title: 'Needs teacher action now',
      description: 'These learners already have a backend-generated intervention proposal ready for review.',
      tone: 'accent',
      learners: teacherAction,
    },
    {
      key: 'needs-attention',
      title: 'Needs attention',
      description: 'These learners are flagged by the backend for monitoring.',
      tone: 'warning',
      learners: needsAttention,
    },
    {
      key: 'on-track',
      title: 'Ready for learner workflow handoff',
      description: 'These learners can usually move straight into their backend-owned continue action.',
      tone: 'success',
      learners: onTrack,
    },
  ]
}

function describeLearnerRationale(learner: TeacherLearnerCard): string {
  return (
    learner.intervention.latest_decision_status
      ? `Latest teacher decision: ${formatContractLabel(learner.intervention.latest_decision_status)}.`
      : learner.curriculum_progression.rationale ??
        learner.current_flow.next_step.rationale ??
        learner.current_flow.rationale
  ) ?? 'No learner-level rationale returned.'
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
