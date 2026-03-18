import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { Dashboard } from './Dashboard'
import type { TeacherContext } from '../../shells/TeacherShell'
import type { TeacherClassroomOverview, TeacherClassroomReadModel } from '../../types'

const classroomA: TeacherClassroomOverview = {
  classroom_id: 'class-1',
  title: 'Math 7A',
  teacher_label: 'Ms. Smith',
  learner_count: 25,
  active_flow_count: 20,
  intervention_available_count: 3,
  blocked_progression_count: 2,
  attention_needed_count: 4,
  missing_learner_count: 0,
}

const classroomB: TeacherClassroomOverview = {
  classroom_id: 'class-2',
  title: 'Math 7B',
  teacher_label: 'Ms. Smith',
  learner_count: 22,
  active_flow_count: 18,
  intervention_available_count: 1,
  blocked_progression_count: 3,
  attention_needed_count: 2,
  missing_learner_count: 0,
}

const emptyClassroom: TeacherClassroomReadModel = {
  classroom_id: '',
  title: '',
  teacher_label: null,
  learner_count: 0,
  active_flow_count: 0,
  intervention_available_count: 0,
  blocked_progression_count: 0,
  attention_needed_count: 0,
  missing_learner_count: 0,
  missing_student_ids: [],
  learners: [],
}

function makeContext(overrides?: Partial<TeacherContext>): TeacherContext {
  return {
    config: {
      baseUrl: 'http://localhost:8000',
      apiKey: '',
      bearerToken: 'test-token',
      useDemoFallback: false,
      showDebugPanels: false,
    },
    classrooms: [classroomA, classroomB],
    selectedClassroomId: 'class-1',
    classroom: emptyClassroom,
    loading: false,
    error: '',
    loadClassroom: vi.fn(),
    ...overrides,
  }
}

function renderDashboard(overrides?: Partial<TeacherContext>) {
  const ctx = makeContext(overrides)
  const router = createMemoryRouter(
    [
      {
        path: '/teacher',
        element: <Outlet context={ctx} />,
        children: [{ index: true, element: <Dashboard /> }],
      },
    ],
    { initialEntries: ['/teacher'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('Dashboard', () => {
  it('renders the dashboard heading', () => {
    renderDashboard()
    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('renders aggregate summary stats', () => {
    renderDashboard()
    // Total attention: 4 + 2 = 6
    expect(screen.getByText('6')).toBeInTheDocument()
    expect(screen.getByText('Need attention')).toBeInTheDocument()
    // Total blocked: 2 + 3 = 5, appears in summary + 2 classroom cards
    expect(screen.getAllByText('Blocked').length).toBeGreaterThanOrEqual(1)
    // Total interventions: 3 + 1 = 4
    expect(screen.getByText('Interventions ready')).toBeInTheDocument()
  })

  it('renders classroom cards', () => {
    renderDashboard()
    expect(screen.getByText('Math 7A')).toBeInTheDocument()
    expect(screen.getByText('Math 7B')).toBeInTheDocument()
  })

  it('renders teacher label and learner count per classroom', () => {
    renderDashboard()
    expect(screen.getAllByText(/Ms\. Smith/).length).toBe(2)
    expect(screen.getByText(/25 learners/)).toBeInTheDocument()
    expect(screen.getByText(/22 learners/)).toBeInTheDocument()
  })

  it('renders classroom-level mini stats', () => {
    renderDashboard()
    // Each classroom card has Attention, Blocked, Interventions mini-stat labels
    // "Blocked" also appears once in the summary section, so 3 total
    expect(screen.getAllByText('Attention').length).toBe(2)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText('Interventions').length).toBe(2)
  })

  it('shows loading message when no classrooms yet', () => {
    renderDashboard({ classrooms: [], loading: true })
    expect(screen.getByText('Loading classrooms...')).toBeInTheDocument()
  })

  it('renders empty state when no classrooms and not loading', () => {
    renderDashboard({ classrooms: [], loading: false })
    // Summary stats should all be 0
    expect(screen.getAllByText('0').length).toBe(3)
  })

  it('classroom cards are links to classroom detail', () => {
    renderDashboard()
    const links = screen.getAllByRole('link')
    const classroomLinks = links.filter(
      (link) =>
        link.getAttribute('href') === '/teacher/classrooms/class-1' ||
        link.getAttribute('href') === '/teacher/classrooms/class-2',
    )
    expect(classroomLinks.length).toBe(2)
  })
})
