import type { TeacherLearnerCard } from '../types'

export type TriageTone = 'accent' | 'success' | 'warning' | 'danger' | 'neutral'

export interface TriageSection {
  key: string
  title: string
  description: string
  tone: TriageTone
  learners: TeacherLearnerCard[]
}

export function buildTriageSections(learners: TeacherLearnerCard[]): TriageSection[] {
  const teacherAction = learners.filter(
    (learner) => learner.intervention.proposal_status === 'available',
  )
  const blocked = learners.filter(
    (learner) =>
      learner.intervention.proposal_status !== 'available' &&
      (learner.curriculum_progression.status.includes('blocked') ||
        learner.attention_reasons.some((reason) => reason.includes('blocked'))),
  )
  const continuing = learners.filter(
    (learner) => !teacherAction.includes(learner) && !blocked.includes(learner),
  )

  return [
    {
      key: 'teacher-action',
      title: 'Needs teacher action',
      description: 'Intervention proposals ready for review.',
      tone: 'accent',
      learners: teacherAction,
    },
    {
      key: 'blocked',
      title: 'Blocked progression',
      description: 'Learners stalled by prerequisites or progression gates.',
      tone: 'warning',
      learners: blocked,
    },
    {
      key: 'continuing',
      title: 'On track',
      description: 'Learners ready for their next step.',
      tone: 'success',
      learners: continuing,
    },
  ]
}

export function toneForProgression(status: string): TriageTone {
  if (status.includes('blocked')) return 'warning'
  if (status.includes('active') || status.includes('ready')) return 'success'
  return 'neutral'
}

export function toneForIntervention(status: string): TriageTone {
  if (status === 'available') return 'accent'
  if (status.includes('unavailable')) return 'neutral'
  return 'warning'
}

export function describeLearnerRationale(learner: TeacherLearnerCard): string {
  if (learner.intervention.latest_decision_status) {
    const status = learner.intervention.latest_decision_status
      .split(/[_-]/g)
      .filter(Boolean)
      .map((t) => t.charAt(0).toUpperCase() + t.slice(1))
      .join(' ')
    return `Latest teacher decision: ${status}.`
  }
  return (
    learner.curriculum_progression.rationale ??
    learner.current_flow.next_step.rationale ??
    learner.current_flow.rationale ??
    'No rationale available.'
  )
}
