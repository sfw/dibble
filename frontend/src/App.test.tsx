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
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url

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
          return jsonResponse(demoGenerationHistory)
        }
        if (url.includes(`/api/learners/${SAMPLE_STUDENT_ID}/history/socratic-sessions`)) {
          return jsonResponse(demoSocraticHistory)
        }
        if (url.includes(`/api/learners/${SAMPLE_STUDENT_ID}/history/remediation-sessions`)) {
          return jsonResponse(demoRemediationHistory)
        }
        if (url.endsWith(`/api/learners/${SAMPLE_STUDENT_ID}/intervention-action`)) {
          return jsonResponse(demoTeacherInterventionAction)
        }
        if (url.endsWith('/api/teachers/classrooms')) {
          return jsonResponse(demoTeacherClassrooms)
        }
        if (url.endsWith(`/api/teachers/classrooms/${demoTeacherClassroom.classroom_id}`)) {
          return jsonResponse(demoTeacherClassroom)
        }

        throw new Error(`Unhandled fetch request: ${url}`)
      }),
    )

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Source: live')).toBeInTheDocument()
    })

    expect(screen.getByText('Backend connected')).toBeInTheDocument()
    expect(screen.getByText('No active contract notices')).toBeInTheDocument()
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
