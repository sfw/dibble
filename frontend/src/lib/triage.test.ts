import { describe, expect, it } from 'vitest'
import { buildTriageSections, describeLearnerRationale, toneForIntervention, toneForProgression } from './triage'
import type { TeacherLearnerCard } from '../types'

function makeLearnerCard(overrides: Partial<{
  triage_section: string
}>): TeacherLearnerCard {
  return {
    student_id: 'student-1',
    grade_level: '5',
    engagement: 'medium',
    frustration: 'low',
    current_flow: {
      status: 'active',
      flow_type: 'generation',
      current_phase: 'target',
      progression_action: 'hold_target',
      target_stage: 'target',
      active_target_kc_ids: ['KC-1'],
      deferred_target_kc_ids: [],
      transfer_target_kc_ids: [],
      session_phase: 'active',
      session_arc_action: 'continue',
      session_stuck_loop_risk: 'none',
      progression_source: 'backend',
      next_step_source: 'backend',
      next_step: {
        action: 'generate',
        target_stage: 'target',
        target_kc_ids: ['KC-1'],
      },
      continue_action: {
        kind: 'generate_follow_up',
        target_stage: 'target',
        target_kc_ids: ['KC-1'],
        request_payload: {},
      },
    },
    curriculum_progression: {
      status: 'active',
      source: 'backend',
      flow_type: 'generation',
      current_stage: 'target',
      progression_action: 'hold_target',
      active_target_kc_ids: ['KC-1'],
      outcome_count: 10,
      mastered_outcome_count: 3,
      ready_outcome_count: 2,
      blocked_outcome_count: 0,
      active_outcome_count: 1,
      mastered_outcome_ratio: 0.3,
      blocked_outcomes: [],
      ready_outcomes: [],
    },
    recent_activity: {
      generation_count: 5,
      observation_count: 10,
      socratic_assessment_count: 2,
    },
    intervention: {
      action_key: 'action-1',
      proposal_status: 'unavailable',
      recommended_action_kind: 'generate_follow_up',
      option_count: 2,
    },
    attention_level: 'low',
    triage_section: overrides.triage_section ?? 'on_track',
    attention_reasons: [],
  }
}

describe('buildTriageSections', () => {
  it('sorts teacher_action learners into the first section', () => {
    const learners = [makeLearnerCard({ triage_section: 'teacher_action' })]
    const sections = buildTriageSections(learners)
    expect(sections[0].key).toBe('teacher-action')
    expect(sections[0].learners).toHaveLength(1)
    expect(sections[1].learners).toHaveLength(0)
    expect(sections[2].learners).toHaveLength(0)
  })

  it('sorts needs_attention learners into the second section', () => {
    const learners = [makeLearnerCard({ triage_section: 'needs_attention' })]
    const sections = buildTriageSections(learners)
    expect(sections[0].learners).toHaveLength(0)
    expect(sections[1].key).toBe('needs-attention')
    expect(sections[1].learners).toHaveLength(1)
    expect(sections[2].learners).toHaveLength(0)
  })

  it('sorts on_track learners into the third section', () => {
    const learners = [makeLearnerCard({ triage_section: 'on_track' })]
    const sections = buildTriageSections(learners)
    expect(sections[2].key).toBe('on-track')
    expect(sections[2].learners).toHaveLength(1)
  })

  it('falls back to on-track for unknown triage_section values', () => {
    const learners = [makeLearnerCard({ triage_section: 'something_new' })]
    const sections = buildTriageSections(learners)
    expect(sections[2].learners).toHaveLength(1)
  })
})

describe('toneForProgression', () => {
  it('returns warning for blocked', () => {
    expect(toneForProgression('blocked_on_prereqs')).toBe('warning')
  })

  it('returns success for active', () => {
    expect(toneForProgression('active')).toBe('success')
  })

  it('returns neutral for unknown', () => {
    expect(toneForProgression('something')).toBe('neutral')
  })
})

describe('toneForIntervention', () => {
  it('returns accent for available', () => {
    expect(toneForIntervention('available')).toBe('accent')
  })

  it('returns neutral for unavailable', () => {
    expect(toneForIntervention('unavailable')).toBe('neutral')
  })
})

describe('describeLearnerRationale', () => {
  it('prefers backend display_rationale when present', () => {
    const learner = makeLearnerCard({})
    learner.display_rationale = 'Backend-owned canonical rationale.'
    learner.curriculum_progression.rationale = 'Should not be used'
    expect(describeLearnerRationale(learner)).toBe('Backend-owned canonical rationale.')
  })

  it('shows latest decision status when present and no display_rationale', () => {
    const learner = makeLearnerCard({})
    learner.intervention.latest_decision_status = 'approved'
    expect(describeLearnerRationale(learner)).toContain('Approved')
  })

  it('falls back to progression rationale', () => {
    const learner = makeLearnerCard({})
    learner.curriculum_progression.rationale = 'Holding at target'
    expect(describeLearnerRationale(learner)).toBe('Holding at target')
  })
})
