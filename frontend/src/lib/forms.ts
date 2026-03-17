import type { GeneratedBlock, GenerationRequestPayload, GenerationStreamEvent } from '../types'

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
