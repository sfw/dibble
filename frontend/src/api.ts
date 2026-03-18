import type {
  BulkUserCreateRequest,
  BulkUserCreateResponse,
  CreateInitialAdminRequest,
  CreateInitialAdminResponse,
  SetupConfigureRequest,
  SetupConfigureResponse,
  SetupStatus,
  UserCreateRequest,
  UserCreateResponse,
  UserSummary,
  UserUpdateRequest,
  Assignment,
  AssignmentCreate,
  AssignmentPage,
  AssignmentStatus,
  AuthIdentity,
  AuthToken,
  ClassroomMasteryTrendsResponse,
  FrontendConfig,
  GeneratedContent,
  GenerationRequestPayload,
  GenerationStreamEvent,
  LearnerCurriculumProgressionSummary,
  LearnerGenerationHistoryPage,
  LearnerFlowSummary,
  LearnerProfileV2,
  LearnerRemediationSessionHistoryPage,
  LearnerSocraticSessionHistoryPage,
  LearnerWorkspace,
  MasteryHistoryResponse,
  ProfileSummary,
  RemediationWorkflowAdvanceResponse,
  RemediationWorkflowSession,
  SocraticAssessmentResponse,
  SocraticAssessmentSession,
  TeacherClassroomOverview,
  TeacherClassroomReadModel,
  TeacherInterventionActionContract,
  TeacherInterventionDecisionRequest,
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
  const headerCode = response.headers.get('X-Dibble-Error-Code')
  try {
    const payload = (await response.json()) as { detail?: string; code?: string }
    const code = payload.code ?? headerCode
    if (code && payload.detail) {
      return `${payload.detail} (${code})`
    }
    return payload.detail ?? code ?? `${response.status} ${response.statusText}`
  } catch {
    return headerCode ? `${response.status} ${response.statusText} (${headerCode})` : `${response.status} ${response.statusText}`
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

export function getLearnerWorkspace(config: FrontendConfig, studentId: string) {
  return requestJson<LearnerWorkspace>(config, `/api/learners/${studentId}/workspace`, {
    headers: buildHeaders(config, false),
  })
}

export function getLearnerProgression(config: FrontendConfig, studentId: string) {
  return requestJson<LearnerCurriculumProgressionSummary>(
    config,
    `/api/learners/${studentId}/progression`,
    {
      headers: buildHeaders(config, false),
    },
  )
}

export function getGenerationHistory(config: FrontendConfig, studentId: string, limit = 20, offset = 0) {
  return requestJson<LearnerGenerationHistoryPage>(
    config,
    `/api/learners/${studentId}/history/generations?limit=${limit}&offset=${offset}`,
    {
      headers: buildHeaders(config, false),
    },
  )
}

export function getSocraticHistory(config: FrontendConfig, studentId: string, limit = 20, offset = 0) {
  return requestJson<LearnerSocraticSessionHistoryPage>(
    config,
    `/api/learners/${studentId}/history/socratic-sessions?limit=${limit}&offset=${offset}`,
    {
      headers: buildHeaders(config, false),
    },
  )
}

export function getRemediationHistory(config: FrontendConfig, studentId: string, limit = 20, offset = 0) {
  return requestJson<LearnerRemediationSessionHistoryPage>(
    config,
    `/api/learners/${studentId}/history/remediation-sessions?limit=${limit}&offset=${offset}`,
    {
      headers: buildHeaders(config, false),
    },
  )
}

export function getTeacherInterventionAction(config: FrontendConfig, studentId: string) {
  return requestJson<TeacherInterventionActionContract>(
    config,
    `/api/learners/${studentId}/intervention-action`,
    {
      headers: buildHeaders(config, false),
    },
  )
}

export function getTeacherClassrooms(config: FrontendConfig) {
  return requestJson<TeacherClassroomOverview[]>(config, '/api/teachers/classrooms', {
    headers: buildHeaders(config, false),
  })
}

export function getTeacherClassroom(config: FrontendConfig, classroomId: string) {
  return requestJson<TeacherClassroomReadModel>(config, `/api/teachers/classrooms/${classroomId}`, {
    headers: buildHeaders(config, false),
  })
}

export function recordTeacherInterventionAction(
  config: FrontendConfig,
  studentId: string,
  payload: TeacherInterventionDecisionRequest,
) {
  return requestJson<TeacherInterventionActionContract>(
    config,
    `/api/learners/${studentId}/intervention-action`,
    {
      method: 'POST',
      headers: buildHeaders(config),
      body: JSON.stringify(payload),
    },
  )
}

export function getGeneratedContent(config: FrontendConfig, generationId: string) {
  return requestJson<GeneratedContent>(config, `/api/content/${generationId}`, {
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

export function createAssignment(config: FrontendConfig, payload: AssignmentCreate) {
  return requestJson<Assignment>(config, '/api/assignments', {
    method: 'POST',
    headers: buildHeaders(config),
    body: JSON.stringify(payload),
  })
}

export function getAssignment(config: FrontendConfig, assignmentId: string) {
  return requestJson<Assignment>(config, `/api/assignments/${assignmentId}`, {
    headers: buildHeaders(config, false),
  })
}

export function updateAssignmentStatus(config: FrontendConfig, assignmentId: string, status: AssignmentStatus) {
  return requestJson<Assignment>(config, `/api/assignments/${assignmentId}`, {
    method: 'PATCH',
    headers: buildHeaders(config),
    body: JSON.stringify({ status }),
  })
}

export function getLearnerAssignments(config: FrontendConfig, studentId: string, limit = 20, offset = 0) {
  return requestJson<AssignmentPage>(
    config,
    `/api/learners/${studentId}/assignments?limit=${limit}&offset=${offset}`,
    {
      headers: buildHeaders(config, false),
    },
  )
}

export function getTeacherAssignments(config: FrontendConfig, limit = 50, offset = 0) {
  return requestJson<AssignmentPage>(
    config,
    `/api/teachers/assignments?limit=${limit}&offset=${offset}`,
    {
      headers: buildHeaders(config, false),
    },
  )
}

export function getAuthIdentity(config: FrontendConfig) {
  return requestJson<AuthIdentity>(config, '/api/auth/me', {
    headers: buildHeaders(config, false),
  })
}

export function issueAuthToken(config: FrontendConfig) {
  return requestJson<AuthToken>(config, '/api/auth/token', {
    method: 'POST',
    headers: buildHeaders(config, false),
  })
}

export function refreshAuthToken(config: FrontendConfig, refreshToken: string) {
  return requestJson<AuthToken>(config, '/api/auth/token/refresh', {
    method: 'POST',
    headers: buildHeaders(config),
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
}

export function revokeAuthToken(config: FrontendConfig, refreshToken?: string) {
  return requestJson<{ status: string }>(config, '/api/auth/token/revoke', {
    method: 'POST',
    headers: buildHeaders(config),
    body: JSON.stringify({ refresh_token: refreshToken ?? null }),
  })
}

export function getLearnerMasteryHistory(config: FrontendConfig, studentId: string, days = 30) {
  return requestJson<MasteryHistoryResponse>(config, `/api/learners/${studentId}/mastery-history?days=${days}`)
}

export function getClassroomMasteryTrends(config: FrontendConfig, classroomId: string, days = 30) {
  return requestJson<ClassroomMasteryTrendsResponse>(config, `/api/teachers/classrooms/${classroomId}/mastery-trends?days=${days}`)
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

export async function getSetupStatus(baseUrl: string): Promise<SetupStatus> {
  const response = await fetch(`${baseUrl}/api/setup/status`)
  if (!response.ok) {
    throw new Error(`Setup status request failed: ${response.status}`)
  }
  return (await response.json()) as SetupStatus
}

export async function postSetupConfigure(
  baseUrl: string,
  payload: SetupConfigureRequest,
): Promise<SetupConfigureResponse> {
  const response = await fetch(`${baseUrl}/api/setup/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`Setup configure request failed: ${response.status}`)
  }
  return (await response.json()) as SetupConfigureResponse
}

export async function postSetupAdmin(
  baseUrl: string,
  payload: CreateInitialAdminRequest,
): Promise<CreateInitialAdminResponse> {
  const response = await fetch(`${baseUrl}/api/setup/admin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`Setup admin request failed: ${response.status}`)
  }
  return (await response.json()) as CreateInitialAdminResponse
}

// ---------------------------------------------------------------------------
// User management
// ---------------------------------------------------------------------------

export async function listUsers(config: FrontendConfig): Promise<UserSummary[]> {
  const response = await fetch(`${config.baseUrl}/api/users`, {
    headers: buildHeaders(config, false),
  })
  if (!response.ok) throw new Error(`List users failed: ${response.status}`)
  return (await response.json()) as UserSummary[]
}

export async function createUser(
  config: FrontendConfig,
  payload: UserCreateRequest,
): Promise<UserCreateResponse> {
  const response = await fetch(`${config.baseUrl}/api/users`, {
    method: 'POST',
    headers: buildHeaders(config),
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(`Create user failed: ${response.status}`)
  return (await response.json()) as UserCreateResponse
}

export async function getUser(config: FrontendConfig, userId: string): Promise<UserSummary> {
  const response = await fetch(`${config.baseUrl}/api/users/${userId}`, {
    headers: buildHeaders(config, false),
  })
  if (!response.ok) throw new Error(`Get user failed: ${response.status}`)
  return (await response.json()) as UserSummary
}

export async function updateUser(
  config: FrontendConfig,
  userId: string,
  payload: UserUpdateRequest,
): Promise<UserSummary> {
  const response = await fetch(`${config.baseUrl}/api/users/${userId}`, {
    method: 'PUT',
    headers: buildHeaders(config),
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(`Update user failed: ${response.status}`)
  return (await response.json()) as UserSummary
}

export async function deleteUser(config: FrontendConfig, userId: string): Promise<void> {
  const response = await fetch(`${config.baseUrl}/api/users/${userId}`, {
    method: 'DELETE',
    headers: buildHeaders(config, false),
  })
  if (!response.ok) throw new Error(`Delete user failed: ${response.status}`)
}

export async function rotateUserKey(
  config: FrontendConfig,
  userId: string,
): Promise<UserCreateResponse> {
  const response = await fetch(`${config.baseUrl}/api/users/${userId}/rotate-key`, {
    method: 'POST',
    headers: buildHeaders(config, false),
  })
  if (!response.ok) throw new Error(`Rotate key failed: ${response.status}`)
  return (await response.json()) as UserCreateResponse
}

export async function bulkCreateUsers(
  config: FrontendConfig,
  payload: BulkUserCreateRequest,
): Promise<BulkUserCreateResponse> {
  const response = await fetch(`${config.baseUrl}/api/users/bulk`, {
    method: 'POST',
    headers: buildHeaders(config),
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(`Bulk create users failed: ${response.status}`)
  return (await response.json()) as BulkUserCreateResponse
}
