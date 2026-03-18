import type {
  GeneratedBlock,
  GenerationRequestPayload,
  GenerationStreamEvent,
  LearnerWorkspace,
} from '../types'
import type { GenerationFormState, RemediationFormState, SocraticFormState } from '../app/workspace'

export function parseList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function nullableText(value: string): string | null {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

export function nullableNumber(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }

  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

export function buildGenerationPayload(
  learnerId: string,
  form: {
    learning_session_id: string
    target_kc_ids: string
    target_lo_ids: string
    intent: string
    requested_content_type: string
    learner_prompt: string
    curriculum_context: string
  },
): GenerationRequestPayload {
  return {
    student_id: learnerId,
    learning_session_id: nullableText(form.learning_session_id),
    target_kc_ids: parseList(form.target_kc_ids),
    target_lo_ids: parseList(form.target_lo_ids),
    intent: form.intent,
    requested_content_type: nullableText(form.requested_content_type),
    learner_prompt: nullableText(form.learner_prompt),
    curriculum_context: parseList(form.curriculum_context),
  }
}

export function buildGenerationFormFromWorkspace(
  workspace: LearnerWorkspace,
  fallback: GenerationFormState,
): GenerationFormState {
  const action = workspace.continue_action
  const payload = action.request_payload

  return {
    learning_session_id:
      action.learning_session_id ??
      readString(payload, 'learning_session_id') ??
      fallback.learning_session_id,
    target_kc_ids: joinList(preferList(action.target_kc_ids, readStringList(payload, 'target_kc_ids'))) || fallback.target_kc_ids,
    target_lo_ids: joinList(readStringList(payload, 'target_lo_ids')) || fallback.target_lo_ids,
    intent: readString(payload, 'intent') ?? fallback.intent,
    requested_content_type:
      readString(payload, 'requested_content_type') ??
      action.content_type ??
      fallback.requested_content_type,
    learner_prompt: readString(payload, 'learner_prompt') ?? fallback.learner_prompt,
    curriculum_context:
      joinList(readStringList(payload, 'curriculum_context')) || fallback.curriculum_context,
  }
}

export function buildSocraticFormFromWorkspace(
  workspace: LearnerWorkspace,
  fallback: SocraticFormState,
): SocraticFormState {
  const session = workspace.socratic_session
  const action = workspace.continue_action
  const payload = action.request_payload

  return {
    session_id:
      session?.session_id ??
      workspace.summary.current_flow.socratic_session_id ??
      fallback.session_id,
    learning_session_id:
      session?.learning_session_id ??
      action.learning_session_id ??
      readString(payload, 'learning_session_id') ??
      fallback.learning_session_id,
    target_kc_ids:
      joinList(preferList(session?.target_kc_ids, action.target_kc_ids)) || fallback.target_kc_ids,
    target_lo_ids:
      joinList(preferList(session?.target_lo_ids, readStringList(payload, 'target_lo_ids'))) ||
      fallback.target_lo_ids,
    curriculum_context:
      joinList(
        preferList(session?.curriculum_context, readStringList(payload, 'curriculum_context')),
      ) || fallback.curriculum_context,
    learner_response: fallback.learner_response,
    learner_confidence: fallback.learner_confidence,
  }
}

export function buildRemediationFormFromWorkspace(
  workspace: LearnerWorkspace,
  fallback: RemediationFormState,
): RemediationFormState {
  const session = workspace.remediation_session
  const action = session?.summary.continue_action ?? workspace.continue_action
  const payload = action.request_payload

  return {
    target_kc_id:
      session?.target_kc_id ??
      action.target_kc_ids[0] ??
      fallback.target_kc_id,
    misconception_description:
      session?.misconception_description ?? fallback.misconception_description,
    learner_prompt: readString(payload, 'learner_prompt') ?? fallback.learner_prompt,
    curriculum_context:
      joinList(
        preferList(session?.curriculum_context, readStringList(payload, 'curriculum_context')),
      ) || fallback.curriculum_context,
  }
}

export function buildRemediationAdvancePromptFromWorkspace(
  workspace: LearnerWorkspace,
  fallback: string,
): string {
  const action = workspace.remediation_session?.summary.continue_action ?? workspace.continue_action
  return readString(action.request_payload, 'learner_prompt') ?? fallback
}

export function applyStreamChunk(
  existing: GeneratedBlock[],
  chunk: NonNullable<GenerationStreamEvent['chunk']>,
): GeneratedBlock[] {
  const next = [...existing]
  const current = next[chunk.block_index]

  if (!current) {
    next[chunk.block_index] = {
      kind: chunk.kind,
      title: chunk.title,
      body: chunk.body_delta,
    }
    return next
  }

  next[chunk.block_index] = {
    ...current,
    body: `${current.body}${chunk.body_delta}`,
  }
  return next
}

function preferList(primary: string[] | null | undefined, secondary: string[] | null | undefined): string[] {
  if (primary && primary.length > 0) {
    return primary
  }
  return secondary ?? []
}

function readString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key]
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function readStringList(payload: Record<string, unknown>, key: string): string[] {
  const value = payload[key]
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
  }
  if (typeof value === 'string') {
    return parseList(value)
  }
  return []
}

function joinList(values: string[] | null | undefined): string {
  return values?.join(', ') ?? ''
}
