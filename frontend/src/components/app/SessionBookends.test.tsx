import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SessionBookends } from './SessionBookends'
import { ProgressStrip } from './ProgressStrip'
import { DefectReportButton } from './DefectReportButton'
import { startLearnerSession, endLearnerSession, reportContentDefect } from '../../api'
import type { FrontendConfig, LearnerCurriculumProgressionSummary } from '../../types'

vi.mock('../../api', () => ({
  startLearnerSession: vi.fn(),
  endLearnerSession: vi.fn(),
  reportContentDefect: vi.fn(),
}))

const mockedStart = vi.mocked(startLearnerSession)
const mockedEnd = vi.mocked(endLearnerSession)
const mockedReport = vi.mocked(reportContentDefect)

const config: FrontendConfig = {
  baseUrl: 'http://localhost:8000',
  apiKey: '',
  bearerToken: '',
  useDemoFallback: false,
  showDebugPanels: false,
}

describe('SessionBookends', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
  })

  it('starts a session and shows the goal', async () => {
    mockedStart.mockResolvedValue({
      learning_session_id: 'session-abc',
      goal_display: 'Today: 3 practice rounds on Fractions.',
      focus_outcome_title: 'Fractions',
      started_at: new Date().toISOString(),
    })

    render(<SessionBookends config={config} studentId="learner-1" />)
    await userEvent.click(screen.getByRole('button', { name: /start today's session/i }))

    await waitFor(() => {
      expect(screen.getByText('Today: 3 practice rounds on Fractions.')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /finish today's session/i })).toBeInTheDocument()
  })

  it('ends a session and shows the recap', async () => {
    sessionStorage.setItem(
      'dibble-session-learner-1',
      JSON.stringify({ learning_session_id: 'session-abc', goal_display: 'Goal' }),
    )
    mockedEnd.mockResolvedValue({
      learning_session_id: 'session-abc',
      completed_activity_count: 3,
      smooth_activity_count: 3,
      display_recap: 'Nice work today! You finished 3 activities and everything went smoothly.',
      ended_at: new Date().toISOString(),
    })

    render(<SessionBookends config={config} studentId="learner-1" />)
    await userEvent.click(screen.getByRole('button', { name: /finish today's session/i }))

    await waitFor(() => {
      expect(screen.getByText(/finished 3 activities/i)).toBeInTheDocument()
    })
    expect(sessionStorage.getItem('dibble-session-learner-1')).toBeNull()
  })
})

describe('ProgressStrip', () => {
  it('renders mastered, working-on, and up-next from the read model', () => {
    const progression = {
      status: 'ok',
      source: 'backend',
      flow_type: 'lesson',
      current_stage: 'target',
      progression_action: 'stay_on_requested_target',
      active_target_kc_ids: [],
      outcome_count: 9,
      mastered_outcome_count: 4,
      ready_outcome_count: 2,
      blocked_outcome_count: 0,
      active_outcome_count: 1,
      mastered_outcome_ratio: 0.44,
      current_outcome: {
        outcome_id: 'lo-1',
        title: 'Equivalent fractions',
        state: 'active',
        knowledge_component_ids: [],
        blocked_prerequisite_kc_ids: [],
        mastery_ratio: 0.5,
        current_flow_aligned: true,
        target_stage: 'target',
      },
      next_outcome: {
        outcome_id: 'lo-2',
        title: 'Adding fractions',
        state: 'ready',
        knowledge_component_ids: [],
        blocked_prerequisite_kc_ids: [],
        mastery_ratio: 0,
        current_flow_aligned: false,
        target_stage: 'target',
      },
      blocked_outcomes: [],
      ready_outcomes: [],
    } as unknown as LearnerCurriculumProgressionSummary

    render(<ProgressStrip progression={progression} />)

    expect(screen.getByText('4 of 9 topics')).toBeInTheDocument()
    expect(screen.getByText('Equivalent fractions')).toBeInTheDocument()
    expect(screen.getByText('Adding fractions')).toBeInTheDocument()
  })
})

describe('DefectReportButton', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends a defect report and shows the confirmation', async () => {
    mockedReport.mockResolvedValue({
      status: 'recorded',
      display_message: "Thanks for letting us know — we'll take a look.",
    })

    render(
      <DefectReportButton config={config} studentId="learner-1" generationId="gen-1" />,
    )
    await userEvent.click(screen.getByRole('button', { name: /something wrong/i }))

    await waitFor(() => {
      expect(screen.getByText(/thanks for letting us know/i)).toBeInTheDocument()
    })
    expect(mockedReport).toHaveBeenCalledWith(config, 'learner-1', {
      generation_id: 'gen-1',
      learning_session_id: null,
    })
  })
})
