import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { ContinueLearning } from './ContinueLearning'
import {
  demoLearnerFlow,
  demoLearnerWorkspace,
  demoProfileSummary,
  demoCurriculumProgression,
  demoGeneration,
} from '../../sample-data'
import type { LearnerContext } from '../../shells/LearnerShell'

const mockHandleStream = vi.fn()
const mockHandleGenerate = vi.fn()
const mockSetForm = vi.fn()

vi.mock('../../hooks/useGenerationWorkspace', () => ({
  useGenerationWorkspace: vi.fn().mockImplementation(() => ({
    form: {},
    setForm: mockSetForm,
    result: demoGeneration,
    loading: false,
    error: '',
    streaming: false,
    streamEvents: [],
    streamedBlocks: [],
    handleGenerate: mockHandleGenerate,
    handleStream: mockHandleStream,
  })),
}))

import { useGenerationWorkspace } from '../../hooks/useGenerationWorkspace'

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

function renderContinue(overrides?: Partial<LearnerContext>) {
  const ctx = { ...context, ...overrides }
  const router = createMemoryRouter(
    [
      {
        path: '/learn',
        element: <Outlet context={ctx} />,
        children: [{ path: 'continue', element: <ContinueLearning /> }],
      },
    ],
    { initialEntries: ['/learn/continue'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('ContinueLearning', () => {
  it('renders the resource title as heading', () => {
    renderContinue()
    expect(screen.getByRole('heading', { name: 'Equivalent Fraction Practice' })).toBeInTheDocument()
  })

  it('renders content type label', () => {
    renderContinue()
    // learnerContentType('worked_example') → 'Worked example'
    expect(screen.getByText('Worked example')).toBeInTheDocument()
  })

  it('renders affective support', () => {
    renderContinue()
    expect(screen.getByText("You're on a roll!")).toBeInTheDocument()
  })

  it('renders generated content blocks', () => {
    renderContinue()
    expect(screen.getByText('Model The Relationship')).toBeInTheDocument()
    expect(screen.getByText('Your Turn')).toBeInTheDocument()
  })

  it('renders progress rail with mastery stats', () => {
    renderContinue()
    expect(screen.getByText('1 of 3 complete')).toBeInTheDocument()
  })

  it('renders continue CTA button', () => {
    renderContinue()
    // The continue button shows learnerContinueAction label
    const btn = screen.getByRole('button', { name: /continue|practice|next/i })
    expect(btn).toBeInTheDocument()
    expect(btn).not.toBeDisabled()
  })

  it('renders back navigation', () => {
    renderContinue()
    expect(screen.getByText('Back to home')).toBeInTheDocument()
  })

  it('shows empty state when no content yet', () => {
    vi.mocked(useGenerationWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      result: null,
      loading: false,
      error: '',
      streaming: false,
      streamEvents: [],
      streamedBlocks: [],
      handleGenerate: mockHandleGenerate,
      handleStream: mockHandleStream,
    } as unknown as ReturnType<typeof useGenerationWorkspace>)

    renderContinue()
    expect(screen.getByText('No content available yet. Your next lesson is being prepared.')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    vi.mocked(useGenerationWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      result: null,
      loading: false,
      error: '',
      streaming: false,
      streamEvents: [],
      streamedBlocks: [],
      handleGenerate: mockHandleGenerate,
      handleStream: mockHandleStream,
    } as unknown as ReturnType<typeof useGenerationWorkspace>)

    renderContinue({ loading: true })
    expect(screen.getByText('Loading your lesson...')).toBeInTheDocument()
  })

  it('shows error banner with retry when error occurs', () => {
    vi.mocked(useGenerationWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      result: demoGeneration,
      loading: false,
      error: 'Server error',
      streaming: false,
      streamEvents: [],
      streamedBlocks: [],
      handleGenerate: mockHandleGenerate,
      handleStream: mockHandleStream,
    } as unknown as ReturnType<typeof useGenerationWorkspace>)

    renderContinue()
    expect(screen.getByText('Server error')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('disables CTA while streaming', () => {
    vi.mocked(useGenerationWorkspace).mockReturnValue({
      form: {},
      setForm: mockSetForm,
      result: null,
      loading: false,
      error: '',
      streaming: true,
      streamEvents: [],
      streamedBlocks: [{ kind: 'text', title: 'Loading...', body: 'Content' }],
      handleGenerate: mockHandleGenerate,
      handleStream: mockHandleStream,
    } as unknown as ReturnType<typeof useGenerationWorkspace>)

    renderContinue()
    const btn = screen.getByRole('button', { name: /generating/i })
    expect(btn).toBeDisabled()
  })
})
