import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { Progress } from './Progress'
import {
  demoLearnerFlow,
  demoLearnerWorkspace,
  demoProfileSummary,
  demoCurriculumProgression,
} from '../../sample-data'
import type { LearnerContext } from '../../shells/LearnerShell'

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
  generationHistory: [],
  socraticHistory: [],
  remediationHistory: [],
  hasMoreHistory: false,
  loadingMore: false,
  loadMoreHistory: vi.fn(),
  loading: false,
  error: '',
}

function renderProgress(overrides?: Partial<LearnerContext>) {
  const ctx = { ...context, ...overrides }
  const router = createMemoryRouter(
    [
      {
        path: '/learn',
        element: <Outlet context={ctx} />,
        children: [{ path: 'progress', element: <Progress /> }],
      },
    ],
    { initialEntries: ['/learn/progress'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('Progress', () => {
  it('renders the page heading', () => {
    renderProgress()
    expect(screen.getByRole('heading', { name: 'Your progress' })).toBeInTheDocument()
  })

  it('renders current focus section', () => {
    renderProgress()
    // "Current focus" appears both as a standalone section and in the all-outcomes group
    expect(screen.getAllByText('Current focus').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Equivalent Fraction Practice').length).toBeGreaterThanOrEqual(1)
  })

  it('renders overall progress stats', () => {
    renderProgress()
    expect(screen.getByText('Course progress')).toBeInTheDocument()
    expect(screen.getByText('1 of 3 mastered')).toBeInTheDocument()
  })

  it('renders recent activity', () => {
    renderProgress()
    expect(screen.getByText('Recent activity')).toBeInTheDocument()
  })

  it('renders what to practice next', () => {
    renderProgress()
    expect(screen.getByText('What to practice next')).toBeInTheDocument()
    // Outcome appears in both "what to practice" and "all outcomes"
    expect(screen.getAllByText('Compare Fraction Families').length).toBeGreaterThanOrEqual(1)
  })

  it('renders all outcomes section', () => {
    renderProgress()
    expect(screen.getByText('All outcomes')).toBeInTheDocument()
    expect(screen.getByText('3 total')).toBeInTheDocument()
  })

  it('shows mastered outcome count in all outcomes', () => {
    renderProgress()
    expect(screen.getByText('1 outcome mastered')).toBeInTheDocument()
  })

  it('shows blocked outcomes with rationale', () => {
    renderProgress()
    // Blocked outcome appears in the all-outcomes section
    expect(screen.getAllByText('Fraction Word Problems').length).toBeGreaterThanOrEqual(1)
    // "Blocked" appears in the stat box and in the outcome group header
    expect(screen.getAllByText('Blocked').length).toBeGreaterThanOrEqual(1)
  })

  it('shows ready to start group', () => {
    renderProgress()
    expect(screen.getByText('Ready to start')).toBeInTheDocument()
  })

  it('shows loading skeleton when loading with no data', () => {
    renderProgress({
      loading: true,
      summary: { ...demoProfileSummary, student_id: '' },
    })
    expect(screen.queryByText('Your progress')).not.toBeInTheDocument()
  })

  it('shows error banner when error is set', () => {
    renderProgress({ error: 'Load failed' })
    expect(screen.getByText('Load failed')).toBeInTheDocument()
  })

  it('shows support_dependent mastery quality badge', () => {
    renderProgress({
      progression: {
        ...demoCurriculumProgression,
        ready_outcomes: [
          {
            outcome_id: 'R-scaffolded',
            title: 'Scaffolded Outcome',
            state: 'ready',
            knowledge_component_ids: ['KC-1'],
            blocked_prerequisite_kc_ids: [],
            mastery_ratio: 0.85,
            current_flow_aligned: false,
            target_stage: 'target',
            mastery_quality: 'support_dependent',
            rationale: 'Mastery scores are above threshold, but recent evidence looks scaffolded.',
          },
        ],
      },
    })
    expect(screen.getAllByText('Needs independent practice').length).toBeGreaterThanOrEqual(1)
  })

  it('shows fragile mastery quality badge', () => {
    renderProgress({
      progression: {
        ...demoCurriculumProgression,
        ready_outcomes: [
          {
            outcome_id: 'R-fragile',
            title: 'Fragile Outcome',
            state: 'ready',
            knowledge_component_ids: ['KC-1'],
            blocked_prerequisite_kc_ids: [],
            mastery_ratio: 0.82,
            current_flow_aligned: false,
            target_stage: 'target',
            mastery_quality: 'fragile',
            rationale: 'Mastery scores are above threshold, but recent evidence looks unstable.',
          },
        ],
      },
    })
    expect(screen.getAllByText('Unstable mastery').length).toBeGreaterThanOrEqual(1)
  })
})
