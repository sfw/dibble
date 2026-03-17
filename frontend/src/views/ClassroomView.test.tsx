import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { demoTeacherClassroom, demoTeacherClassrooms } from '../sample-data'
import { ClassroomView } from './ClassroomView'

describe('ClassroomView', () => {
  it('renders classroom summaries and learner cards and opens learner detail', async () => {
    const user = userEvent.setup()
    const onPickClassroom = vi.fn()
    const onOpenLearner = vi.fn()

    render(
      <ClassroomView
        classrooms={demoTeacherClassrooms}
        selectedClassroomId={demoTeacherClassroom.classroom_id}
        classroom={demoTeacherClassroom}
        onPickClassroom={onPickClassroom}
        onOpenLearner={onOpenLearner}
        showDebugPanels
      />,
    )

    expect(screen.getByText('Classroom attention and progression posture')).toBeInTheDocument()
    expect(screen.getAllByText('Grade 5 Fractions').length).toBeGreaterThan(0)
    expect(screen.getByText('Which learners need attention right now')).toBeInTheDocument()
    expect(screen.getByText('missing-student-id')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Open learner detail' })[0]!)

    expect(onOpenLearner).toHaveBeenCalledWith('11111111-1111-1111-1111-111111111111')
    expect(screen.getByText('Debug classroom payload')).toBeInTheDocument()
  })
})
