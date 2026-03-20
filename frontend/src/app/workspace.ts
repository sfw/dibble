export type ViewKey = 'overview' | 'generation' | 'socratic' | 'remediation' | 'teacher' | 'classroom'
export type DataSource = 'live' | 'demo'

export function labelForView(view: ViewKey): string {
  if (view === 'generation') {
    return 'generated content'
  }
  if (view === 'socratic') {
    return 'Socratic'
  }
  if (view === 'remediation') {
    return 'remediation'
  }
  if (view === 'teacher') {
    return 'teacher triage'
  }
  if (view === 'classroom') {
    return 'classroom'
  }

  return 'learner overview'
}

export function resolveContinueActionView(kind: string | null | undefined): ViewKey | null {
  if (!kind) {
    return null
  }

  if (kind === 'continue_socratic') {
    return 'socratic'
  }
  if (kind === 'advance_remediation') {
    return 'remediation'
  }
  if (kind === 'generate_follow_up') {
    return 'generation'
  }

  return null
}

export function resolveArtifactView(kind: string | null | undefined): ViewKey | null {
  if (!kind) {
    return null
  }

  if (kind === 'generated_content') {
    return 'generation'
  }
  if (kind === 'socratic_session') {
    return 'socratic'
  }
  if (kind === 'remediation_session') {
    return 'remediation'
  }

  return null
}

export interface GenerationFormState {
  learning_session_id: string
  target_kc_ids: string
  target_lo_ids: string
  intent: string
  requested_content_type: string
  learner_prompt: string
  curriculum_context: string
}

export const initialGenerationForm: GenerationFormState = {
  learning_session_id: 'session-fractions-bridge',
  target_kc_ids: 'KC-1',
  target_lo_ids: 'LO-1',
  intent: 'explanation',
  requested_content_type: '',
  learner_prompt: 'Use a supportive tone and name the transfer move explicitly.',
  curriculum_context: 'Equivalent fractions',
}

export interface SocraticFormState {
  session_id: string
  learning_session_id: string
  target_kc_ids: string
  target_lo_ids: string
  curriculum_context: string
  learner_response: string
  learner_confidence: string
}

export const initialSocraticForm: SocraticFormState = {
  session_id: 'soc-demo-1',
  learning_session_id: 'session-fractions-bridge',
  target_kc_ids: 'KC-1',
  target_lo_ids: 'LO-1',
  curriculum_context: 'Equivalent fractions',
  learner_response:
    'The amount stays the same because the whole does not change, only the number of equal parts changes.',
  learner_confidence: '0.76',
}

export interface RemediationFormState {
  target_kc_id: string
  misconception_description: string
  learner_prompt: string
  curriculum_context: string
}

export const initialRemediationForm: RemediationFormState = {
  target_kc_id: 'KC-2',
  misconception_description:
    'The learner compares numerator and denominator separately instead of comparing the same whole amount.',
  learner_prompt: 'Step back to one whole model before returning to the target.',
  curriculum_context: 'Equivalent fractions',
}

export const initialRemediationAdvancePrompt =
  'Advance only if the learner can explain the whole correctly without relying on numerator-only cues.'
