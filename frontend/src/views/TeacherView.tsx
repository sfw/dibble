import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

import { InsightCard, JsonPanel, MetricList, PanelNotice, Pill, SectionHeader } from '../components/primitives'
import {
  formatContentType,
  formatContinueAction,
  formatContractLabel,
  formatPercent,
  formatTimestamp,
  titleCase,
} from '../lib/formatters'
import type {
  LearnerCurriculumProgressionSummary,
  LearnerFlowSummary,
  LearnerProfileV2,
  ProfileSummary,
  TeacherContractGap,
  TeacherInterventionActionContract,
  TeacherInterventionDecision,
  TeacherInterventionDecisionRequest,
} from '../types'

export function TeacherView({
  summary,
  profile,
  flow,
  progression,
  intervention,
  gaps,
  dataSource,
  loading = false,
  submissionError = '',
  submittingDecision = false,
  onSubmitDecision,
  handoffContext = null,
  onReturnToClassroom,
  showDebugPanels = false,
}: {
  summary: ProfileSummary
  profile: LearnerProfileV2
  flow: LearnerFlowSummary
  progression: LearnerCurriculumProgressionSummary
  intervention: TeacherInterventionActionContract
  gaps: TeacherContractGap[]
  dataSource: 'live' | 'demo'
  loading?: boolean
  submissionError?: string
  submittingDecision?: boolean
  onSubmitDecision: (payload: TeacherInterventionDecisionRequest) => void
  handoffContext?: {
    classroomId: string
    classroomTitle: string
    learnerId: string
  } | null
  onReturnToClassroom?: () => void
  showDebugPanels?: boolean
}) {
  const recommendedOption = useMemo(
    () =>
      intervention.available_options.find((option) => option.is_recommended) ??
      intervention.available_options[0] ??
      null,
    [intervention.available_options],
  )
  const [selectedOptionId, setSelectedOptionId] = useState('')
  const latestDecisionOptionId =
    intervention.latest_decision?.selected_option_id &&
    intervention.available_options.some(
      (option) => option.option_id === intervention.latest_decision?.selected_option_id,
    )
      ? intervention.latest_decision.selected_option_id
      : ''
  const [note, setNote] = useState('')
  const effectiveSelectedOptionId = intervention.available_options.some(
    (option) => option.option_id === selectedOptionId,
  )
    ? selectedOptionId
    : (latestDecisionOptionId || recommendedOption?.option_id || '')
  const selectedOption =
    intervention.available_options.find((option) => option.option_id === effectiveSelectedOptionId) ?? recommendedOption

  return (
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.92fr)]">
      <div className="flex flex-col gap-6">
        {handoffContext ? (
          <div className="panel">
            <SectionHeader
              eyebrow="Classroom handoff"
              title={`Reviewing ${handoffContext.learnerId} from ${handoffContext.classroomTitle}`}
              description="This learner was opened from the classroom triage queue, so you can review the intervention contract here and then jump back to the classroom when you are done."
            />
            <div className="flex flex-wrap items-center gap-3">
              <Pill label={handoffContext.classroomId} tone="neutral" />
              {onReturnToClassroom ? (
                <Button type="button" variant="outline" size="sm" onClick={onReturnToClassroom}>
                  Return to classroom
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className="panel">
          <SectionHeader
            eyebrow="Teacher-facing explainability"
            title="Intervention readiness and rationale"
            description="This surface now reflects the backend-owned intervention contract, while still calling out the remaining teacher-facing gaps."
          />
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
            <InsightCard
              title="Current recommendation"
              value={formatContentType(flow.next_step.content_type)}
              detail={`Action ${formatContractLabel(flow.next_step.action)} on ${formatContractLabel(flow.next_step.target_stage)}`}
              rationale={flow.next_step.rationale ?? flow.rationale ?? 'No rationale returned'}
            />
            <InsightCard
              title="Teacher proposal"
              value={formatContractLabel(intervention.proposal_status)}
              detail={`Source ${formatContractLabel(intervention.source)}`}
              rationale={intervention.rationale ?? 'No intervention rationale returned'}
            />
            <InsightCard
              title="Risk posture"
              value={flow.session_stuck_loop_risk}
              detail={`Relapse risk ${formatPercent(summary.strategy.relapse_risk)}`}
              rationale={`Volatility ${formatPercent(summary.strategy.volatility_index)}`}
            />
            <InsightCard
              title="Trust level"
              value={dataSource === 'live' ? 'backend-connected' : 'demo-fallback'}
              detail={`Profile completeness ${formatPercent(profile.profile_metadata.completeness_score)}`}
              rationale="The teacher view should expose confidence and missing seams, not hide them."
            />
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Intervention control"
            title="Review the backend-owned intervention proposal"
            description="Teachers can see the proposed action, compare alternatives, and record a decision against the learner-specific intervention contract."
          />
          <div className="flex flex-col gap-4">
            <article className="summary-card">
              <div className="summary-card__topline">
                <Pill label={formatContractLabel(intervention.flow_type)} tone="neutral" />
                <Pill label={formatContractLabel(intervention.current_phase)} tone="accent" />
                <Pill label={formatContractLabel(intervention.target_stage)} tone="success" />
              </div>
              <h3>{selectedOption?.label ?? 'No intervention option selected'}</h3>
              <p>{selectedOption?.rationale ?? intervention.rationale ?? 'No intervention rationale returned.'}</p>
              <div className="summary-card__grid">
                <div>
                  <span>Progression action</span>
                  <strong>{formatContractLabel(intervention.progression_action)}</strong>
                </div>
                <div>
                  <span>Target KCs</span>
                  <strong>{intervention.active_target_kc_ids.join(', ') || 'none'}</strong>
                </div>
                <div>
                  <span>Next content</span>
                  <strong>{formatContentType(intervention.next_step.content_type)}</strong>
                </div>
                <div>
                  <span>Action kind</span>
                  <strong>{formatContinueAction(selectedOption?.continue_action.kind ?? intervention.proposed_action.kind)}</strong>
                </div>
              </div>
            </article>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {intervention.available_options.map((option) => {
                const isSelected = option.option_id === effectiveSelectedOptionId
                return (
                  <button
                    key={option.option_id}
                    type="button"
                    className={`option-card ${isSelected ? 'option-card--selected' : ''}`}
                    onClick={() => setSelectedOptionId(option.option_id)}
                  >
                    <div className="option-card__header">
                      <strong>{option.label}</strong>
                      {option.is_recommended ? <Pill label="recommended" tone="success" /> : null}
                    </div>
                    <p>{option.rationale ?? 'No rationale returned.'}</p>
                    <span className="muted">{formatContinueAction(option.continue_action.kind)}</span>
                  </button>
                )
              })}
            </div>

            <label>
              Teacher note
              <Textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Optional context for why this learner should be approved, deferred, escalated, or routed to a different backend-owned option."
              />
            </label>

            <div className="flex flex-wrap items-center gap-3">
              {intervention.allowed_decisions.map((decision) => (
                <Button
                  key={decision}
                  type="button"
                  variant={buttonVariantForDecision(decision)}
                  onClick={() => onSubmitDecision(buildDecisionPayload(decision, selectedOption?.option_id ?? null, note))}
                  disabled={submittingDecision || !selectedOption}
                >
                  {submittingDecision ? 'Saving…' : labelForDecision(decision)}
                </Button>
              ))}
              {loading ? <PanelNotice message="Refreshing intervention contract…" /> : null}
              {submissionError ? <PanelNotice message={submissionError} tone="error" /> : null}
            </div>

            {intervention.latest_decision ? (
              <article className="summary-card">
                <h3>Latest recorded decision</h3>
                <div className="summary-card__grid">
                  <div>
                    <span>Decision</span>
                    <strong>{formatContractLabel(intervention.latest_decision.decision)}</strong>
                  </div>
                  <div>
                    <span>Status</span>
                    <strong>{formatContractLabel(intervention.latest_decision.status)}</strong>
                  </div>
                  <div>
                    <span>Selected option</span>
                    <strong>{intervention.latest_decision.selected_option_id ?? 'none'}</strong>
                  </div>
                  <div>
                    <span>Recorded at</span>
                    <strong>{formatTimestamp(intervention.latest_decision.decided_at)}</strong>
                  </div>
                </div>
                <p>{intervention.latest_decision.note ?? 'No teacher note was recorded.'}</p>
              </article>
            ) : null}
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Curriculum progression"
            title="How learner flow aligns to curriculum posture"
            description="Teachers should be able to see the current learner move in the context of the backend-owned curriculum progression contract."
          />
          <div className="grid gap-4 md:grid-cols-2">
            <article className="summary-card">
              <div className="summary-card__topline">
                <Pill label={formatContractLabel(progression.status)} tone="neutral" />
                <Pill label={formatContractLabel(progression.current_stage)} tone="accent" />
              </div>
              <h3>{progression.current_resource?.title ?? 'No active curriculum resource'}</h3>
              <p>{progression.rationale ?? 'No curriculum progression rationale returned.'}</p>
              <div className="summary-card__grid">
                <div>
                  <span>Current action</span>
                  <strong>{formatContractLabel(progression.progression_action)}</strong>
                </div>
                <div>
                  <span>Next resource</span>
                  <strong>{progression.next_resource?.title ?? 'None queued'}</strong>
                </div>
                <div>
                  <span>Blocked resources</span>
                  <strong>{String(progression.blocked_resource_count)}</strong>
                </div>
                <div>
                  <span>Mastered ratio</span>
                  <strong>{formatPercent(progression.mastered_resource_ratio)}</strong>
                </div>
              </div>
            </article>
            <MetricList
              title="Progression counts"
              items={[
                { label: 'Resources', value: String(progression.resource_count) },
                { label: 'Ready', value: String(progression.ready_resource_count) },
                { label: 'Active', value: String(progression.active_resource_count) },
                { label: 'Blocked', value: String(progression.blocked_resource_count) },
                { label: 'Targets', value: progression.active_target_kc_ids.join(', ') || 'none' },
              ]}
            />
          </div>
        </div>

        <div className="panel">
          <SectionHeader
            eyebrow="Remaining backend gaps"
            title="What the frontend still cannot delegate cleanly to the backend"
            description="These are the gaps that still matter after the new history, workspace, and intervention contracts landed."
          />
          <div className="gap-list">
            {gaps.map((gap) => (
              <article key={gap.title} className="gap-card">
                <div className="gap-card__header">
                  <Pill
                    label={gap.severity}
                    tone={gap.severity === 'P0' ? 'danger' : gap.severity === 'P1' ? 'warning' : 'neutral'}
                  />
                  <h3>{gap.title}</h3>
                </div>
                <p><strong>Why it matters:</strong> {gap.why_it_matters}</p>
                <p><strong>Current backend:</strong> {gap.current_backend}</p>
                <p><strong>Frontend stance:</strong> {gap.frontend_response}</p>
              </article>
            ))}
          </div>
        </div>
      </div>

      <aside className="flex flex-col gap-6">
        <div className="panel">
          <SectionHeader
            eyebrow="Intervention summary"
            title="What a teacher can safely see"
            description="Compact, stable, and learner-specific read models."
          />
          <MetricList
            title="Teacher snapshot"
            items={[
              { label: 'Progress signal', value: summary.progress.signal },
              { label: 'Strategy signal', value: summary.strategy.signal },
              { label: 'Flow type', value: flow.flow_type },
              { label: 'Current phase', value: flow.current_phase },
              { label: 'Curriculum status', value: progression.status },
              { label: 'Proposal status', value: intervention.proposal_status },
            ]}
          />
        </div>
        <div className="panel">
          <SectionHeader
            eyebrow="Execution path"
            title="What the chosen option would do"
            description="Teachers should be able to inspect the concrete backend action, not just a label."
          />
          <MetricList
            title="Selected option"
            items={[
              { label: 'Action kind', value: selectedOption?.continue_action.kind ?? intervention.proposed_action.kind },
              { label: 'Endpoint', value: selectedOption?.continue_action.endpoint ?? intervention.proposed_action.endpoint ?? 'n/a' },
              { label: 'Method', value: selectedOption?.continue_action.method ?? intervention.proposed_action.method ?? 'n/a' },
              { label: 'Content type', value: selectedOption?.continue_action.content_type ?? intervention.proposed_action.content_type ?? 'n/a' },
              { label: 'Target KCs', value: (selectedOption?.continue_action.target_kc_ids ?? intervention.proposed_action.target_kc_ids).join(', ') || 'none' },
            ]}
          />
        </div>
        {showDebugPanels ? (
          <JsonPanel
            title="Debug explainability payload"
            value={{
              summary: {
                progress: summary.progress,
                strategy: summary.strategy,
                state_profile: summary.state_profile,
              },
              current_flow: flow,
              curriculum_progression: progression,
              intervention,
            }}
          />
        ) : null}
      </aside>
    </section>
  )
}

function buildDecisionPayload(
  decision: TeacherInterventionDecision,
  optionId: string | null,
  note: string,
): TeacherInterventionDecisionRequest {
  return {
    decision,
    option_id: decision === 'select_option' ? optionId : null,
    note: note.trim() || null,
  }
}

function labelForDecision(decision: TeacherInterventionDecision): string {
  if (decision === 'select_option') {
    return 'Select option'
  }
  if (decision === 'escalate_human') {
    return 'Escalate human'
  }
  return titleCase(decision)
}

function buttonVariantForDecision(decision: TeacherInterventionDecision): 'default' | 'secondary' | 'outline' {
  if (decision === 'approve') {
    return 'default'
  }
  if (decision === 'select_option') {
    return 'outline'
  }
  return 'secondary'
}
