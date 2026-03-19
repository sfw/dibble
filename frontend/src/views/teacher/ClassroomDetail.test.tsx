import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { ClassroomDetail } from './ClassroomDetail'
import type { TeacherContext } from '../../shells/TeacherShell'
import type { TeacherSectionReadModel, TeacherLearnerCard } from '../../types'

function makeLearner(overrides: Partial<TeacherLearnerCard> & { student_id: string }): TeacherLearnerCard {
  return {
    grade_level: '7',
    engagement: 'medium',
    frustration: 'low',
    current_flow: {
      status: 'active',
      flow_type: 'generation',
      current_phase: 'target',
      progression_action: 'hold_target',
      target_stage: 'target',
      active_target_kc_ids: [],
      deferred_target_kc_ids: [],
      transfer_target_kc_ids: [],
      session_phase: 'active',
      session_arc_action: 'stabilize',
      session_stuck_loop_risk: 'none',
      progression_source: 'flow',
      next_step_source: 'flow',
      next_step: { action: 'generate', target_stage: 'target', target_kc_ids: [] },
      continue_action: {
        kind: 'generate_follow_up',
        target_stage: 'target',
        target_kc_ids: [],
        request_payload: {},
      },
    },
    curriculum_progression: {
      status: 'active',
      source: 'flow',
      flow_type: 'generation',
      current_stage: 'target',
      progression_action: 'hold_target',
      active_target_kc_ids: [],
      resource_count: 5,
      mastered_resource_count: 2,
      ready_resource_count: 1,
      blocked_resource_count: 1,
      active_resource_count: 1,
      mastered_resource_ratio: 0.4,
      blocked_resources: [],
      ready_resources: [],
    },
    recent_activity: {
      generation_count: 3,
      observation_count: 5,
      socratic_assessment_count: 1,
    },
    intervention: {
      action_key: 'int-1',
      proposal_status: 'unavailable',
      recommended_action_kind: 'idle',
      option_count: 0,
    },
    attention_level: 'none',
    triage_section: 'on_track',
    attention_reasons: [],
    ...overrides,
  }
}

const learnerOnTrack = makeLearner({
  student_id: 'student-1',
  triage_section: 'on_track',
})

const learnerNeedsAttention = makeLearner({
  student_id: 'student-2',
  triage_section: 'needs_attention',
  attention_level: 'high',
  frustration: 'high',
})

const learnerTeacherAction = makeLearner({
  student_id: 'student-3',
  triage_section: 'teacher_action',
  intervention: {
    action_key: 'int-3',
    proposal_status: 'available',
    recommended_action_kind: 'generate_follow_up',
    option_count: 2,
  },
})

const mockClassroom: TeacherSectionReadModel = {
  section_id: 'class-1',
  title: 'Math 7A',
  teacher_label: 'Ms. Smith',
  learner_count: 3,
  active_flow_count: 3,
  blocked_progression_count: 0,
  intervention_available_count: 1,
  attention_needed_count: 1,
  missing_learner_count: 0,
  missing_student_ids: [],
  learners: [learnerTeacherAction, learnerNeedsAttention, learnerOnTrack],
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
    classrooms: [],
    selectedSectionId: 'class-1',
    classroom: mockClassroom,
    loading: false,
    error: '',
    loadSection: vi.fn(),
    ...overrides,
  }
}

function renderClassroomDetail(overrides?: Partial<TeacherContext>) {
  const ctx = makeContext(overrides)
  const router = createMemoryRouter(
    [
      {
        path: '/teacher',
        element: <Outlet context={ctx} />,
        children: [{ path: 'sections/:sectionId', element: <ClassroomDetail /> }],
      },
    ],
    { initialEntries: ['/teacher/sections/class-1'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('ClassroomDetail', () => {
  it('renders the classroom title', () => {
    renderClassroomDetail()
    expect(screen.getByText('Math 7A')).toBeInTheDocument()
  })

  it('renders teacher label and learner count', () => {
    renderClassroomDetail()
    expect(screen.getByText(/Ms\. Smith/)).toBeInTheDocument()
    expect(screen.getByText(/3 learners/)).toBeInTheDocument()
  })

  it('renders header badges for active, blocked, and interventions', () => {
    renderClassroomDetail()
    expect(screen.getByText('3 active')).toBeInTheDocument()
    expect(screen.getByText('0 blocked')).toBeInTheDocument()
    expect(screen.getByText('1 interventions')).toBeInTheDocument()
  })

  it('renders triage sections', () => {
    renderClassroomDetail()
    expect(screen.getByText('Needs teacher action')).toBeInTheDocument()
    expect(screen.getByText('Needs attention')).toBeInTheDocument()
    expect(screen.getByText('On track')).toBeInTheDocument()
  })

  it('renders learner rows with student ids', () => {
    renderClassroomDetail()
    expect(screen.getByText('student-1')).toBeInTheDocument()
    expect(screen.getByText('student-2')).toBeInTheDocument()
    expect(screen.getByText('student-3')).toBeInTheDocument()
  })

  it('shows intervene button for learner with available intervention', () => {
    renderClassroomDetail()
    expect(screen.getByText('Intervene')).toBeInTheDocument()
  })

  it('shows review button for all learners', () => {
    renderClassroomDetail()
    expect(screen.getAllByText('Review').length).toBe(3)
  })

  it('renders back to dashboard link', () => {
    renderClassroomDetail()
    expect(screen.getByText('Back to dashboard')).toBeInTheDocument()
  })

  it('shows refreshing message while loading', () => {
    renderClassroomDetail({ loading: true })
    expect(screen.getByText('Refreshing section...')).toBeInTheDocument()
  })

  it('shows empty group message when section has no learners', () => {
    const emptyClassroom: TeacherSectionReadModel = {
      ...mockClassroom,
      learners: [],
    }
    renderClassroomDetail({ classroom: emptyClassroom })
    // All three sections should show empty messages
    expect(screen.getAllByText('No learners in this group.').length).toBe(3)
  })

  it('links learner names to learner detail view', () => {
    renderClassroomDetail()
    const link = screen.getByRole('link', { name: 'student-1' })
    expect(link.getAttribute('href')).toBe('/teacher/learners/student-1')
  })
})
