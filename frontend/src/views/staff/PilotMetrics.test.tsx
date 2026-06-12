import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { PilotMetrics } from './PilotMetrics'
import { AuthContext } from '../../contexts/AuthContext'
import { ConfigContext } from '../../contexts/ConfigContext'
import type { AuthState } from '../../hooks/useAuth'
import { getPilotMetrics } from '../../api'
import type { PilotMetricsResponse } from '../../types'

vi.mock('../../api', () => ({
  getPilotMetrics: vi.fn(),
}))

const mockedGetPilotMetrics = vi.mocked(getPilotMetrics)

function makeAuthState(): AuthState {
  return {
    identity: {
      principal_id: 'admin-1',
      role: 'admin',
      auth_scheme: 'api_key',
      display_name: 'Admin Operator',
      learner_id: null,
    },
    authenticated: true,
    loading: false,
    error: '',
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    getToken: vi.fn().mockReturnValue(''),
    getApiKey: vi.fn().mockReturnValue('admin-key'),
  }
}

function buildMetrics(): PilotMetricsResponse {
  return {
    days: 90,
    learners: [
      {
        student_id: 'learner-1',
        sessions: {
          sessions_started: 8,
          sessions_completed: 6,
          completion_rate: 0.75,
          active_days: 5,
          day_over_day_return_rate: 0.5,
          week_over_week_return_rate: 1.0,
        },
        mastery: {
          snapshot_count: 4,
          earliest_overall_kc_mastery: 0.4,
          latest_overall_kc_mastery: 0.62,
          kc_mastery_delta: 0.22,
          earliest_overall_lo_mastery: 0.35,
          latest_overall_lo_mastery: 0.5,
          lo_mastery_delta: 0.15,
        },
        defect_report_count: 1,
        intervention_decision_counts: { approve: 2 },
        baseline_agreement_rate: 0.8,
        baseline_decision_count: 10,
        generation: {
          generation_count: 12,
          cache_hits: 4,
          average_latency_ms: 850,
          total_prompt_tokens: 9000,
          total_completion_tokens: 3000,
          verification_failed_count: 0,
        },
      },
    ],
    cohort: {
      learner_count: 1,
      sessions_started: 8,
      sessions_completed: 6,
      completion_rate: 0.75,
      average_kc_mastery_delta: 0.22,
      defect_report_count: 1,
      intervention_decision_counts: { approve: 2 },
      generation_count: 12,
      cache_hits: 4,
      average_latency_ms: 850,
      total_prompt_tokens: 9000,
      total_completion_tokens: 3000,
      verification_failed_count: 0,
    },
    baseline: {
      total_decisions: 10,
      agreed_decisions: 8,
      agreement_rate: 0.8,
      decision_points: [
        {
          decision_point: 'router.route',
          total_decisions: 10,
          agreed_decisions: 8,
          agreement_rate: 0.8,
        },
      ],
      divergences: [
        {
          decision_point: 'router.route',
          student_id: 'learner-1',
          production_decision: { intervention_type: 'reteach' },
          baseline_decision: { intervention_type: 'targeted_practice' },
          inputs_digest: 'abc123',
          created_at: null,
        },
      ],
    },
  }
}

function renderView() {
  return render(
    <MemoryRouter>
      <ConfigContext.Provider
        value={{
          baseUrl: 'http://localhost:8000',
          setBaseUrl: () => {},
        }}
      >
        <AuthContext.Provider value={makeAuthState()}>
          <PilotMetrics />
        </AuthContext.Provider>
      </ConfigContext.Provider>
    </MemoryRouter>,
  )
}

describe('PilotMetrics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders cohort stats and learner table', async () => {
    mockedGetPilotMetrics.mockResolvedValue(buildMetrics())

    renderView()

    await waitFor(() => {
      expect(screen.getByText('Pilot metrics')).toBeInTheDocument()
    })
    expect(screen.getByText('Baseline agreement')).toBeInTheDocument()
    expect(screen.getAllByText('80%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('learner-1').length).toBeGreaterThan(0)
    expect(screen.getByText('6/8')).toBeInTheDocument()
  })

  it('shows an error banner when the request fails', async () => {
    mockedGetPilotMetrics.mockRejectedValue(new Error('boom'))

    renderView()

    await waitFor(() => {
      expect(screen.getByText(/boom/)).toBeInTheDocument()
    })
  })
})
