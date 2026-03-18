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
 * Uses the backend-provided `triage_section` field on each TeacherLearnerCard.
 * The backend owns the categorization decision — the frontend only groups
 * and assigns display metadata (title, description, tone).
 */
export function buildTriageSections(learners: TeacherLearnerCard[]): TriageSection[] {
  const teacherAction = learners.filter((l) => l.triage_section === 'teacher_action')
  const needsAttention = learners.filter((l) => l.triage_section === 'needs_attention')
  const onTrack = learners.filter(
    (l) => l.triage_section !== 'teacher_action' && l.triage_section !== 'needs_attention',
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
 */
export function toneForProgression(status: string): TriageTone {
  if (status.includes('blocked')) return 'warning'
  if (status.includes('active') || status.includes('ready')) return 'success'
  return 'neutral'
}

/**
 * Maps a backend-provided intervention status to a display tone.
 */
export function toneForIntervention(status: string): TriageTone {
  if (status === 'available') return 'accent'
  if (status.includes('unavailable')) return 'neutral'
  return 'warning'
}

/**
 * Selects the most relevant rationale string to display for a learner.
 *
 * Prefers intervention decision status, then curriculum progression rationale,
 * then flow next-step rationale, then flow rationale. A backend-owned
 * `display_rationale` field on TeacherLearnerCard would simplify this.
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
