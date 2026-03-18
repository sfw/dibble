import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import {
  SAMPLE_STUDENT_ID,
  demoGenerationHistory,
  demoLearnerWorkspace,
  demoProfile,
  demoRemediationHistory,
  demoSocraticHistory,
  demoTeacherClassroom,
  demoTeacherClassrooms,
  demoTeacherInterventionAction,
} from './sample-data'

describe('App', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  it('keeps classroom handoff continuity while routing into teacher and learner workspaces', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Backend unavailable'))))

    render(<App />)

    expect((await screen.findAllByText('Backend unavailable Showing demo data instead.')).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('tab', { name: 'Classroom View' }))
    await user.click(screen.getAllByRole('button', { name: 'Open teacher triage' })[0]!)

    expect(await screen.findByText(`Reviewing ${SAMPLE_STUDENT_ID} from Grade 5 Fractions`)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Return to classroom' }))
    expect(await screen.findByText('Move from classroom posture to learner action handoff')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Continue generated content' }))
    expect(await screen.findByText('Create grounded lesson moves')).toBeInTheDocument()
  })

  it('surfaces live workspace connectivity when backend contracts load successfully', async () => {
    stubLiveFetch()

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Source: live')).toBeInTheDocument()
    })

    expect(screen.getByText('Backend connected')).toBeInTheDocument()
    expect(screen.getByText('No active contract notices')).toBeInTheDocument()
  })

  it('surfaces teacher-decision fallback notices after live intervention writes fail', async () => {
    const user = userEvent.setup()
    stubLiveFetch({ failTeacherDecisionPost: true })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Source: live')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('tab', { name: 'Teacher View' }))
    await user.clear(screen.getByLabelText('Teacher note'))
    await user.type(screen.getByLabelText('Teacher note'), 'Follow up after stations with one more check.')
    await user.click(screen.getByRole('button', { name: 'Approve' }))

    await waitFor(() => {
      expect(screen.getByText('Source: demo')).toBeInTheDocument()
    })

    const errorMessage =
      'Teacher decision unavailable (teacher_decision_unavailable) Recorded a demo decision instead.'

    expect(screen.getByText('Demo fallback active')).toBeInTheDocument()
    expect(screen.getAllByText(errorMessage).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Follow up after stations with one more check.').length).toBeGreaterThan(0)
  })

  it('keeps shell fallback posture honest when classroom refresh drops to demo after a live boot', async () => {
    const user = userEvent.setup()
    stubLiveFetch({ failClassroomRefresh: true })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Source: live')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Refresh learner workspace' }))

    await waitFor(() => {
      expect(screen.getByText('Source: demo')).toBeInTheDocument()
    })

    expect(screen.getByText('Demo fallback active')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Teacher classroom refresh failed (teacher_classroom_unavailable) Showing demo classroom data instead.',
      ),
    ).toBeInTheDocument()
  })
})

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

function errorResponse(status: number, detail: string, code: string): Response {
  return new Response(JSON.stringify({ detail, code }), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'X-Dibble-Error-Code': code,
    },
  })
}

function stubLiveFetch({
  failTeacherDecisionPost = false,
  failClassroomRefresh = false,
}: {
  failTeacherDecisionPost?: boolean
  failClassroomRefresh?: boolean
} = {}) {
  let classroomListRequests = 0

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const request = input instanceof Request ? input : null
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
      const method = init?.method ?? request?.method ?? 'GET'

      if (url.endsWith('/api/learners')) {
        return jsonResponse([SAMPLE_STUDENT_ID])
      }
      if (url.endsWith(`/api/learners/${SAMPLE_STUDENT_ID}/workspace`)) {
        return jsonResponse(demoLearnerWorkspace)
      }
      if (url.endsWith(`/api/learners/${SAMPLE_STUDENT_ID}/profile`)) {
        return jsonResponse(demoProfile)
      }
      if (url.includes(`/api/learners/${SAMPLE_STUDENT_ID}/history/generations`)) {
        return jsonResponse({ items: demoGenerationHistory, offset: 0, limit: 20, has_more: false })
      }
      if (url.includes(`/api/learners/${SAMPLE_STUDENT_ID}/history/socratic-sessions`)) {
        return jsonResponse({ items: demoSocraticHistory, offset: 0, limit: 20, has_more: false })
      }
      if (url.includes(`/api/learners/${SAMPLE_STUDENT_ID}/history/remediation-sessions`)) {
        return jsonResponse({ items: demoRemediationHistory, offset: 0, limit: 20, has_more: false })
      }
      if (url.endsWith(`/api/learners/${SAMPLE_STUDENT_ID}/intervention-action`) && method === 'POST') {
        if (failTeacherDecisionPost) {
          return errorResponse(503, 'Teacher decision unavailable', 'teacher_decision_unavailable')
        }

        return jsonResponse(demoTeacherInterventionAction)
      }
      if (url.endsWith(`/api/learners/${SAMPLE_STUDENT_ID}/intervention-action`)) {
        return jsonResponse(demoTeacherInterventionAction)
      }
      if (url.endsWith('/api/teachers/classrooms')) {
        classroomListRequests += 1

        if (failClassroomRefresh && classroomListRequests > 1) {
          return errorResponse(503, 'Teacher classroom refresh failed', 'teacher_classroom_unavailable')
        }

        return jsonResponse(demoTeacherClassrooms)
      }
      if (url.endsWith(`/api/teachers/classrooms/${demoTeacherClassroom.classroom_id}`)) {
        return jsonResponse(demoTeacherClassroom)
      }

      throw new Error(`Unhandled fetch request: ${url}`)
    }),
  )
}
