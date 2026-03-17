import type {
  FrontendConfig,
  GeneratedContent,
  GenerationRequestPayload,
  GenerationStreamEvent,
  LearnerFlowSummary,
  LearnerProfileV2,
  ProfileSummary,
  RemediationWorkflowAdvanceResponse,
  RemediationWorkflowSession,
  SocraticAssessmentResponse,
  SocraticAssessmentSession,
} from './types'

function buildHeaders(config: FrontendConfig, contentType = true): HeadersInit {
  const headers: Record<string, string> = {}

  if (contentType) {
    headers['Content-Type'] = 'application/json'
  }

  if (config.bearerToken.trim()) {
    headers.Authorization = `Bearer ${config.bearerToken.trim()}`
  } else if (config.apiKey.trim()) {
    headers['X-API-Key'] = config.apiKey.trim()
  }

  return headers
}

async function requestJson<T>(
  config: FrontendConfig,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${config.baseUrl}${path}`, init)
  if (!response.ok) {
    throw new Error(await extractError(response))
  }
  return (await response.json()) as T
}

async function extractError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ?? `${response.status} ${response.statusText}`
  } catch {
    return `${response.status} ${response.statusText}`
  }
}

export function getLearners(config: FrontendConfig) {
  return requestJson<string[]>(config, '/api/learners', {
    headers: buildHeaders(config, false),
  })
}

export function getLearnerSummary(config: FrontendConfig, studentId: string) {
  return requestJson<ProfileSummary>(config, `/api/learners/${studentId}/summary`, {
    headers: buildHeaders(config, false),
  })
}

export function getLearnerProfile(config: FrontendConfig, studentId: string) {
  return requestJson<LearnerProfileV2>(config, `/api/learners/${studentId}/profile`, {
    headers: buildHeaders(config, false),
  })
}

export function getLearnerFlow(config: FrontendConfig, studentId: string) {
  return requestJson<LearnerFlowSummary>(config, `/api/learners/${studentId}/flow`, {
    headers: buildHeaders(config, false),
  })
}

export function generateContent(config: FrontendConfig, payload: GenerationRequestPayload) {
  return requestJson<GeneratedContent>(config, '/api/content/generate', {
    method: 'POST',
    headers: buildHeaders(config),
    body: JSON.stringify(payload),
  })
}

export function runSocraticAssessment(
  config: FrontendConfig,
  payload: {
    student_id: string
    session_id?: string | null
    learning_session_id?: string | null
    target_kc_ids: string[]
    target_lo_ids: string[]
    curriculum_context: string[]
    learner_response?: string | null
    learner_confidence?: number | null
    conversation_history?: Array<{ role: string; text: string }>
  },
) {
  return requestJson<SocraticAssessmentResponse>(config, '/api/assessments/socratic', {
    method: 'POST',
    headers: buildHeaders(config),
    body: JSON.stringify(payload),
  })
}

export function getSocraticSession(config: FrontendConfig, sessionId: string) {
  return requestJson<SocraticAssessmentSession>(config, `/api/assessments/socratic/${sessionId}`, {
    headers: buildHeaders(config, false),
  })
}

export function triggerRemediation(
  config: FrontendConfig,
  payload: {
    student_id: string
    target_kc_id: string
    misconception_description: string
    learner_prompt?: string | null
    curriculum_context: string[]
  },
) {
  return requestJson<GeneratedContent>(config, '/api/remedial/trigger', {
    method: 'POST',
    headers: buildHeaders(config),
    body: JSON.stringify(payload),
  })
}

export function getRemediationSession(config: FrontendConfig, sessionId: string) {
  return requestJson<RemediationWorkflowSession>(config, `/api/remedial/sessions/${sessionId}`, {
    headers: buildHeaders(config, false),
  })
}

export function advanceRemediationSession(
  config: FrontendConfig,
  sessionId: string,
  payload: {
    learner_prompt?: string | null
    curriculum_context: string[]
  },
) {
  return requestJson<RemediationWorkflowAdvanceResponse>(
    config,
    `/api/remedial/sessions/${sessionId}/advance`,
    {
      method: 'POST',
      headers: buildHeaders(config),
      body: JSON.stringify(payload),
    },
  )
}

export async function streamGeneration(
  config: FrontendConfig,
  payload: GenerationRequestPayload,
  onEvent: (event: GenerationStreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${config.baseUrl}/api/llm/stream`, {
    method: 'POST',
    headers: {
      ...buildHeaders(config),
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(await extractError(response))
  }

  if (!response.body) {
    throw new Error('Streaming is unavailable because the response body is empty.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''

    for (const part of parts) {
      const parsed = parseSseRecord(part)
      if (parsed) {
        onEvent(parsed)
      }
    }
  }

  const trailing = buffer.trim()
  if (trailing) {
    const parsed = parseSseRecord(trailing)
    if (parsed) {
      onEvent(parsed)
    }
  }
}

function parseSseRecord(record: string): GenerationStreamEvent | null {
  let eventName = ''
  let data = ''

  for (const line of record.split('\n')) {
    if (line.startsWith('event: ')) {
      eventName = line.slice(7).trim()
    }
    if (line.startsWith('data: ')) {
      data += line.slice(6)
    }
  }

  if (!data) {
    return null
  }

  const payload = JSON.parse(data) as Omit<GenerationStreamEvent, 'event'>
  return {
    event: eventName || 'message',
    ...payload,
  }
}
