import { describe, expect, it } from 'vitest'

import {
  formatArtifactKind,
  formatAttentionReason,
  formatContentType,
  formatContinueAction,
  formatContractLabel,
} from './formatters'

describe('formatters', () => {
  it('humanizes backend-owned contract labels for product-facing views', () => {
    expect(formatContractLabel('hold_repair_target')).toBe('Hold Repair Target')
    expect(formatContentType('practice_problem')).toBe('Practice Problem')
    expect(formatContentType(null)).toBe('Monitor')
    expect(formatArtifactKind('generated_content')).toBe('Generated content')
    expect(formatContinueAction('generate_follow_up')).toBe('Continue generated content')
    expect(formatContinueAction('idle')).toBe('No immediate action')
    expect(formatAttentionReason('teacher_intervention_available')).toBe('Teacher intervention ready')
  })
})
