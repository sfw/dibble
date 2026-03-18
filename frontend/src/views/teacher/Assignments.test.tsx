import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { TeacherAssignments } from './Assignments'
import type { TeacherContext } from '../../shells/TeacherShell'
import type { TeacherClassroomReadModel } from '../../types'

const mockClassroom: TeacherClassroomReadModel = {
  classroom_id: 'class-1',
  title: 'Math 7A',
  teacher_label: 'Ms. Smith',
  learner_count: 2,
  active_flow_count: 1,
  blocked_progression_count: 0,
  intervention_available_count: 0,
  learners: [
    {
      student_id: 'student-1',
      grade_level: '7',
      current_flow: {
        flow_type: 'generation',
        target_kc_ids: [],
        target_lo_ids: [],
        current_phase: 'target',
        session_phase: 'active',
        socratic_session_id: null,
        remediation_session_id: null,
        rationale: null,
      },
      curriculum_progression: {
        current_stage: 'target',
        current_stage_display_label: null,
        current_resource: null,
        next_ready_resource: null,
        prerequisite_blockers: [],
        resource_count: 5,
        mastered_resource_count: 2,
        mastered_resource_ratio: 0.4,
        progression_action: 'hold_target',
        progression_action_display_label: null,
      },
      intervention: {
        action_key: 'int-1',
        proposal_status: 'none',
        available_options: [],
        latest_decision: null,
        proposed_action: { kind: 'idle', method: 'GET', endpoint: '', request_hint: null, display_label: null },
      },
      attention_level: 'none',
      attention_reasons: [],
      triage_section: {
        key: 'on_track',
        title: 'On track',
        description: 'Progressing normally',
        tone: 'success',
      },
    },
  ],
}

vi.mock('../../hooks/useAssignments', () => ({
  useTeacherAssignments: vi.fn().mockReturnValue({
    assignments: [
      {
        assignment_id: 'asgn-1',
        student_id: 'student-1',
        teacher_id: 'teacher-1',
        classroom_id: 'class-1',
        title: 'Fractions practice',
        description: 'Work on equivalent fractions',
        status: 'assigned',
        target_resource_id: null,
        target_kc_ids: [],
        target_lo_ids: [],
        due_at: '2026-03-20T00:00:00Z',
        created_at: '2026-03-17T12:00:00Z',
        started_at: null,
        completed_at: null,
        updated_at: '2026-03-17T12:00:00Z',
      },
      {
        assignment_id: 'asgn-2',
        student_id: 'student-1',
        teacher_id: 'teacher-1',
        classroom_id: 'class-1',
        title: 'Completed task',
        description: '',
        status: 'completed',
        target_resource_id: null,
        target_kc_ids: [],
        target_lo_ids: [],
        due_at: null,
        created_at: '2026-03-15T12:00:00Z',
        started_at: '2026-03-15T13:00:00Z',
        completed_at: '2026-03-16T10:00:00Z',
        updated_at: '2026-03-16T10:00:00Z',
      },
    ],
    hasMore: false,
    loading: false,
    loadingMore: false,
    creating: false,
    error: '',
    loadMore: vi.fn(),
    create: vi.fn().mockResolvedValue({}),
    updateStatus: vi.fn().mockResolvedValue({}),
    refresh: vi.fn(),
  }),
}))

const context: TeacherContext = {
  config: {
    baseUrl: 'http://localhost:8000',
    apiKey: '',
    bearerToken: 'test-token',
    useDemoFallback: false,
    showDebugPanels: false,
  },
  classrooms: [],
  selectedClassroomId: 'class-1',
  classroom: mockClassroom,
  loading: false,
  error: '',
  loadClassroom: vi.fn(),
}

function renderTeacherAssignments() {
  const router = createMemoryRouter(
    [
      {
        path: '/teacher',
        element: <Outlet context={context} />,
        children: [
          { path: 'assignments', element: <TeacherAssignments /> },
        ],
      },
    ],
    { initialEntries: ['/teacher/assignments'] },
  )

  return render(<RouterProvider router={router} />)
}

describe('TeacherAssignments', () => {
  it('renders the page heading', () => {
    renderTeacherAssignments()
    expect(screen.getByRole('heading', { name: 'Assignments' })).toBeInTheDocument()
  })

  it('renders assignment count summary', () => {
    renderTeacherAssignments()
    expect(screen.getByText(/1 active/)).toBeInTheDocument()
    expect(screen.getByText(/1 completed/)).toBeInTheDocument()
  })

  it('renders assignment titles', () => {
    renderTeacherAssignments()
    expect(screen.getByText('Fractions practice')).toBeInTheDocument()
    expect(screen.getByText('Completed task')).toBeInTheDocument()
  })

  it('shows new assignment button', () => {
    renderTeacherAssignments()
    expect(screen.getByRole('button', { name: /new assignment/i })).toBeInTheDocument()
  })

  it('shows cancel button for active assignments', () => {
    renderTeacherAssignments()
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
  })

  it('shows student ID on assignment rows', () => {
    renderTeacherAssignments()
    expect(screen.getAllByText(/student-1/).length).toBeGreaterThan(0)
  })
})
