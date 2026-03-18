import type { TeacherLearnerCard } from '../types'

export type TriageTone = 'accent' | 'success' | 'warning' | 'danger' | 'neutral'

export interface TriageSection {
  key: string
  title: string
  description: string
  tone: TriageTone
  learners: TeacherLearnerCard[]
}

/**
 * Groups learners into triage sections for teacher review.
 *
 * BACKEND-OWNED DECISION: Triage categorization should be a backend responsibility.
 * The backend already provides `attention_level` and `intervention.proposal_status`
 * on each TeacherLearnerCard. This function groups by those backend-provided fields
 * rather than re-deriving categories from raw progression or attention data.
 *
 * When the backend provides a `triage_section` field on TeacherLearnerCard, this
 * function should simply group by that field and stop interpreting signals locally.
 */
export function buildTriageSections(learners: TeacherLearnerCard[]): TriageSection[] {
  // Group by backend-provided attention_level and intervention status.
  // The backend owns the decision about which learners need attention — we only
  // sort into display groups based on the backend's classification.
  const teacherAction = learners.filter(
    (learner) => learner.intervention.proposal_status === 'available',
  )
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
      title: 'Needs teacher action',
      description: 'Intervention proposals ready for review.',
      tone: 'accent',
      learners: teacherAction,
    },
    {
      key: 'needs-attention',
      title: 'Needs attention',
      description: 'Learners flagged by the system for monitoring.',
      tone: 'warning',
      learners: needsAttention,
    },
    {
      key: 'on-track',
      title: 'On track',
      description: 'Learners progressing through their next step.',
      tone: 'success',
      learners: onTrack,
    },
  ]
}

/**
 * Maps a backend-provided progression status to a display tone.
 *
 * TEMPORARY SHIM: The backend should provide a `progression_tone` or equivalent
 * field so the frontend does not interpret status strings.
 */
export function toneForProgression(status: string): TriageTone {
  if (status.includes('blocked')) return 'warning'
  if (status.includes('active') || status.includes('ready')) return 'success'
  return 'neutral'
}

/**
 * Maps a backend-provided intervention status to a display tone.
 *
 * TEMPORARY SHIM: The backend should provide a display tone alongside the status.
 */
export function toneForIntervention(status: string): TriageTone {
  if (status === 'available') return 'accent'
  if (status.includes('unavailable')) return 'neutral'
  return 'warning'
}

/**
 * Selects the most relevant rationale string to display for a learner.
 *
 * TEMPORARY SHIM: The backend should provide a single `display_rationale` field
 * on TeacherLearnerCard so the frontend does not choose between rationale sources.
 */
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
