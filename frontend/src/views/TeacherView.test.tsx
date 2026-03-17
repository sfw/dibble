import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { demoLearnerFlow, demoProfile, demoProfileSummary, teacherContractGaps } from '../sample-data'
import { TeacherView } from './TeacherView'

describe('TeacherView', () => {
  it('renders explainability signals and backend contract gaps', () => {
    render(
      <TeacherView
        summary={demoProfileSummary}
        profile={demoProfile}
        flow={demoLearnerFlow}
        gaps={teacherContractGaps}
        dataSource="live"
      />,
    )

    expect(screen.getByText('Intervention readiness and rationale')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'practice_problem' })).toBeInTheDocument()
    expect(screen.getByText('Action deliver on transfer')).toBeInTheDocument()
    expect(screen.getByText('backend-connected')).toBeInTheDocument()
    expect(screen.getByText('Compact explainability payload')).toBeInTheDocument()
    expect(screen.getByText('What the frontend still cannot delegate cleanly to the backend')).toBeInTheDocument()

    for (const gap of teacherContractGaps) {
      expect(screen.getByText(gap.title)).toBeInTheDocument()
      expect(screen.getByText(gap.frontend_response)).toBeInTheDocument()
    }
  })
})
