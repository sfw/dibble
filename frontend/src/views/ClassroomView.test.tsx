import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { demoTeacherClassroom, demoTeacherClassrooms } from '../sample-data'
import { ClassroomView } from './ClassroomView'

describe('ClassroomView', () => {
  it('renders classroom summaries and learner cards and opens learner detail', async () => {
    const user = userEvent.setup()
    const onPickClassroom = vi.fn()
    const onOpenTeacher = vi.fn()
    const onContinueLearner = vi.fn()

    render(
      <ClassroomView
        classrooms={demoTeacherClassrooms}
        selectedClassroomId={demoTeacherClassroom.classroom_id}
        classroom={demoTeacherClassroom}
        onPickClassroom={onPickClassroom}
        onOpenTeacher={onOpenTeacher}
        onContinueLearner={onContinueLearner}
        showDebugPanels
      />,
    )

    expect(screen.getByText('Classroom attention and progression posture')).toBeInTheDocument()
    expect(screen.getAllByText('Grade 5 Fractions').length).toBeGreaterThan(0)
    expect(screen.getByText('Move from classroom posture to learner action handoff')).toBeInTheDocument()
    expect(screen.getByText('Needs teacher action now')).toBeInTheDocument()
    expect(screen.getByText('Blocked until prerequisites shift')).toBeInTheDocument()
    expect(screen.getByText('Teacher intervention ready')).toBeInTheDocument()
    expect(screen.getByText('missing-student-id')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue generated content' })).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Open teacher triage' })[0]!)
    await user.click(screen.getByRole('button', { name: 'Continue generated content' }))

    expect(onOpenTeacher).toHaveBeenCalledWith('11111111-1111-1111-1111-111111111111')
    expect(onContinueLearner).toHaveBeenCalledWith(
      '11111111-1111-1111-1111-111111111111',
      'generate_follow_up',
    )
    expect(screen.getByText('Debug classroom payload')).toBeInTheDocument()
  })

  it('lets the teacher switch classrooms and keeps blocked learners in teacher-first posture', async () => {
    const user = userEvent.setup()
    const onPickClassroom = vi.fn()

    render(
      <ClassroomView
        classrooms={[
          ...demoTeacherClassrooms,
          {
            ...demoTeacherClassrooms[0],
            classroom_id: 'CLASS-2',
            title: 'Grade 5 Decimals',
            learner_count: 3,
          },
        ]}
        selectedClassroomId={demoTeacherClassroom.classroom_id}
        classroom={demoTeacherClassroom}
        onPickClassroom={onPickClassroom}
        onOpenTeacher={() => {}}
        onContinueLearner={() => {}}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Grade 5 Decimals/i }))

    expect(onPickClassroom).toHaveBeenCalledWith('CLASS-2')
    expect(screen.getByText('Teacher review first')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Continue learner overview' })).not.toBeInTheDocument()
  })

  it('renders classroom refresh, error, and empty-queue states', () => {
    render(
      <ClassroomView
        classrooms={demoTeacherClassrooms}
        selectedClassroomId={demoTeacherClassroom.classroom_id}
        classroom={{ ...demoTeacherClassroom, learners: [] }}
        loading
        error="Classroom contracts failed to refresh."
        onPickClassroom={() => {}}
        onOpenTeacher={() => {}}
        onContinueLearner={() => {}}
      />,
    )

    expect(screen.getByText('Refreshing classroom contracts…')).toBeInTheDocument()
    expect(screen.getByText('Classroom contracts failed to refresh.')).toBeInTheDocument()
    expect(screen.getAllByText('No learners in this queue').length).toBeGreaterThan(0)
  })
})
