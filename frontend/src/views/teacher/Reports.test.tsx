import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router'
import { Reports } from './Reports'
import type { TeacherContext } from '../../shells/TeacherShell'
import type { TeacherClassroomReadModel, TeacherClassroomOverview, TeacherLearnerCard } from '../../types'

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

const learnerA = makeLearner({
  student_id: 'student-1',
  engagement: 'high',
  frustration: 'none',
  attention_level: 'none',
  curriculum_progression: {
    status: 'active',
    source: 'flow',
    flow_type: 'generation',
    current_stage: 'transfer',
    progression_action: 'advance_to_transfer',
    active_target_kc_ids: [],
    resource_count: 5,
    mastered_resource_count: 4,
    ready_resource_count: 0,
    blocked_resource_count: 0,
    active_resource_count: 1,
    mastered_resource_ratio: 0.8,
    blocked_resources: [],
    ready_resources: [],
  },
  recent_activity: { generation_count: 5, observation_count: 8, socratic_assessment_count: 2 },
})

const learnerB = makeLearner({
  student_id: 'student-2',
  engagement: 'low',
  frustration: 'high',
  attention_level: 'high',
  curriculum_progression: {
    status: 'active',
    source: 'flow',
    flow_type: 'remediation',
    current_stage: 'repair',
    progression_action: 'hold_repair_target',
    active_target_kc_ids: [],
    resource_count: 5,
    mastered_resource_count: 1,
    ready_resource_count: 0,
    blocked_resource_count: 2,
    active_resource_count: 2,
    mastered_resource_ratio: 0.2,
    blocked_resources: [],
    ready_resources: [],
  },
  recent_activity: { generation_count: 2, observation_count: 3, socratic_assessment_count: 0 },
})

const mockClassroom: TeacherClassroomReadModel = {
  classroom_id: 'class-1',
  title: 'Math 7A',
  teacher_label: 'Ms. Smith',
  learner_count: 2,
  active_flow_count: 2,
  blocked_progression_count: 1,
  intervention_available_count: 0,
  attention_needed_count: 1,
  missing_learner_count: 0,
  missing_student_ids: [],
  learners: [learnerA, learnerB],
}

const mockClassrooms: TeacherClassroomOverview[] = [
  {
    classroom_id: 'class-1',
    title: 'Math 7A',
    teacher_label: 'Ms. Smith',
    learner_count: 2,
    active_flow_count: 2,
    blocked_progression_count: 1,
    intervention_available_count: 0,
    attention_needed_count: 1,
    missing_learner_count: 0,
  },
  {
    classroom_id: 'class-2',
    title: 'Math 7B',
    teacher_label: 'Ms. Smith',
    learner_count: 3,
    active_flow_count: 3,
    blocked_progression_count: 0,
    intervention_available_count: 1,
    attention_needed_count: 0,
    missing_learner_count: 0,
  },
]

const context: TeacherContext = {
  config: {
    baseUrl: 'http://localhost:8000',
    apiKey: '',
    bearerToken: 'test-token',
    useDemoFallback: false,
    showDebugPanels: false,
  },
  classrooms: mockClassrooms,
  selectedClassroomId: 'class-1',
  classroom: mockClassroom,
  loading: false,
  error: '',
  loadClassroom: vi.fn(),
}

function renderReports(overrides?: Partial<TeacherContext>) {
  const ctx = { ...context, ...overrides }
  const router = createMemoryRouter(
    [
      {
        path: '/teacher',
        element: <Outlet context={ctx} />,
        children: [{ path: 'reports', element: <Reports /> }],
      },
    ],
    { initialEntries: ['/teacher/reports'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('Reports', () => {
  it('renders the page heading', () => {
    renderReports()
    expect(screen.getByRole('heading', { name: 'Reports' })).toBeInTheDocument()
  })

  it('renders top-line summary cards with aggregated counts', () => {
    renderReports()
    expect(screen.getByText('Total learners')).toBeInTheDocument()
    expect(screen.getByText('Active now')).toBeInTheDocument()
    expect(screen.getByText('Need attention')).toBeInTheDocument()
    // "Blocked" appears in both summary card and classroom progress cards
    expect(screen.getAllByText('Blocked').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Interventions')).toBeInTheDocument()
    // 5 total learners and 5 active — both render as "5"
    expect(screen.getAllByText('5')).toHaveLength(2)
  })

  it('renders classroom progress cards', () => {
    renderReports()
    expect(screen.getByText('Math 7A')).toBeInTheDocument()
    expect(screen.getByText('Math 7B')).toBeInTheDocument()
  })

  it('renders stage distribution for loaded classroom', () => {
    renderReports()
    expect(screen.getByText('Stage distribution')).toBeInTheDocument()
    expect(screen.getByText('Repair')).toBeInTheDocument()
    expect(screen.getByText('Transfer')).toBeInTheDocument()
  })

  it('renders engagement and frustration overview', () => {
    renderReports()
    expect(screen.getByText('Engagement & frustration')).toBeInTheDocument()
    expect(screen.getByText('Engagement')).toBeInTheDocument()
    expect(screen.getByText('Frustration')).toBeInTheDocument()
  })

  it('renders recent activity totals', () => {
    renderReports()
    expect(screen.getByText('Recent activity')).toBeInTheDocument()
    expect(screen.getByText('Lessons generated')).toBeInTheDocument()
    // 5 + 2 = 7 total generations
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('renders attention levels', () => {
    renderReports()
    expect(screen.getByText('Attention levels')).toBeInTheDocument()
    expect(screen.getByText('Urgent')).toBeInTheDocument()
    expect(screen.getByText('On track')).toBeInTheDocument()
  })

  it('shows loading state when no classrooms', () => {
    renderReports({ classrooms: [], loading: true })
    expect(screen.getByText('Loading report data...')).toBeInTheDocument()
  })

  it('shows classroom learner count in breakdown header', () => {
    renderReports()
    expect(screen.getByText('Math 7A — learner breakdown')).toBeInTheDocument()
    // "2 learners" appears in both the classroom progress card and the breakdown badge
    expect(screen.getAllByText('2 learners').length).toBeGreaterThanOrEqual(1)
  })
})
