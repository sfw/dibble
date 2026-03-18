import { render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { SocraticCheck } from './SocraticCheck'
import {
  demoLearnerFlow,
  demoLearnerWorkspace,
  demoProfileSummary,
  demoCurriculumProgression,
  demoSocraticSession,
  demoSocraticResponse,
} from '../../sample-data'
import type { LearnerContext } from '../../shells/LearnerShell'

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

const mockHandleRun = vi.fn()
const mockHandleReload = vi.fn()
const mockSetForm = vi.fn()

vi.mock('../../hooks/useSocraticWorkspace', () => ({
  useSocraticWorkspace: vi.fn().mockImplementation(() => ({
    form: {},
    setForm: mockSetForm,
    response: demoSocraticResponse,
    session: demoSocraticSession,
    loading: false,
    error: '',
    handleRun: mockHandleRun,
    handleReload: mockHandleReload,
  })),
}))

// Re-import so we can override per-test
import { useSocraticWorkspace } from '../../hooks/useSocraticWorkspace'

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

function renderSocratic(overrides?: Partial<LearnerContext>) {
  const ctx = { ...context, ...overrides }
  const router = createMemoryRouter(
    [
      {
        path: '/learn',
        element: <Outlet context={ctx} />,
        children: [
          { path: 'socratic/:sessionId', element: <SocraticCheck /> },
        ],
      },
    ],
    { initialEntries: ['/learn/socratic/soc-demo-1'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('SocraticCheck', () => {
  it('renders the page heading', () => {
    renderSocratic()
    expect(screen.getByRole('heading', { name: "Let's see what you know" })).toBeInTheDocument()
  })

  it('renders understanding check label', () => {
    renderSocratic()
    expect(screen.getByText('Understanding check')).toBeInTheDocument()
  })

  it('renders conversation history', () => {
    renderSocratic()
    expect(screen.getByText('Why might 1/2 and 2/4 represent the same amount?')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Because the whole is the same and both pictures cover equal space even with different numbers.',
      ),
    ).toBeInTheDocument()
  })

  it('renders confidence picker with radiogroup', () => {
    renderSocratic()
    expect(screen.getByRole('radiogroup')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Not sure' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Somewhat' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Pretty sure' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Very sure' })).toBeInTheDocument()
  })

  it('has Pretty sure selected by default', () => {
    renderSocratic()
    expect(screen.getByRole('radio', { name: 'Pretty sure' })).toHaveAttribute('aria-checked', 'true')
  })

  it('renders submit button', () => {
    renderSocratic()
    expect(screen.getByRole('button', { name: /submit your answer/i })).toBeInTheDocument()
  })

  it('disables submit when response is empty', () => {
    renderSocratic()
    expect(screen.getByRole('button', { name: /submit your answer/i })).toBeDisabled()
  })

  it('renders back navigation', () => {
    renderSocratic()
    expect(screen.getByText('Back to home')).toBeInTheDocument()
  })

  it('renders hint disclosure when hints are present', () => {
    renderSocratic()
    expect(screen.getByText('Need a hint?')).toBeInTheDocument()
  })

  it('renders affective support when present', () => {
    renderSocratic()
    expect(screen.getByText("You're on a roll!")).toBeInTheDocument()
  })

  it('shows error banner with retry when error occurs', () => {
    vi.mocked(useSocraticWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      response: demoSocraticResponse,
      session: demoSocraticSession,
      loading: false,
      error: 'Network error',
      handleRun: mockHandleRun,
      handleReload: mockHandleReload,
    } as unknown as ReturnType<typeof useSocraticWorkspace>)

    renderSocratic()
    expect(screen.getByText('Network error')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('shows loading indicator when loading', () => {
    vi.mocked(useSocraticWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      response: demoSocraticResponse,
      session: demoSocraticSession,
      loading: true,
      error: '',
      handleRun: mockHandleRun,
      handleReload: mockHandleReload,
    } as unknown as ReturnType<typeof useSocraticWorkspace>)

    renderSocratic()
    expect(screen.getByText('Thinking...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /checking/i })).toBeDisabled()
  })
})
