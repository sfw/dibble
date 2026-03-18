import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { RemediationSession } from './RemediationSession'
import {
  demoLearnerFlow,
  demoLearnerWorkspace,
  demoProfileSummary,
  demoCurriculumProgression,
  demoRemediationSession,
  demoGeneration,
} from '../../sample-data'
import type { LearnerContext } from '../../shells/LearnerShell'

const mockHandleAdvance = vi.fn()
const mockHandleReload = vi.fn()
const mockHandleTrigger = vi.fn()
const mockSetForm = vi.fn()
const mockSetAdvancePrompt = vi.fn()

vi.mock('../../hooks/useRemediationWorkspace', () => ({
  useRemediationWorkspace: vi.fn().mockImplementation(() => ({
    form: {},
    setForm: mockSetForm,
    content: demoGeneration,
    session: demoRemediationSession,
    advance: null,
    loading: false,
    error: '',
    advancePrompt: '',
    setAdvancePrompt: mockSetAdvancePrompt,
    handleTrigger: mockHandleTrigger,
    handleReload: mockHandleReload,
    handleAdvance: mockHandleAdvance,
  })),
}))

import { useRemediationWorkspace } from '../../hooks/useRemediationWorkspace'

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

function renderRemediation(overrides?: Partial<LearnerContext>) {
  const ctx = { ...context, ...overrides }
  const router = createMemoryRouter(
    [
      {
        path: '/learn',
        element: <Outlet context={ctx} />,
        children: [
          { path: 'remediation/:sessionId', element: <RemediationSession /> },
        ],
      },
    ],
    { initialEntries: ['/learn/remediation/rem-demo-1'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('RemediationSession', () => {
  it('renders the current step title as heading', () => {
    renderRemediation()
    expect(screen.getByRole('heading', { name: 'Repair The Comparison Rule' })).toBeInTheDocument()
  })

  it('renders practice session label', () => {
    renderRemediation()
    expect(screen.getByText('Practice session')).toBeInTheDocument()
  })

  it('renders step progress indicator', () => {
    renderRemediation()
    expect(screen.getByText('Step 2 of 3')).toBeInTheDocument()
  })

  it('renders phase label with objective', () => {
    renderRemediation()
    expect(screen.getByText('Compare fractions by whole amount instead of separate numerator and denominator cues.')).toBeInTheDocument()
  })

  it('renders content blocks from generated content', () => {
    renderRemediation()
    expect(screen.getByText('Model The Relationship')).toBeInTheDocument()
  })

  it('renders response textarea', () => {
    renderRemediation()
    expect(screen.getByText('Your response')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('What do you think?')).toBeInTheDocument()
  })

  it('disables continue button when response is empty', () => {
    renderRemediation()
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('enables continue button when response has text', () => {
    vi.mocked(useRemediationWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      content: demoGeneration,
      session: demoRemediationSession,
      advance: null,
      loading: false,
      error: '',
      advancePrompt: 'My answer',
      setAdvancePrompt: mockSetAdvancePrompt,
      handleTrigger: mockHandleTrigger,
      handleReload: mockHandleReload,
      handleAdvance: mockHandleAdvance,
    } as unknown as ReturnType<typeof useRemediationWorkspace>)

    renderRemediation()
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })

  it('renders back navigation', () => {
    renderRemediation()
    expect(screen.getByText('Back to home')).toBeInTheDocument()
  })

  it('renders rationale disclosure', () => {
    renderRemediation()
    expect(screen.getByText('Why am I working on this?')).toBeInTheDocument()
  })

  it('renders affective support when present', () => {
    renderRemediation()
    expect(screen.getByText("You're on a roll!")).toBeInTheDocument()
  })

  it('shows error banner with retry when error occurs', () => {
    vi.mocked(useRemediationWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      content: demoGeneration,
      session: demoRemediationSession,
      advance: null,
      loading: false,
      error: 'Connection failed',
      advancePrompt: '',
      setAdvancePrompt: mockSetAdvancePrompt,
      handleTrigger: mockHandleTrigger,
      handleReload: mockHandleReload,
      handleAdvance: mockHandleAdvance,
    } as unknown as ReturnType<typeof useRemediationWorkspace>)

    renderRemediation()
    expect(screen.getByText('Connection failed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('shows loading state', () => {
    vi.mocked(useRemediationWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      content: { ...demoGeneration, response: { ...demoGeneration.response, blocks: [] } },
      session: demoRemediationSession,
      advance: null,
      loading: true,
      error: '',
      advancePrompt: '',
      setAdvancePrompt: mockSetAdvancePrompt,
      handleTrigger: mockHandleTrigger,
      handleReload: mockHandleReload,
      handleAdvance: mockHandleAdvance,
    } as unknown as ReturnType<typeof useRemediationWorkspace>)

    renderRemediation()
    expect(screen.getByText('Preparing your next step...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /working/i })).toBeDisabled()
  })

  it('shows empty state when no steps exist', () => {
    vi.mocked(useRemediationWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      content: demoGeneration,
      session: { ...demoRemediationSession, steps: [], current_step_index: null },
      advance: null,
      loading: false,
      error: '',
      advancePrompt: '',
      setAdvancePrompt: mockSetAdvancePrompt,
      handleTrigger: mockHandleTrigger,
      handleReload: mockHandleReload,
      handleAdvance: mockHandleAdvance,
    } as unknown as ReturnType<typeof useRemediationWorkspace>)

    renderRemediation()
    expect(screen.getByText('Your practice session is being prepared. Check back in a moment.')).toBeInTheDocument()
  })
})
