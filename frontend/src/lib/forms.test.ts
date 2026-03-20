import { describe, expect, it } from 'vitest'

import { initialGenerationForm, initialRemediationAdvancePrompt, initialRemediationForm, initialSocraticForm } from '../app/workspace'
import { demoLearnerWorkspace } from '../sample-data'
import {
  applyStreamChunk,
  buildGenerationFormFromWorkspace,
  buildGenerationPayload,
  buildRemediationAdvancePromptFromWorkspace,
  buildRemediationFormFromWorkspace,
  buildSocraticFormFromWorkspace,
  nullableNumber,
  nullableText,
  parseList,
} from './forms'

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

  it('hydrates generation, Socratic, and remediation forms from learner workspace contracts', () => {
    expect(buildGenerationFormFromWorkspace(demoLearnerWorkspace, initialGenerationForm)).toEqual({
      learning_session_id: 'session-fractions-bridge',
      target_kc_ids: 'KC-1',
      target_lo_ids: 'LO-1',
      intent: 'practice',
      requested_content_type: 'practice_problem',
      learner_prompt: initialGenerationForm.learner_prompt,
      curriculum_context: 'Equivalent fractions',
    })

    expect(buildSocraticFormFromWorkspace(demoLearnerWorkspace, initialSocraticForm)).toEqual({
      session_id: 'soc-demo-1',
      learning_session_id: 'session-fractions-bridge',
      target_kc_ids: 'KC-1',
      target_lo_ids: 'LO-1',
      curriculum_context: 'Equivalent fractions',
      learner_response: initialSocraticForm.learner_response,
      learner_confidence: initialSocraticForm.learner_confidence,
    })

    expect(buildRemediationFormFromWorkspace(demoLearnerWorkspace, initialRemediationForm)).toEqual({
      target_kc_id: 'KC-2',
      misconception_description:
        'The learner compares numerator and denominator separately instead of the full amount.',
      learner_prompt:
        'Advance only if the learner explains the whole correctly without relying on numerator-only cues.',
      curriculum_context: 'Equivalent fractions',
    })
    expect(
      buildRemediationAdvancePromptFromWorkspace(demoLearnerWorkspace, initialRemediationAdvancePrompt),
    ).toBe('Advance only if the learner explains the whole correctly without relying on numerator-only cues.')
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

  it('replaces a streamed block when the chunk carries a full block payload', () => {
    expect(
      applyStreamChunk([], {
        block_index: 0,
        kind: '',
        title: '',
        body_delta: '',
        block: {
          block_id: 'block-1',
          kind: 'practice_problem',
          title: 'Choose the Setup',
          body: 'Select the correct setup.',
          interaction: {
            type: 'multiple_choice',
            prompt: 'Which setup preserves place value?',
            options: [
              { option_id: 'A', label: 'Option A', body: 'Misaligned digits.' },
              { option_id: 'B', label: 'Option B', body: 'Aligned decimals.' },
            ],
            correct_option_id: 'B',
            reveal: {
              trigger: 'after_selection',
              prompt: 'Explain why the decimal points align.',
              support: 'Keep tenths under tenths.',
              placeholder: 'Explain your thinking.',
            },
            allow_retry: false,
          },
        },
        done: true,
      }),
    ).toEqual([
      {
        block_id: 'block-1',
        kind: 'practice_problem',
        title: 'Choose the Setup',
        body: 'Select the correct setup.',
        interaction: {
          type: 'multiple_choice',
          prompt: 'Which setup preserves place value?',
          options: [
            { option_id: 'A', label: 'Option A', body: 'Misaligned digits.' },
            { option_id: 'B', label: 'Option B', body: 'Aligned decimals.' },
          ],
          correct_option_id: 'B',
          reveal: {
            trigger: 'after_selection',
            prompt: 'Explain why the decimal points align.',
            support: 'Keep tenths under tenths.',
            placeholder: 'Explain your thinking.',
          },
          allow_retry: false,
        },
      },
    ])
  })
})
