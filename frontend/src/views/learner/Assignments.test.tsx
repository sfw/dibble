import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { Assignments } from './Assignments'
import {
  demoLearnerFlow,
  demoLearnerWorkspace,
  demoProfileSummary,
  demoCurriculumProgression,
} from '../../sample-data'
import type { LearnerContext } from '../../shells/LearnerShell'

vi.mock('../../hooks/useAssignments', () => ({
  useLearnerAssignments: vi.fn().mockReturnValue({
    assignments: [
      {
        assignment_id: 'asgn-1',
        student_id: 'student-demo-001',
        teacher_id: 'teacher-1',
        section_id: 'class-1',
        title: 'Fractions practice',
        description: 'Practice equivalent fractions',
        status: 'assigned',
        target_resource_id: null,
        target_kc_ids: ['kc-fractions'],
        target_lo_ids: [],
        due_at: '2026-03-20T00:00:00Z',
        created_at: '2026-03-17T12:00:00Z',
        started_at: null,
        completed_at: null,
        updated_at: '2026-03-17T12:00:00Z',
      },
      {
        assignment_id: 'asgn-2',
        student_id: 'student-demo-001',
        teacher_id: 'teacher-1',
        section_id: 'class-1',
        title: 'Decimals review',
        description: '',
        status: 'completed',
        target_resource_id: null,
        target_kc_ids: [],
        target_lo_ids: [],
        due_at: null,
        created_at: '2026-03-16T10:00:00Z',
        started_at: '2026-03-16T11:00:00Z',
        completed_at: '2026-03-16T15:00:00Z',
        updated_at: '2026-03-16T15:00:00Z',
      },
    ],
    hasMore: false,
    loading: false,
    loadingMore: false,
    error: '',
    loadMore: vi.fn(),
    updateStatus: vi.fn().mockResolvedValue(null),
    refresh: vi.fn(),
  }),
}))

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

function renderAssignments() {
  const router = createMemoryRouter(
    [
      {
        path: '/learn',
        element: <Outlet context={context} />,
        children: [
          { path: 'assignments', element: <Assignments /> },
        ],
      },
    ],
    { initialEntries: ['/learn/assignments'] },
  )

  return render(<RouterProvider router={router} />)
}

describe('Learner Assignments', () => {
  it('renders the page heading', () => {
    renderAssignments()
    expect(screen.getByRole('heading', { name: 'Assignments' })).toBeInTheDocument()
  })

  it('renders active and past assignment sections', () => {
    renderAssignments()
    expect(screen.getByText('To do')).toBeInTheDocument()
    expect(screen.getByText('Past')).toBeInTheDocument()
  })

  it('renders assignment titles', () => {
    renderAssignments()
    expect(screen.getByText('Fractions practice')).toBeInTheDocument()
    expect(screen.getByText('Decimals review')).toBeInTheDocument()
  })

  it('shows a Start button for assigned work', () => {
    renderAssignments()
    expect(screen.getByRole('button', { name: /start/i })).toBeInTheDocument()
  })

  it('shows assignment description', () => {
    renderAssignments()
    expect(screen.getByText('Practice equivalent fractions')).toBeInTheDocument()
  })
})
