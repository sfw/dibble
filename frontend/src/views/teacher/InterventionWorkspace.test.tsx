import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { InterventionWorkspace } from './InterventionWorkspace'
import type { TeacherContext } from '../../shells/TeacherShell'

// ---------------------------------------------------------------------------
// Mock API calls — InterventionWorkspace uses useLearnerWorkspace and
// useLearnerContracts hooks that call these APIs
// ---------------------------------------------------------------------------

vi.mock('../../api', () => ({
  getLearners: vi.fn().mockRejectedValue(new Error('Demo mode')),
  getLearnerWorkspace: vi.fn().mockRejectedValue(new Error('Demo mode')),
  getLearnerProfile: vi.fn().mockRejectedValue(new Error('Demo mode')),
  getGenerationHistory: vi.fn().mockRejectedValue(new Error('Demo mode')),
  getSocraticHistory: vi.fn().mockRejectedValue(new Error('Demo mode')),
  getRemediationHistory: vi.fn().mockRejectedValue(new Error('Demo mode')),
  getTeacherInterventionAction: vi.fn().mockRejectedValue(new Error('Demo mode')),
  submitTeacherInterventionDecision: vi.fn().mockRejectedValue(new Error('Demo mode')),
  recordTeacherInterventionAction: vi.fn().mockRejectedValue(new Error('Demo mode')),
  getGeneratedContent: vi.fn().mockRejectedValue(new Error('Demo mode')),
}))

// ---------------------------------------------------------------------------
// Context — useDemoFallback true so the hooks use demo data from sample-data
// ---------------------------------------------------------------------------

const context: TeacherContext = {
  config: {
    baseUrl: 'http://localhost:8000',
    apiKey: '',
    bearerToken: 'test-token',
    useDemoFallback: true,
    showDebugPanels: false,
  },
  classrooms: [],
  selectedClassroomId: 'class-1',
  classroom: {
    classroom_id: 'class-1',
    title: 'Math 7A',
    teacher_label: 'Ms. Smith',
    learner_count: 1,
    active_flow_count: 1,
    blocked_progression_count: 0,
    intervention_available_count: 1,
    attention_needed_count: 0,
    missing_learner_count: 0,
    missing_student_ids: [],
    learners: [],
  },
  loading: false,
  error: '',
  loadClassroom: vi.fn(),
}

function renderIntervention(studentId = 'student-1') {
  const router = createMemoryRouter(
    [
      {
        path: '/teacher',
        element: <Outlet context={context} />,
        children: [{ path: 'learners/:studentId/intervention', element: <InterventionWorkspace /> }],
      },
    ],
    { initialEntries: [`/teacher/learners/${studentId}/intervention`] },
  )
  return render(<RouterProvider router={router} />)
}

describe('InterventionWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the intervention header with student id', () => {
    renderIntervention()
    expect(screen.getByText(/Intervention: student-1/)).toBeInTheDocument()
  })

  it('renders back to learner detail link', () => {
    renderIntervention()
    expect(screen.getByText('Back to learner detail')).toBeInTheDocument()
  })

  it('renders the proposed action section', () => {
    renderIntervention()
    expect(screen.getByText('Proposed action')).toBeInTheDocument()
  })

  it('renders the evidence context section with rationale', () => {
    renderIntervention()
    expect(screen.getByText('Evidence context')).toBeInTheDocument()
    expect(screen.getByText('Rationale')).toBeInTheDocument()
  })

  it('renders stage, phase, and progression labels', () => {
    renderIntervention()
    expect(screen.getByText('Stage')).toBeInTheDocument()
    expect(screen.getByText('Phase')).toBeInTheDocument()
    expect(screen.getByText('Progression')).toBeInTheDocument()
  })

  it('renders the proposal status badge', () => {
    renderIntervention()
    expect(screen.getByText('Proposal ready')).toBeInTheDocument()
  })

  it('renders decision control buttons', () => {
    renderIntervention()
    expect(screen.getByRole('button', { name: /approve recommendation/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /defer/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /escalate/i })).toBeInTheDocument()
  })

  it('renders the note textarea', () => {
    renderIntervention()
    expect(screen.getByText('Note (optional)')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Add a note about this decision...')).toBeInTheDocument()
  })

  it('renders option cards from demo data', () => {
    renderIntervention()
    expect(screen.getByText('Options')).toBeInTheDocument()
    // Demo data has "Send transfer practice" and "Hold with one more worked example"
    expect(screen.getByText('Send transfer practice')).toBeInTheDocument()
    expect(screen.getByText('Hold with one more worked example')).toBeInTheDocument()
  })

  it('marks recommended options with a badge', () => {
    renderIntervention()
    expect(screen.getByText('Recommended')).toBeInTheDocument()
  })

  it('allows selecting an option and shows the select button', async () => {
    const user = userEvent.setup()
    renderIntervention()
    await user.click(screen.getByText('Hold with one more worked example'))
    expect(screen.getByRole('button', { name: /use selected option/i })).toBeInTheDocument()
  })

  it('does not show "Use selected option" before any option is selected', () => {
    renderIntervention()
    expect(screen.queryByRole('button', { name: /use selected option/i })).not.toBeInTheDocument()
  })

  it('renders target KC badges when present', () => {
    renderIntervention()
    // Demo data has active_target_kc_ids: ['KC-1']
    expect(screen.getByText('KC-1')).toBeInTheDocument()
  })
})
