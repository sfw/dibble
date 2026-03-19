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
        selectedSectionId={demoTeacherClassroom.section_id}
        classroom={demoTeacherClassroom}
        onPickClassroom={onPickClassroom}
        onOpenTeacher={onOpenTeacher}
        onContinueLearner={onContinueLearner}
        showDebugPanels
      />,
    )

    expect(screen.getByText('Section attention and progression posture')).toBeInTheDocument()
    expect(screen.getAllByText('Grade 5 Fractions').length).toBeGreaterThan(0)
    expect(screen.getByText('Move from section posture to learner action handoff')).toBeInTheDocument()
    expect(screen.getByText('Needs teacher action now')).toBeInTheDocument()
    expect(screen.getByText('Needs attention')).toBeInTheDocument()
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
    expect(screen.getByText('Debug section payload')).toBeInTheDocument()
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
            section_id: 'CLASS-2',
            title: 'Grade 5 Decimals',
            learner_count: 3,
          },
        ]}
        selectedSectionId={demoTeacherClassroom.section_id}
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
        selectedSectionId={demoTeacherClassroom.section_id}
        classroom={{ ...demoTeacherClassroom, learners: [] }}
        loading
        error="Section contracts failed to refresh."
        onPickClassroom={() => {}}
        onOpenTeacher={() => {}}
        onContinueLearner={() => {}}
      />,
    )

    expect(screen.getByText('Refreshing section contracts…')).toBeInTheDocument()
    expect(screen.getByText('Section contracts failed to refresh.')).toBeInTheDocument()
    expect(screen.getAllByText('No learners in this queue').length).toBeGreaterThan(0)
  })

  describe('collapsible triage sections', () => {
    it('shows learner count badges in section titles', () => {
      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      // Each triage section header shows the learner count as a badge
      // The demo data has 1 learner in teacher-action and 1 in needs-attention, so there are multiple "1 learner" badges
      expect(screen.getAllByText('1 learner').length).toBeGreaterThanOrEqual(2)
    })

    it('collapses the on-track section by default and expands on click', async () => {
      const user = userEvent.setup()

      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      // The on-track section toggle button should have aria-expanded=false
      const sectionButtons = screen.getAllByRole('button', { expanded: false })
      const onTrackButton = sectionButtons.find((btn) =>
        btn.textContent?.includes('Ready for learner workflow handoff'),
      )
      expect(onTrackButton).toBeTruthy()

      // Intervention sections should be expanded
      const expandedButtons = screen.getAllByRole('button', { expanded: true })
      const teacherActionButton = expandedButtons.find((btn) =>
        btn.textContent?.includes('Needs teacher action now'),
      )
      expect(teacherActionButton).toBeTruthy()

      // Click to expand on-track section
      await user.click(onTrackButton!)
      expect(onTrackButton).toHaveAttribute('aria-expanded', 'true')
    })

    it('collapses an expanded section on click', async () => {
      const user = userEvent.setup()

      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      const expandedButtons = screen.getAllByRole('button', { expanded: true })
      const teacherActionButton = expandedButtons.find((btn) =>
        btn.textContent?.includes('Needs teacher action now'),
      )
      expect(teacherActionButton).toBeTruthy()

      await user.click(teacherActionButton!)
      expect(teacherActionButton).toHaveAttribute('aria-expanded', 'false')
    })
  })

  describe('filter bar', () => {
    it('filters learners by student ID search', async () => {
      const user = userEvent.setup()

      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      const searchInput = screen.getByLabelText('Search by student ID')
      await user.type(searchInput, '11111')

      // Should show filtered count
      expect(screen.getByTestId('filter-count')).toHaveTextContent('1 of 2 learners')

      // The first learner should still be visible
      expect(screen.getByText('11111111-1111-1111-1111-111111111111')).toBeInTheDocument()
    })

    it('filters by intervention toggle', async () => {
      const user = userEvent.setup()

      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      const interventionButton = screen.getByLabelText('Filter by intervention')
      await user.click(interventionButton)

      expect(screen.getByTestId('filter-count')).toHaveTextContent('1 of 2 learners')
    })

    it('does not show filter count when no filters are active', () => {
      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      expect(screen.queryByTestId('filter-count')).not.toBeInTheDocument()
    })
  })

  describe('compact layout toggle', () => {
    it('switches to compact layout on toggle', async () => {
      const user = userEvent.setup()

      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      // Card layout should be active by default
      const cardButton = screen.getByLabelText('Card layout')
      const compactButton = screen.getByLabelText('Compact layout')
      expect(cardButton).toHaveAttribute('aria-pressed', 'true')
      expect(compactButton).toHaveAttribute('aria-pressed', 'false')

      // Switch to compact
      await user.click(compactButton)
      expect(compactButton).toHaveAttribute('aria-pressed', 'true')
      expect(cardButton).toHaveAttribute('aria-pressed', 'false')

      // In compact mode, the summary grid should be hidden (not present without expanding)
      // The compact card has a Triage button instead of 'Open teacher triage'
      expect(screen.getAllByRole('button', { name: /Triage/i }).length).toBeGreaterThan(0)
    })

    it('expands compact card details on click', async () => {
      const user = userEvent.setup()

      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      // Switch to compact
      await user.click(screen.getByLabelText('Compact layout'))

      // Find the expand button for the first learner in teacher-action section
      const expandButton = screen.getByLabelText(/Expand details for 11111111/)
      expect(expandButton).toHaveAttribute('aria-expanded', 'false')

      await user.click(expandButton)
      expect(expandButton).toHaveAttribute('aria-expanded', 'true')

      // Now the rationale / detail grid should be visible
      expect(screen.getByText('Current phase')).toBeInTheDocument()
    })

    it('switches back to card layout', async () => {
      const user = userEvent.setup()

      render(
        <ClassroomView
          classrooms={demoTeacherClassrooms}
          selectedSectionId={demoTeacherClassroom.section_id}
          classroom={demoTeacherClassroom}
          onPickClassroom={() => {}}
          onOpenTeacher={() => {}}
          onContinueLearner={() => {}}
        />,
      )

      // Switch to compact then back to card
      await user.click(screen.getByLabelText('Compact layout'))
      await user.click(screen.getByLabelText('Card layout'))

      // Card layout should show the full triage buttons
      expect(screen.getAllByRole('button', { name: 'Open teacher triage' }).length).toBeGreaterThan(0)
    })
  })
})
