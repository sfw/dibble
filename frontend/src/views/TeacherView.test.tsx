import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import {
  demoCurriculumProgression,
  demoLearnerFlow,
  demoProfile,
  demoProfileSummary,
  demoTeacherInterventionAction,
  teacherContractGaps,
} from '../sample-data'
import { TeacherView } from './TeacherView'

describe('TeacherView', () => {
  it('renders intervention controls, latest decision data, and remaining contract gaps', async () => {
    const user = userEvent.setup()
    const onSubmitDecision = vi.fn()
    const onReturnToClassroom = vi.fn()

    render(
      <TeacherView
        summary={demoProfileSummary}
        profile={demoProfile}
        flow={demoLearnerFlow}
        progression={demoCurriculumProgression}
        intervention={demoTeacherInterventionAction}
        gaps={teacherContractGaps}
        dataSource="live"
        onSubmitDecision={onSubmitDecision}
        handoffContext={{
          classroomId: 'CLASS-1',
          classroomTitle: 'Grade 5 Fractions',
          learnerId: demoProfileSummary.student_id,
        }}
        onReturnToClassroom={onReturnToClassroom}
        showDebugPanels
      />,
    )

    expect(
      screen.getByText(`Reviewing ${demoProfileSummary.student_id} from Grade 5 Fractions`),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Return to section' })).toBeInTheDocument()
    expect(screen.getByText('Intervention readiness and rationale')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Hold with one more worked example' })).toBeInTheDocument()
    expect(screen.getByText('How learner flow aligns to curriculum posture')).toBeInTheDocument()
    expect(screen.getByText('Review the backend-owned intervention proposal')).toBeInTheDocument()
    expect(screen.getAllByText('Send transfer practice').length).toBeGreaterThan(0)
    expect(screen.getByText('worked_example_support_reset')).toBeInTheDocument()
    expect(screen.getByText('Latest recorded decision')).toBeInTheDocument()
    expect(screen.getByText('backend-connected')).toBeInTheDocument()
    expect(screen.getByText('Debug explainability payload')).toBeInTheDocument()
    expect(screen.getByText('Product-expansion areas not yet built')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await user.click(screen.getByRole('button', { name: 'Return to section' }))

    expect(onSubmitDecision).toHaveBeenCalledWith({
      decision: 'approve',
      option_id: null,
      note: null,
    })
    expect(onReturnToClassroom).toHaveBeenCalled()

    for (const gap of teacherContractGaps) {
      expect(screen.getByText(gap.title)).toBeInTheDocument()
      expect(screen.getByText(gap.frontend_response)).toBeInTheDocument()
    }
  })

  it('submits selected teacher options and notes against the intervention contract', async () => {
    const user = userEvent.setup()
    const onSubmitDecision = vi.fn()

    render(
      <TeacherView
        summary={demoProfileSummary}
        profile={demoProfile}
        flow={demoLearnerFlow}
        progression={demoCurriculumProgression}
        intervention={demoTeacherInterventionAction}
        gaps={teacherContractGaps}
        dataSource="live"
        onSubmitDecision={onSubmitDecision}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Return to remediation/i }))
    await user.type(screen.getByLabelText('Teacher note'), 'Observed repeated numerator-only reasoning.')
    await user.click(screen.getByRole('button', { name: 'Select option' }))

    expect(onSubmitDecision).toHaveBeenCalledWith({
      decision: 'select_option',
      option_id: 'continue_remediation',
      note: 'Observed repeated numerator-only reasoning.',
    })
    expect(screen.getAllByText('Return to remediation').length).toBeGreaterThan(0)
    expect(screen.getByText('/api/remedial/sessions/rem-demo-1/advance')).toBeInTheDocument()
  })

  it('renders intervention loading and submission-error states', () => {
    render(
      <TeacherView
        summary={demoProfileSummary}
        profile={demoProfile}
        flow={demoLearnerFlow}
        progression={demoCurriculumProgression}
        intervention={demoTeacherInterventionAction}
        gaps={teacherContractGaps}
        dataSource="demo"
        loading
        submissionError="Intervention decision failed."
        onSubmitDecision={() => {}}
      />,
    )

    expect(screen.getByText('Refreshing intervention contract…')).toBeInTheDocument()
    expect(screen.getByText('Intervention decision failed.')).toBeInTheDocument()
  })
})
