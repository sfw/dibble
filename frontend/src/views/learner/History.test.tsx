import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { History } from './History'
import {
  demoLearnerFlow,
  demoLearnerWorkspace,
  demoProfileSummary,
  demoCurriculumProgression,
} from '../../sample-data'
import type { LearnerContext } from '../../shells/LearnerShell'
import type {
  LearnerGenerationHistoryEntry,
  LearnerSocraticSessionHistoryEntry,
  LearnerRemediationSessionHistoryEntry,
} from '../../types'

const nextStep = { action: 'generate', target_stage: 'target', target_kc_ids: [] as string[] }
const continueAction = { kind: 'idle' as const, target_stage: 'target', target_kc_ids: [] as string[], request_payload: {} }

const generations: LearnerGenerationHistoryEntry[] = [
  {
    generation_id: 'gen-1',
    content_type: 'conceptual_explanation',
    flow_type: 'generation',
    status: 'completed',
    delivered_phase: 'target',
    progression_action: 'hold_target',
    target_stage: 'target',
    active_target_kc_ids: [],
    rationale: 'Explained fractions',
    mastery_signal: 'insufficient',
    mastery_confidence: 0,
    progress_signal: 'insufficient',
    evidence_signal: 'steady',
    next_step: nextStep,
    continue_action: continueAction,
    created_at: '2026-03-17T10:00:00Z',
  },
  {
    generation_id: 'gen-2',
    content_type: 'practice_problem',
    flow_type: 'generation',
    status: 'completed',
    delivered_phase: 'transfer',
    progression_action: 'attempt_transfer',
    target_stage: 'transfer',
    active_target_kc_ids: [],
    rationale: 'Practice problems',
    mastery_signal: 'improving',
    mastery_confidence: 0.8,
    progress_signal: 'advancing',
    evidence_signal: 'progressing',
    next_step: nextStep,
    continue_action: continueAction,
    created_at: '2026-03-17T09:00:00Z',
  },
]

const socratic: LearnerSocraticSessionHistoryEntry[] = [
  {
    session_id: 'soc-1',
    target_kc_ids: [],
    target_lo_ids: [],
    status: 'completed',
    turn_count: 3,
    latest_steering_action: 'open_probe',
    latest_next_action: 'generate',
    latest_evidence_strength: 'moderate',
    rationale: 'Checked understanding',
    next_step: nextStep,
    continue_action: continueAction,
    created_at: '2026-03-17T08:00:00Z',
    updated_at: '2026-03-17T08:05:00Z',
  },
]

const remediation: LearnerRemediationSessionHistoryEntry[] = [
  {
    session_id: 'rem-1',
    target_kc_id: 'kc-1',
    focus_kc_ids: ['kc-1'],
    prerequisite_kc_ids: [],
    status: 'active',
    step_count: 4,
    completed_step_count: 2,
    progression_decision: 'hold',
    progression_rationale: 'Still building foundations',
    next_step: { action: 'advance', target_stage: 'repair', target_kc_ids: [] },
    continue_action: continueAction,
    created_at: '2026-03-17T07:00:00Z',
    updated_at: '2026-03-17T07:10:00Z',
  },
]

const context: LearnerContext = {
  config: {
    baseUrl: 'http://localhost:8000',
    apiKey: '',
    bearerToken: 'test-token',
    useDemoFallback: false,
    showDebugPanels: false,
  },
  summary: demoProfileSummary,
  flow: demoLearnerFlow,
  workspace: demoLearnerWorkspace,
  progression: demoCurriculumProgression,
  generationHistory: generations,
  socraticHistory: socratic,
  remediationHistory: remediation,
  hasMoreHistory: false,
  loadingMore: false,
  loadMoreHistory: vi.fn(),
  loading: false,
  error: '',
}

function renderHistory(overrides?: Partial<LearnerContext>) {
  const ctx = { ...context, ...overrides }
  const router = createMemoryRouter(
    [
      {
        path: '/learn',
        element: <Outlet context={ctx} />,
        children: [{ path: 'history', element: <History /> }],
      },
    ],
    { initialEntries: ['/learn/history'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('History', () => {
  it('renders the page heading', () => {
    renderHistory()
    expect(screen.getByRole('heading', { name: 'History' })).toBeInTheDocument()
  })

  it('renders all timeline entries', () => {
    renderHistory()
    expect(screen.getByText('Explained fractions')).toBeInTheDocument()
    expect(screen.getByText('Practice problems')).toBeInTheDocument()
    expect(screen.getByText('Checked understanding')).toBeInTheDocument()
    expect(screen.getByText('Still building foundations')).toBeInTheDocument()
  })

  it('renders filter tabs with counts', () => {
    renderHistory()
    expect(screen.getByRole('tab', { name: /All.*4/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Lessons.*2/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Checks.*1/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Practice.*1/i })).toBeInTheDocument()
  })

  it('filters to only lessons when Lessons tab clicked', async () => {
    const user = userEvent.setup()
    renderHistory()

    await user.click(screen.getByRole('tab', { name: /Lessons/i }))

    expect(screen.getByText('Explained fractions')).toBeInTheDocument()
    expect(screen.getByText('Practice problems')).toBeInTheDocument()
    expect(screen.queryByText('Checked understanding')).not.toBeInTheDocument()
    expect(screen.queryByText('Still building foundations')).not.toBeInTheDocument()
  })

  it('filters to only checks when Checks tab clicked', async () => {
    const user = userEvent.setup()
    renderHistory()

    await user.click(screen.getByRole('tab', { name: /Checks/i }))

    expect(screen.queryByText('Explained fractions')).not.toBeInTheDocument()
    expect(screen.getByText('Checked understanding')).toBeInTheDocument()
    expect(screen.queryByText('Still building foundations')).not.toBeInTheDocument()
  })

  it('filters to only practice when Practice tab clicked', async () => {
    const user = userEvent.setup()
    renderHistory()

    await user.click(screen.getByRole('tab', { name: /Practice/i }))

    expect(screen.queryByText('Explained fractions')).not.toBeInTheDocument()
    expect(screen.queryByText('Checked understanding')).not.toBeInTheDocument()
    expect(screen.getByText('Still building foundations')).toBeInTheDocument()
  })

  it('returns to all entries when All tab clicked', async () => {
    const user = userEvent.setup()
    renderHistory()

    await user.click(screen.getByRole('tab', { name: /Lessons/i }))
    await user.click(screen.getByRole('tab', { name: /All/i }))

    expect(screen.getByText('Explained fractions')).toBeInTheDocument()
    expect(screen.getByText('Checked understanding')).toBeInTheDocument()
    expect(screen.getByText('Still building foundations')).toBeInTheDocument()
  })

  it('shows empty state when no entries exist', () => {
    renderHistory({
      generationHistory: [],
      socraticHistory: [],
      remediationHistory: [],
    })
    expect(screen.getByText('No activities yet. Start a lesson to see your history here.')).toBeInTheDocument()
  })

  it('shows filtered empty state when filter has no matches', async () => {
    const user = userEvent.setup()
    renderHistory({
      generationHistory: generations,
      socraticHistory: [],
      remediationHistory: [],
    })

    await user.click(screen.getByRole('tab', { name: /Practice/i }))

    expect(screen.getByText('No practice sessions yet.')).toBeInTheDocument()
  })

  it('shows load more button when hasMoreHistory', () => {
    renderHistory({ hasMoreHistory: true })
    expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument()
  })

  it('shows error banner when error is set', () => {
    renderHistory({ error: 'Failed to load' })
    expect(screen.getByText('Failed to load')).toBeInTheDocument()
  })
})
