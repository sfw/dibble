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
    // "Current focus" appears both as a standalone section and in the all-resources group
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
    // Resource appears in both "what to practice" and "all resources"
    expect(screen.getAllByText('Compare Fraction Families').length).toBeGreaterThanOrEqual(1)
  })

  it('renders all resources section', () => {
    renderProgress()
    expect(screen.getByText('All resources')).toBeInTheDocument()
    expect(screen.getByText('3 total')).toBeInTheDocument()
  })

  it('shows mastered resource count in all resources', () => {
    renderProgress()
    expect(screen.getByText('1 resource mastered')).toBeInTheDocument()
  })

  it('shows blocked resources with rationale', () => {
    renderProgress()
    // Blocked resource appears in the all-resources section
    expect(screen.getAllByText('Fraction Word Problems').length).toBeGreaterThanOrEqual(1)
    // "Blocked" appears in the stat box and in the resource group header
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
})
