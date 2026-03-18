import { describe, expect, it } from 'vitest'
import {
  learnerContinueAction,
  learnerFlowType,
  learnerStage,
  learnerArtifact,
  learnerSignal,
  learnerRemediationPhase,
  learnerProgressionAction,
  teacherContinueAction,
  teacherFlowType,
  teacherStage,
  teacherArtifact,
  teacherAttention,
  teacherRemediationPhase,
  teacherProgressionAction,
} from './copy'

describe('learner copy', () => {
  it('translates continue-action kinds to learner-safe language', () => {
    expect(learnerContinueAction('idle')).toBe('All caught up')
    expect(learnerContinueAction('generate_follow_up')).toBe('Continue your lesson')
    expect(learnerContinueAction('advance_remediation')).toBe('Keep practicing')
    expect(learnerContinueAction('continue_socratic')).toBe('Check your understanding')
  })

  it('translates flow types', () => {
    expect(learnerFlowType('generation')).toBe('Lesson')
    expect(learnerFlowType('socratic')).toBe('Understanding check')
    expect(learnerFlowType('remediation')).toBe('Practice session')
  })

  it('translates stages to warm language', () => {
    expect(learnerStage('repair')).toBe('Building foundations')
    expect(learnerStage('bridge')).toBe('Connecting ideas')
    expect(learnerStage('target')).toBe('Learning new skills')
    expect(learnerStage('transfer')).toBe('Applying what you know')
  })

  it('translates artifact kinds', () => {
    expect(learnerArtifact('generated_content')).toBe('Lesson')
    expect(learnerArtifact('socratic_session')).toBe('Understanding check')
  })

  it('translates signal levels', () => {
    expect(learnerSignal('high')).toBe('Going strong')
    expect(learnerSignal('medium')).toBe('On track')
  })

  it('translates remediation phases', () => {
    expect(learnerRemediationPhase('diagnose')).toBe('Understanding the challenge')
    expect(learnerRemediationPhase('practice')).toBe('Practicing')
  })

  it('translates progression actions', () => {
    expect(learnerProgressionAction('hold_repair_target')).toBe('Still working on foundations')
    expect(learnerProgressionAction('advance_to_transfer')).toBe('Ready to apply')
  })

  it('handles null/undefined gracefully', () => {
    expect(learnerContinueAction(null)).toBe('All caught up')
    expect(learnerContinueAction(undefined)).toBe('All caught up')
    expect(learnerFlowType(null)).toBe('Activity')
    expect(learnerStage(null)).toBe('Learning')
  })

  it('falls back to title-cased value for unknown keys', () => {
    // learnerProgressionAction has no explicit fallback, so unknown keys get title-cased
    expect(learnerProgressionAction('some_new_action')).toBe('Some New Action')
    expect(teacherStage('exploration')).toBe('Exploration')
  })
})

describe('teacher copy', () => {
  it('translates continue-action kinds to teacher language', () => {
    expect(teacherContinueAction('idle')).toBe('No pending action')
    expect(teacherContinueAction('generate_follow_up')).toBe('Next generated lesson')
    expect(teacherContinueAction('advance_remediation')).toBe('Remediation in progress')
  })

  it('translates flow types', () => {
    expect(teacherFlowType('generation')).toBe('Generation')
    expect(teacherFlowType('socratic')).toBe('Socratic assessment')
    expect(teacherFlowType('remediation')).toBe('Remediation')
  })

  it('translates stages', () => {
    expect(teacherStage('repair')).toBe('Repair')
    expect(teacherStage('transfer')).toBe('Transfer')
  })

  it('translates artifact kinds', () => {
    expect(teacherArtifact('generated_content')).toBe('Generated content')
    expect(teacherArtifact('socratic_session')).toBe('Socratic session')
  })

  it('translates attention levels', () => {
    expect(teacherAttention('high')).toBe('Urgent')
    expect(teacherAttention('none')).toBe('On track')
  })

  it('translates remediation phases', () => {
    expect(teacherRemediationPhase('diagnose')).toBe('Diagnosis')
    expect(teacherRemediationPhase('verify')).toBe('Verification')
  })

  it('translates progression actions', () => {
    expect(teacherProgressionAction('hold_repair_target')).toBe('Held at repair')
    expect(teacherProgressionAction('advance_to_target')).toBe('Advancing to target')
  })
})
