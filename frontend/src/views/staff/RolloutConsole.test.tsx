import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { RolloutConsole } from './RolloutConsole'
import { AuthContext } from '../../contexts/AuthContext'
import { ConfigContext } from '../../contexts/ConfigContext'
import type { AuthState } from '../../hooks/useAuth'
import {
  getReleaseReadiness,
  getRolloutEvaluationSummary,
  getRolloutPolicy,
  simulateRolloutPolicyChange,
  updateRolloutPolicy,
} from '@/api'

vi.mock('@/api', () => ({
  getRolloutPolicy: vi.fn(),
  getRolloutEvaluationSummary: vi.fn(),
  simulateRolloutPolicyChange: vi.fn(),
  updateRolloutPolicy: vi.fn(),
  getReleaseReadiness: vi.fn(),
}))

const mockedGetRolloutPolicy = vi.mocked(getRolloutPolicy)
const mockedGetRolloutEvaluationSummary = vi.mocked(getRolloutEvaluationSummary)
const mockedSimulateRolloutPolicyChange = vi.mocked(simulateRolloutPolicyChange)
const mockedUpdateRolloutPolicy = vi.mocked(updateRolloutPolicy)
const mockedGetReleaseReadiness = vi.mocked(getReleaseReadiness)

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

function renderRolloutConsole() {
  return render(
    <ConfigContext.Provider value={{ baseUrl: 'http://localhost:8000', setBaseUrl: vi.fn() }}>
      <AuthContext.Provider value={makeAuthState()}>
        <MemoryRouter>
          <RolloutConsole />
        </MemoryRouter>
      </AuthContext.Provider>
    </ConfigContext.Provider>,
  )
}

describe('RolloutConsole', () => {
  beforeEach(() => {
    mockedGetRolloutPolicy.mockReset()
    mockedGetRolloutEvaluationSummary.mockReset()
    mockedSimulateRolloutPolicyChange.mockReset()
    mockedUpdateRolloutPolicy.mockReset()
    mockedGetReleaseReadiness.mockReset()

    mockedGetRolloutPolicy.mockResolvedValue({
      policy: {
        policy_id: 'default',
        label: 'Controlled rollout',
        description: 'Conservative rollout policy.',
        assignment_salt: 'dibble-rollout-v1',
        updated_at: '2026-04-22T00:00:00Z',
        behavior_gates: [
          {
            capability: 'non_text_modalities',
            mode: 'text_only',
            fallback_behavior: 'text_only_fallback',
            description: 'Non-text modalities can be rolled out gradually.',
          },
          {
            capability: 'migration_execution',
            mode: 'manual_only',
            fallback_behavior: 'manual_review_required',
            description: 'Migration execution stays manual until approved.',
          },
        ],
        cohorts: [
          {
            cohort_id: 'cohort-1',
            label: 'Pilot households',
            description: 'Hand-picked rollout cohort.',
            assignment_unit: 'household',
            rollout_percentage: 40,
            learner_ids: [],
            household_ids: ['household-1'],
            pinned_evaluation_bucket_id: 'bucket-1',
            behavior_overrides: [],
          },
        ],
        evaluation_buckets: [
          {
            bucket_id: 'bucket-1',
            label: 'Baseline Controlled',
            description: 'Conservative baseline.',
            weight: 100,
            dimensions: { modality_mode: 'text_only' },
            behavior_overrides: [],
          },
        ],
        kill_switches: [
          {
            capability: 'migration_execution',
            active: true,
            reason: 'Hold while validating dry-run behavior',
            updated_at: '2026-04-22T00:00:00Z',
          },
        ],
      },
    })
    mockedGetRolloutEvaluationSummary.mockResolvedValue({
      generated_at: '2026-04-22T00:00:00Z',
      total_samples: 12,
      buckets: [
        {
          bucket_id: 'bucket-1',
          label: 'Baseline Controlled',
          dimensions: { modality_mode: 'text_only' },
          sample_count: 12,
          learner_count: 4,
          positive_run_rate: 0.75,
          average_run_outcome_score: 0.68,
          average_observation_score: 0.71,
          average_assessment_score: 0.65,
          modality_counts: { text: 12 },
        },
      ],
    })
    mockedGetReleaseReadiness.mockResolvedValue({
      generated_at: '2026-04-22T00:00:00Z',
      total_recent_traces: 10,
      degraded_trace_count: 2,
      provider_statuses: [],
      fallback_counts: [],
      pending_review_queues: [{ queue_key: 'migration_review', count: 1, summary: 'One migration review waiting.' }],
      stuck_migration_plans: [],
      stale_autonomous_suggestions: [],
      cloud_library: {
        remote_enabled: false,
        degraded: false,
        recent_lookup_failures: 0,
        recent_publish_failures: 0,
        remote_endpoint: null,
        last_degraded_at: null,
        last_degraded_reason: null,
      },
      active_kill_switches: [
        {
          capability: 'migration_execution',
          active: true,
          reason: 'Hold while validating dry-run behavior',
          updated_at: '2026-04-22T00:00:00Z',
        },
      ],
      recent_degraded_operations: [],
      blocked_review_previews: [
        {
          item_kind: 'migration_plan',
          item_id: 'plan-1',
          summary: 'Migration plan needs manual review.',
          explanation: 'A high-risk learner goal remap is still pending.',
          next_step: 'Confirm goal remap with an operator.',
          risk_level: 'high',
          household_id: null,
          learner_id: null,
        },
      ],
    })
    mockedSimulateRolloutPolicyChange.mockResolvedValue({
      current_policy_id: 'default',
      proposed_policy_id: 'default',
      generated_at: '2026-04-22T00:00:00Z',
      summary: {
        total_subject_count: 1,
        changed_subject_count: 1,
        changed_learner_count: 0,
        changed_household_count: 1,
        newly_risky_subject_count: 1,
        capability_change_counts: { non_text_modalities: 1 },
        top_capability_deltas: [
          {
            capability: 'non_text_modalities',
            affected_subject_count: 1,
            newly_risky_subject_count: 1,
          },
        ],
      },
      diffs: [
        {
          subject: { household_id: 'household-1', label: 'Pilot households household household-1' },
          current_inspection: {
            policy_id: 'default',
            subject: { household_id: 'household-1' },
            cohort_ids: ['cohort-1'],
            evaluation_bucket: null,
            decisions: [],
            generated_at: '2026-04-22T00:00:00Z',
          },
          proposed_inspection: {
            policy_id: 'default',
            subject: { household_id: 'household-1' },
            cohort_ids: ['cohort-1'],
            evaluation_bucket: null,
            decisions: [],
            generated_at: '2026-04-22T00:00:00Z',
          },
          cohort_changed: false,
          evaluation_bucket_changed: false,
          newly_risky_capabilities: ['non_text_modalities'],
          capability_deltas: [
            {
              capability: 'non_text_modalities',
              changed: true,
              changed_fields: ['mode'],
              fallback_changed: false,
              newly_exposed_to_risky_capability: true,
              current_decision: {
                capability: 'non_text_modalities',
                enabled: false,
                mode: 'text_only',
                fallback_behavior: 'text_only_fallback',
                effective_gate: {
                  capability: 'non_text_modalities',
                  mode: 'text_only',
                  fallback_behavior: 'text_only_fallback',
                  description: 'Non-text modalities can be rolled out gradually.',
                },
                source: 'policy',
                source_cohort_ids: [],
                evaluation_bucket_id: null,
                kill_switch_active: false,
                kill_switch_reason: null,
                rationale: ['Current rollout keeps this subject text-only.'],
              },
              proposed_decision: {
                capability: 'non_text_modalities',
                enabled: true,
                mode: 'full_multimodal',
                fallback_behavior: 'text_only_fallback',
                effective_gate: {
                  capability: 'non_text_modalities',
                  mode: 'full_multimodal',
                  fallback_behavior: 'text_only_fallback',
                  description: 'Non-text modalities can be rolled out gradually.',
                },
                source: 'policy',
                source_cohort_ids: [],
                evaluation_bucket_id: null,
                kill_switch_active: false,
                kill_switch_reason: null,
                rationale: ['Proposed rollout would allow non-text modalities for this cohort.'],
              },
            },
          ],
        },
      ],
    })
    mockedUpdateRolloutPolicy.mockResolvedValue({
      policy: {
        policy_id: 'default',
        label: 'Controlled rollout',
        description: 'Conservative rollout policy.',
        assignment_salt: 'dibble-rollout-v1',
        updated_at: '2026-04-22T00:00:00Z',
        behavior_gates: [],
        cohorts: [],
        evaluation_buckets: [],
        kill_switches: [],
      },
    })
  })

  it('renders rollout controls and shows simulation results', async () => {
    const user = userEvent.setup()
    renderRolloutConsole()

    expect(await screen.findByText('Simulate policy changes before they touch live households.')).toBeInTheDocument()
    expect(screen.getByText('Pilot households')).toBeInTheDocument()
    expect(screen.getAllByText('Active kill switches').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Run simulation' }))

    await waitFor(() => {
      expect(mockedSimulateRolloutPolicyChange).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
        expect.objectContaining({
          subjects: [expect.objectContaining({ household_id: 'household-1' })],
        }),
      )
    })

    expect(await screen.findByText('Pilot households household household-1')).toBeInTheDocument()
    expect(screen.getByText('1 newly risky')).toBeInTheDocument()
    expect(screen.getByText('Proposed rollout would allow non-text modalities for this cohort.')).toBeInTheDocument()
    expect(screen.getByText('Trust readiness')).toBeInTheDocument()
  })
})
