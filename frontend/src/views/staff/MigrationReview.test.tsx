import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { MigrationReview } from './MigrationReview'
import { AuthContext } from '../../contexts/AuthContext'
import { ConfigContext } from '../../contexts/ConfigContext'
import type { AuthState } from '../../hooks/useAuth'
import {
  approveCurriculumMigrationPlan,
  getReleaseReadiness,
  listCurriculumImpactAnalyses,
  listCurriculumMigrationPlans,
  listCurriculumSnapshotDiffs,
  previewCurriculumMigrationExecution,
} from '@/api'

vi.mock('@/api', () => ({
  listCurriculumSnapshotDiffs: vi.fn(),
  listCurriculumImpactAnalyses: vi.fn(),
  listCurriculumMigrationPlans: vi.fn(),
  createCurriculumMigrationPlan: vi.fn(),
  approveCurriculumMigrationPlan: vi.fn(),
  previewCurriculumMigrationExecution: vi.fn(),
  getReleaseReadiness: vi.fn(),
}))

const mockedListCurriculumSnapshotDiffs = vi.mocked(listCurriculumSnapshotDiffs)
const mockedListCurriculumImpactAnalyses = vi.mocked(listCurriculumImpactAnalyses)
const mockedListCurriculumMigrationPlans = vi.mocked(listCurriculumMigrationPlans)
const mockedApproveCurriculumMigrationPlan = vi.mocked(approveCurriculumMigrationPlan)
const mockedPreviewCurriculumMigrationExecution = vi.mocked(previewCurriculumMigrationExecution)
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

function renderMigrationReview() {
  return render(
    <ConfigContext.Provider value={{ baseUrl: 'http://localhost:8000', setBaseUrl: vi.fn() }}>
      <AuthContext.Provider value={makeAuthState()}>
        <MemoryRouter>
          <MigrationReview />
        </MemoryRouter>
      </AuthContext.Provider>
    </ConfigContext.Provider>,
  )
}

describe('MigrationReview', () => {
  beforeEach(() => {
    mockedListCurriculumSnapshotDiffs.mockReset()
    mockedListCurriculumImpactAnalyses.mockReset()
    mockedListCurriculumMigrationPlans.mockReset()
    mockedApproveCurriculumMigrationPlan.mockReset()
    mockedPreviewCurriculumMigrationExecution.mockReset()
    mockedGetReleaseReadiness.mockReset()

    mockedListCurriculumSnapshotDiffs.mockResolvedValue([
      {
        diff_id: 'diff-1',
        source_snapshot_id: 'snapshot-a',
        target_snapshot_id: 'snapshot-b',
        framework_id: 'math-7',
        source_framework_version: '2025',
        target_framework_version: '2026',
        created_at: '2026-04-22T00:00:00Z',
        updated_at: '2026-04-22T00:00:00Z',
        entity_deltas: [
          {
            delta_id: 'delta-1',
            artifact_kind: 'outcome',
            artifact_id: 'OUT-1',
            change_kind: 'changed',
            risk_level: 'high',
            before: null,
            after: null,
            field_changes: [],
            approved_alignment_edge_id: null,
            suggested_action: 'keep_pinned',
            rationale: 'Outcome title changed and may break learner goal references.',
          },
        ],
      },
    ])
    mockedListCurriculumImpactAnalyses.mockResolvedValue([
      {
        analysis_id: 'impact-1',
        diff_id: 'diff-1',
        source_snapshot_id: 'snapshot-a',
        target_snapshot_id: 'snapshot-b',
        created_at: '2026-04-22T00:00:00Z',
        updated_at: '2026-04-22T00:00:00Z',
        impacts: [
          {
            impact_id: 'runtime-1',
            entity_kind: 'learner_goal',
            entity_id: 'goal-1',
            student_id: 'student-1',
            current_snapshot_id: 'snapshot-a',
            referenced_course_ids: [],
            referenced_outcome_ids: ['OUT-1'],
            referenced_kc_ids: [],
            matched_delta_ids: ['delta-1'],
            suggested_action: 'keep_pinned',
            confidence: 0.91,
            risk_level: 'high',
            rationale: 'Pinned learner goal needs review before remap.',
          },
        ],
      },
    ])
    mockedListCurriculumMigrationPlans.mockResolvedValue([
      {
        plan_id: 'plan-1',
        diff_id: 'diff-1',
        source_snapshot_id: 'snapshot-a',
        target_snapshot_id: 'snapshot-b',
        status: 'ready',
        created_at: '2026-04-22T00:00:00Z',
        updated_at: '2026-04-22T00:00:00Z',
        actions: [
          {
            action_id: 'action-1',
            action_type: 'swap_provenance_only',
            entity_kind: 'library_artifact',
            entity_id: 'artifact-1',
            source_snapshot_id: 'snapshot-a',
            target_snapshot_id: 'snapshot-b',
            source_outcome_ids: [],
            target_outcome_ids: [],
            source_kc_ids: ['KC-1'],
            target_kc_ids: ['KC-2'],
            approved_alignment_edge_ids: [],
            risk_level: 'low',
            confidence: 0.84,
            status: 'approved',
            rationale: 'Artifact provenance can move without learner-visible changes.',
            reviewer_id: 'admin-1',
            approved_at: '2026-04-22T00:00:00Z',
            executed_at: null,
            execution_summary: null,
          },
        ],
        review_items: [
          {
            review_item_id: 'review-1',
            entity_kind: 'learner_goal',
            entity_id: 'goal-1',
            risk_level: 'high',
            blocking_delta_ids: ['delta-1'],
            recommended_action: 'keep_pinned',
            rationale: 'Pinned learner goal still needs operator confirmation.',
          },
        ],
      },
    ])
    mockedApproveCurriculumMigrationPlan.mockResolvedValue({
      plan_id: 'plan-1',
      diff_id: 'diff-1',
      source_snapshot_id: 'snapshot-a',
      target_snapshot_id: 'snapshot-b',
      status: 'ready',
      created_at: '2026-04-22T00:00:00Z',
      updated_at: '2026-04-22T00:00:00Z',
      actions: [
        {
          action_id: 'action-1',
          action_type: 'swap_provenance_only',
          entity_kind: 'library_artifact',
          entity_id: 'artifact-1',
          source_snapshot_id: 'snapshot-a',
          target_snapshot_id: 'snapshot-b',
          source_outcome_ids: [],
          target_outcome_ids: [],
          source_kc_ids: ['KC-1'],
          target_kc_ids: ['KC-2'],
          approved_alignment_edge_ids: [],
          risk_level: 'low',
          confidence: 0.84,
          status: 'approved',
          rationale: 'Artifact provenance can move without learner-visible changes.',
          reviewer_id: 'admin-1',
          approved_at: '2026-04-22T00:00:00Z',
          executed_at: null,
          execution_summary: null,
        },
      ],
      review_items: [
        {
          review_item_id: 'review-1',
          entity_kind: 'learner_goal',
          entity_id: 'goal-1',
          risk_level: 'high',
          blocking_delta_ids: ['delta-1'],
          recommended_action: 'keep_pinned',
          rationale: 'Pinned learner goal still needs operator confirmation.',
        },
      ],
    })
    mockedPreviewCurriculumMigrationExecution.mockResolvedValue({
      plan_id: 'plan-1',
      diff_id: 'diff-1',
      rollout_blocked: true,
      rollout_reason: 'Migration execution remains manual-only under the current rollout policy.',
      generated_at: '2026-04-22T00:00:00Z',
      executed_action_count: 0,
      blocked_action_count: 1,
      action_previews: [
        {
          action_id: 'action-1',
          would_execute: false,
          status: 'approved',
          summary: 'Would keep the library artifact pinned to the current curriculum snapshot.',
          explanation: {
            action_id: 'action-1',
            entity_kind: 'library_artifact',
            entity_id: 'artifact-1',
            action_type: 'swap_provenance_only',
            risk_level: 'low',
            confidence: 0.84,
            rationale: 'Rollout policy still blocks migration execution.',
            rollout_effect: {
              capability: 'migration_execution',
              enabled: false,
              mode: 'manual_only',
              fallback_behavior: 'manual_review_required',
              effective_gate: {
                capability: 'migration_execution',
                mode: 'manual_only',
                fallback_behavior: 'manual_review_required',
                description: 'Migration execution stays manual until approved.',
              },
              source: 'policy',
              source_cohort_ids: [],
              evaluation_bucket_id: null,
              kill_switch_active: false,
              kill_switch_reason: null,
              rationale: ['Migration execution remains manual-only.'],
            },
            fallback_behavior: 'manual_review_required',
            next_expected_consequence: 'The plan remains ready but unexecuted.',
            generated_at: '2026-04-22T00:00:00Z',
          },
        },
      ],
    })
    mockedGetReleaseReadiness.mockResolvedValue({
      generated_at: '2026-04-22T00:00:00Z',
      total_recent_traces: 6,
      degraded_trace_count: 1,
      provider_statuses: [],
      fallback_counts: [],
      pending_review_queues: [{ queue_key: 'migration_review', count: 1, summary: 'One migration review waiting.' }],
      stuck_migration_plans: [{ plan_id: 'plan-1', status: 'ready', approved_action_count: 1, failed_action_count: 0, review_item_count: 1, updated_at: '2026-04-22T00:00:00Z' }],
      stale_autonomous_suggestions: [],
      cloud_library: {
        remote_enabled: true,
        degraded: true,
        recent_lookup_failures: 2,
        recent_publish_failures: 1,
        remote_endpoint: 'https://library.example.com',
        last_degraded_at: '2026-04-22T00:00:00Z',
        last_degraded_reason: 'Timed out contacting the remote library.',
      },
      active_kill_switches: [],
      recent_degraded_operations: [],
      blocked_review_previews: [
        {
          item_kind: 'migration_review',
          item_id: 'review-1',
          summary: 'Learner goal review is still blocked.',
          explanation: 'Pinned learner goal needs operator confirmation.',
          next_step: 'Confirm whether the learner goal should stay pinned.',
          risk_level: 'high',
          household_id: null,
          learner_id: 'student-1',
        },
      ],
    })
  })

  it('shows blocked review items and dry-run consequences', async () => {
    const user = userEvent.setup()
    renderMigrationReview()

    expect(await screen.findByText('Review dry runs before curriculum changes touch runtime state.')).toBeInTheDocument()
    expect(screen.getByText('Pinned learner goal still needs operator confirmation.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Preview dry run' }))

    await waitFor(() => {
      expect(mockedPreviewCurriculumMigrationExecution).toHaveBeenCalledWith(
        expect.objectContaining({ baseUrl: 'http://localhost:8000' }),
        'plan-1',
        expect.objectContaining({
          dry_run: true,
          executor_id: 'admin-1',
        }),
      )
    })

    expect(await screen.findByText('Rollout policy is still blocking execution.')).toBeInTheDocument()
    expect(screen.getByText('Would keep the library artifact pinned to the current curriculum snapshot.')).toBeInTheDocument()
    expect(screen.getByText('Trust readiness')).toBeInTheDocument()
    expect(screen.getByText('Learner goal review is still blocked.')).toBeInTheDocument()
  })
})
