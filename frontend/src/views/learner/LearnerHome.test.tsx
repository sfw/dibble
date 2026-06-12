import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { LearnerHome } from './LearnerHome'
import {
  demoLearnerFlow,
  demoLearnerWorkspace,
  demoProfileSummary,
  demoCurriculumProgression,
} from '../../sample-data'
import type { LearnerContext } from '../../shells/LearnerShell'

const baseContext: LearnerContext = {
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

function renderHome(overrides?: Partial<LearnerContext>) {
  const ctx = { ...baseContext, ...overrides }
  const router = createMemoryRouter(
    [
      {
        path: '/learn',
        element: <Outlet context={ctx} />,
        children: [{ index: true, element: <LearnerHome /> }],
      },
    ],
    { initialEntries: ['/learn'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('LearnerHome', () => {
  it('renders the welcome heading when a continue action exists', () => {
    renderHome()
    expect(screen.getByText('Welcome back')).toBeInTheDocument()
  })

  it('renders the idle greeting when continue action is idle', () => {
    renderHome({
      workspace: {
        ...baseContext.workspace,
        continue_action: {
          ...baseContext.workspace.continue_action,
          kind: 'idle',
        },
      },
    })
    expect(screen.getByText('Great work today!')).toBeInTheDocument()
  })

  it('renders the current lesson card with a resume button', () => {
    renderHome()
    expect(screen.getByRole('button', { name: /resume/i })).toBeInTheDocument()
  })

  it('hides the lesson card when action is idle', () => {
    renderHome({
      workspace: {
        ...baseContext.workspace,
        continue_action: {
          ...baseContext.workspace.continue_action,
          kind: 'idle',
        },
      },
    })
    expect(screen.queryByRole('button', { name: /resume/i })).not.toBeInTheDocument()
  })

  it('renders the today focus section with current stage and resource', () => {
    renderHome()
    expect(screen.getByText("Today's focus")).toBeInTheDocument()
    expect(screen.getByText('Current stage')).toBeInTheDocument()
    expect(screen.getAllByText('Working on').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Equivalent Fraction Practice').length).toBeGreaterThan(0)
  })

  it('renders the progress summary section', () => {
    renderHome()
    expect(screen.getByText('Your progress')).toBeInTheDocument()
    expect(screen.getByText('1 of 3 mastered')).toBeInTheDocument()
  })

  it('renders recent activity count', () => {
    renderHome()
    expect(screen.getByText(/9 lessons completed recently/)).toBeInTheDocument()
  })

  it('renders flow rationale when present', () => {
    renderHome()
    expect(
      screen.getByText(/recent support-light success/),
    ).toBeInTheDocument()
  })

  it('shows loading skeleton when loading with no student id', () => {
    renderHome({
      loading: true,
      workspace: { ...baseContext.workspace, student_id: '' },
    })
    // PageSkeleton renders skeleton elements rather than the page content
    expect(screen.queryByText('Welcome back')).not.toBeInTheDocument()
  })

  it('shows error banner when error is present', () => {
    renderHome({ error: 'Something went wrong' })
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('navigates to continue learning on resume click', async () => {
    const user = userEvent.setup()
    renderHome()
    await user.click(screen.getByRole('button', { name: /resume/i }))
    // After navigation, URL should change — we can verify by the router state
    // In the test environment, the router will attempt to navigate to /learn/continue
    // The route doesn't exist in our test router, so the page will be empty
    expect(screen.queryByText('Welcome back')).not.toBeInTheDocument()
  })

  it('disables resume button while loading', () => {
    renderHome({ loading: true })
    expect(screen.getByRole('button', { name: /resume/i })).toBeDisabled()
  })
})
