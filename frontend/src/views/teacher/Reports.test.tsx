import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    ready_resources: [
      {
        resource_id: 'res-1',
        title: 'Fractions Basics',
        state: 'ready',
        learning_objective_ids: ['lo-1'],
        knowledge_component_ids: ['kc-1'],
        blocked_prerequisite_kc_ids: [],
        mastery_ratio: 0.9,
        current_flow_aligned: false,
        target_stage: 'mastered',
      },
    ],
  },
  recent_activity: { generation_count: 5, observation_count: 8, socratic_assessment_count: 2 },
})

const learnerB = makeLearner({
  student_id: 'student-2',
  engagement: 'low',
  frustration: 'high',
  attention_level: 'high',
  attention_reasons: ['high_frustration', 'teacher_intervention_available'],
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
    current_resource: {
      resource_id: 'res-2',
      title: 'Decimal Operations',
      state: 'active',
      learning_objective_ids: ['lo-2'],
      knowledge_component_ids: ['kc-2'],
      blocked_prerequisite_kc_ids: [],
      mastery_ratio: 0.3,
      current_flow_aligned: true,
      target_stage: 'repair',
    },
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
    expect(screen.getAllByText('Blocked').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Interventions')).toBeInTheDocument()
    expect(screen.getAllByText('5')).toHaveLength(2)
  })

  it('renders classroom progress cards', () => {
    renderReports()
    // "Math 7A" appears in both the classroom card and the deep-dive header
    expect(screen.getAllByText('Math 7A').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Math 7B').length).toBeGreaterThanOrEqual(1)
  })

  it('renders stage distribution for loaded classroom', () => {
    renderReports()
    expect(screen.getByText('Stage distribution')).toBeInTheDocument()
    // Stage names appear in both distribution chart and learner table
    expect(screen.getAllByText('Repair').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Transfer').length).toBeGreaterThanOrEqual(1)
  })

  it('renders engagement and frustration overview', () => {
    renderReports()
    expect(screen.getByText('Engagement & frustration')).toBeInTheDocument()
    // "Engagement" and "Frustration" appear in both the overview and the learner table headers
    expect(screen.getAllByText('Engagement').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Frustration').length).toBeGreaterThanOrEqual(1)
  })

  it('renders recent activity totals', () => {
    renderReports()
    expect(screen.getByText('Recent activity')).toBeInTheDocument()
    expect(screen.getByText('Lessons generated')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('renders attention levels', () => {
    renderReports()
    expect(screen.getByText('Attention levels')).toBeInTheDocument()
    // "Urgent" and "On track" appear in both the attention summary and the learner table
    expect(screen.getAllByText('Urgent').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('On track').length).toBeGreaterThanOrEqual(1)
  })

  it('shows loading skeleton when no classrooms loaded yet', () => {
    renderReports({ classrooms: [], loading: true })
    // PageSkeleton renders pulse-animated skeleton elements
    expect(screen.queryByText('Reports')).not.toBeInTheDocument()
  })

  it('shows error banner when error is set', () => {
    renderReports({ error: 'Failed to load classrooms' })
    expect(screen.getByText('Failed to load classrooms')).toBeInTheDocument()
  })

  it('shows classroom learner count in breakdown header', () => {
    renderReports()
    expect(screen.getByText('Math 7A — learner breakdown')).toBeInTheDocument()
    expect(screen.getAllByText('2 learners').length).toBeGreaterThanOrEqual(1)
  })

  it('renders per-learner drill-down table', () => {
    renderReports()
    expect(screen.getByText('All learners')).toBeInTheDocument()
    expect(screen.getByText('student-1')).toBeInTheDocument()
    expect(screen.getByText('student-2')).toBeInTheDocument()
  })

  it('renders attention reasons in learner table', () => {
    renderReports()
    expect(screen.getByText('High frustration')).toBeInTheDocument()
    expect(screen.getByText('Intervention ready')).toBeInTheDocument()
  })

  it('renders sortable column headers in learner table', () => {
    renderReports()
    expect(screen.getByRole('button', { name: /Learner/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Stage/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Mastery/i })).toBeInTheDocument()
  })

  it('expands attention level to show learner drill-down', async () => {
    const user = userEvent.setup()
    renderReports()
    // Click the "Urgent" attention level row (has count 1)
    const urgentButton = screen.getAllByText('Urgent')[0].closest('button')
    if (urgentButton) {
      await user.click(urgentButton)
    }
    // student-2 is in the attention drill-down and in the main table
    expect(screen.getAllByText('student-2').length).toBeGreaterThanOrEqual(2)
  })

  it('renders classroom selector when multiple classrooms exist', () => {
    renderReports()
    expect(screen.getByText('Deep-dive into:')).toBeInTheDocument()
    const select = screen.getByRole('combobox')
    expect(select).toBeInTheDocument()
  })

  // --- New sections ---

  it('renders class average mastery banner', () => {
    renderReports()
    expect(screen.getByText('Class average mastery')).toBeInTheDocument()
    // Average of 0.8 and 0.2 = 50% — find within the banner context
    expect(screen.getAllByText('50%').length).toBeGreaterThanOrEqual(1)
  })

  it('renders on-track and at-risk counts in mastery banner', () => {
    renderReports()
    // student-1 (0.8) is on track, student-2 (0.2) is at risk
    expect(screen.getByText('On track (≥50%)')).toBeInTheDocument()
    expect(screen.getByText(/At risk/)).toBeInTheDocument()
  })

  it('renders mastery distribution histogram', () => {
    renderReports()
    expect(screen.getByText('Mastery distribution')).toBeInTheDocument()
    // Bucket labels
    expect(screen.getByText('0–25%')).toBeInTheDocument()
    expect(screen.getByText('25–50%')).toBeInTheDocument()
    expect(screen.getByText('50–75%')).toBeInTheDocument()
    expect(screen.getByText('75–100%')).toBeInTheDocument()
  })

  it('renders resource mastery breakdown', () => {
    renderReports()
    expect(screen.getByText('Resource mastery')).toBeInTheDocument()
    // Resources from learner fixture data
    expect(screen.getByText('Decimal Operations')).toBeInTheDocument()
    expect(screen.getByText('Fractions Basics')).toBeInTheDocument()
  })
})
