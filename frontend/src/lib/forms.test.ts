import { describe, expect, it } from 'vitest'

import { applyStreamChunk, buildGenerationPayload, nullableNumber, nullableText, parseList } from './forms'

describe('forms helpers', () => {
  it('parses comma-separated lists into trimmed values', () => {
    expect(parseList(' KC-1, KC-2, , KC-3 ')).toEqual(['KC-1', 'KC-2', 'KC-3'])
  })

  it('normalizes optional text and numbers', () => {
    expect(nullableText('  learner note  ')).toBe('learner note')
    expect(nullableText('   ')).toBeNull()
    expect(nullableNumber(' 0.76 ')).toBe(0.76)
    expect(nullableNumber('not-a-number')).toBeNull()
    expect(nullableNumber('')).toBeNull()
  })

  it('builds a generation payload from form state', () => {
    expect(
      buildGenerationPayload('student-1', {
        learning_session_id: ' session-1 ',
        target_kc_ids: 'KC-1, KC-2',
        target_lo_ids: 'LO-1',
        intent: 'practice',
        requested_content_type: 'worked_example',
        learner_prompt: ' Keep it supportive ',
        curriculum_context: 'Equivalent fractions, area models',
      }),
    ).toEqual({
      student_id: 'student-1',
      learning_session_id: 'session-1',
      target_kc_ids: ['KC-1', 'KC-2'],
      target_lo_ids: ['LO-1'],
      intent: 'practice',
      requested_content_type: 'worked_example',
      learner_prompt: 'Keep it supportive',
      curriculum_context: ['Equivalent fractions', 'area models'],
    })
  })

  it('accumulates stream chunks into ordered generated blocks', () => {
    const withFirstChunk = applyStreamChunk([], {
      block_index: 0,
      kind: 'hint',
      title: 'Bridge move',
      body_delta: 'Start from one whole.',
      done: false,
    })

    expect(withFirstChunk).toEqual([
      {
        kind: 'hint',
        title: 'Bridge move',
        body: 'Start from one whole.',
      },
    ])

    expect(
      applyStreamChunk(withFirstChunk, {
        block_index: 0,
        kind: 'hint',
        title: 'Bridge move',
        body_delta: ' Then partition it equally.',
        done: true,
      }),
    ).toEqual([
      {
        kind: 'hint',
        title: 'Bridge move',
        body: 'Start from one whole. Then partition it equally.',
      },
    ])
  })
})
