import { render, screen } from '@testing-library/react'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { Dashboard } from './Dashboard'
import type { ParentContext } from '../../shells/ParentShell'

function renderDashboard(context: ParentContext) {
  const router = createMemoryRouter(
    [
      {
        path: '/parent',
        element: <Outlet context={context} />,
        children: [{ index: true, element: <Dashboard /> }],
      },
    ],
    { initialEntries: ['/parent'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('Parent Dashboard', () => {
  const baseContext: ParentContext = {
    config: {
      baseUrl: 'http://localhost:8000',
      apiKey: 'parent-key',
      bearerToken: '',
      useDemoFallback: false,
      showDebugPanels: false,
    },
    overview: {
      household: null,
      learners: [],
      session_suggestions: [],
      pending_approvals: [],
      weekly_summaries: [],
      notifications: [],
      available_learners: [{ learner_id: 'student-1', display_name: 'Avery' }],
    },
    loading: false,
    error: '',
    saveSetup: vi.fn().mockResolvedValue(undefined),
    savePreferences: vi.fn().mockResolvedValue(undefined),
    refresh: vi.fn().mockResolvedValue(undefined),
    markRead: vi.fn().mockResolvedValue(undefined),
    dismissNotification: vi.fn().mockResolvedValue(undefined),
    snoozeNotification: vi.fn().mockResolvedValue(undefined),
    acceptSuggestion: vi.fn().mockResolvedValue(undefined),
    deferSuggestion: vi.fn().mockResolvedValue(undefined),
    snoozeSuggestion: vi.fn().mockResolvedValue(undefined),
    approveParentApproval: vi.fn().mockResolvedValue(undefined),
    rejectParentApproval: vi.fn().mockResolvedValue(undefined),
  }

  it('renders setup state when the household is not configured', () => {
    renderDashboard(baseContext)

    expect(screen.getByText('Set up your household teaching loop')).toBeInTheDocument()
    expect(screen.getByText('Avery')).toBeInTheDocument()
    expect(screen.getByText('Create household')).toBeInTheDocument()
  })

  it('renders learner progress and notifications when the household exists', () => {
    renderDashboard({
      ...baseContext,
      overview: {
        household: {
          household_id: 'household-1',
          household_name: 'Avery Family',
          parent_profiles: [
            {
              parent_user_id: 'parent-1',
              relationship_label: 'parent',
              preferences: {
                session_cadence: 'daily',
                auto_session_suggestions: true,
                weekly_summary_day: 'sunday',
                soft_escalation_enabled: true,
                approval_mode: 'guided',
                modality_introduction_requires_approval: true,
                trajectory_revision_requires_approval: true,
                high_autonomy_session_requires_approval: true,
              },
            },
          ],
          learner_ids: ['student-1'],
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
        },
        learners: [
          {
            learner_id: 'student-1',
            learner_label: 'Avery',
            grade_level: '5',
            goal_title: 'Equivalent Fractions',
            mastery_ratio: 0.42,
            engagement: 'medium',
            frustration: 'low',
            current_stage: 'session_due',
            next_session_focus: 'Model equivalent fractions visually',
            suggested_modality: 'diagram',
            cadence_decision: 'session_due',
            soft_escalation_active: false,
            summary_headline: 'Still moving toward Equivalent Fractions.',
            pending_approval_count: 1,
          },
        ],
        session_suggestions: [
          {
            learner_id: 'student-1',
            cadence_decision: 'session_due',
            status: 'pending',
            snoozed_until: null,
            focus_label: 'Model equivalent fractions visually',
            target_kc_ids: ['KC-1'],
            modality: 'diagram',
          },
        ],
        pending_approvals: [
          {
            approval_id: 'approval-1',
            learner_id: 'student-1',
            approval_type: 'modality_introduction',
            status: 'pending',
            title: 'Approve diagram lessons',
            message: 'Dibble wants to introduce a new teaching modality.',
            proposed_value: 'diagram',
            metadata: {},
            requested_at: '2026-04-20T00:00:00Z',
          },
        ],
        weekly_summaries: [
          {
            learner_id: 'student-1',
            headline: 'Weekly learning update',
            celebration: 'Mastered 1 of 4 mapped outcomes.',
            next_focus: 'Model equivalent fractions visually',
            generated_at: '2026-04-20T00:00:00Z',
          },
        ],
        notifications: [
          {
            notification_id: 'notif-1',
            household_id: 'household-1',
            dedupe_key: 'weekly:1',
            category: 'weekly_summary',
            severity: 'info',
            title: 'Weekly summary ready',
            message: 'Weekly learning update',
            status: 'unread',
            snoozed_until: null,
            created_at: '2026-04-20T00:00:00Z',
            updated_at: '2026-04-20T00:00:00Z',
            metadata: {},
          },
        ],
        available_learners: [],
      },
    })

    expect(screen.getByText('Avery Family')).toBeInTheDocument()
    expect(screen.getByText('Avery')).toBeInTheDocument()
    expect(screen.getByText('Weekly summary ready')).toBeInTheDocument()
    expect(screen.getByText('Session initiation suggestions')).toBeInTheDocument()
    expect(screen.getByText('Approval gates')).toBeInTheDocument()
    expect(screen.getByText('Approve diagram lessons')).toBeInTheDocument()
    expect(screen.getAllByText('Snooze 1 day').length).toBeGreaterThan(0)
    expect(screen.getByText(/Status: pending/)).toBeInTheDocument()
    expect(screen.getByText('Save preferences')).toBeInTheDocument()
  })
})
