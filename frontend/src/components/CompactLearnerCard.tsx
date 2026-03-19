import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Pill } from '../components/primitives'
import { labelForView, resolveContinueActionView } from '../app/workspace'
import {
  formatAttentionReason,
  formatContinueAction,
  formatContractLabel,
} from '../lib/formatters'
import type { TeacherLearnerCard } from '../types'

function toneForProgression(status: string): 'accent' | 'success' | 'warning' | 'danger' | 'neutral' {
  if (status.includes('blocked')) return 'warning'
  if (status.includes('active') || status.includes('ready')) return 'success'
  return 'neutral'
}

function toneForIntervention(status: string): 'accent' | 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'available') return 'accent'
  if (status.includes('unavailable')) return 'neutral'
  return 'warning'
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

export function CompactLearnerCard({
  learner,
  isOpening,
  onOpenTeacher,
  onContinueLearner,
}: {
  learner: TeacherLearnerCard
  isOpening: boolean
  onOpenTeacher: (studentId: string) => void
  onContinueLearner: (studentId: string, continueActionKind: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const continueView = resolveContinueActionView(learner.current_flow.continue_action.kind)

  return (
    <article className="history-card triage-card !p-3">
      <div className="flex items-center gap-3 flex-wrap">
        <button
          type="button"
          className="shrink-0 cursor-pointer bg-transparent border-none p-0"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          aria-label={`${expanded ? 'Collapse' : 'Expand'} details for ${learner.student_id}`}
        >
          <ChevronRight
            className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
          />
        </button>
        <strong className="text-sm truncate max-w-[180px]">{learner.student_id}</strong>
        <span className="text-xs text-muted-foreground">Grade {learner.grade_level}</span>
        <div className="flex flex-wrap gap-1.5 items-center">
          <Pill label={formatContractLabel(learner.current_flow.flow_type)} tone="neutral" />
          <Pill
            label={formatContractLabel(learner.curriculum_progression.status)}
            tone={toneForProgression(learner.curriculum_progression.status)}
          />
          <Pill
            label={formatContractLabel(learner.intervention.proposal_status)}
            tone={toneForIntervention(learner.intervention.proposal_status)}
          />
          {learner.attention_reasons.map((reason) => (
            <Pill key={reason} label={formatAttentionReason(reason)} tone="warning" />
          ))}
        </div>
        <div className="flex items-center gap-2 ml-auto shrink-0">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenTeacher(learner.student_id)}
            disabled={isOpening}
            className="text-xs h-7 px-2"
          >
            {isOpening ? 'Opening...' : 'Triage'}
          </Button>
          {continueView ? (
            <Button
              type="button"
              size="sm"
              onClick={() =>
                onContinueLearner(learner.student_id, learner.current_flow.continue_action.kind)
              }
              disabled={isOpening}
              className="text-xs h-7 px-2"
            >
              {isOpening ? 'Opening...' : `Continue`}
            </Button>
          ) : null}
        </div>
      </div>
      {expanded ? (
        <div className="mt-3 animate-fade-in">
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
          <p className="mt-2 text-sm">{describeLearnerRationale(learner)}</p>
        </div>
      ) : null}
    </article>
  )
}
