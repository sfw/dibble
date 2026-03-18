import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AffectiveSupport } from './AffectiveSupport'
import type { ProfileSummary, SignalLevel } from '../../types'

function makeSummary(overrides: { engagement?: SignalLevel; frustration?: SignalLevel } = {}): ProfileSummary {
  return {
    student_id: 'test-student',
    grade_level: '5',
    profile_version: '1',
    kc_count: 10,
    lo_count: 5,
    engagement: overrides.engagement ?? 'medium',
    frustration: overrides.frustration ?? 'low',
    total_load: 0.5,
    confidence_calibration: 0.7,
    help_seeking: 'low',
    calibration: {} as ProfileSummary['calibration'],
    progress: {} as ProfileSummary['progress'],
    strategy: {} as ProfileSummary['strategy'],
    state_profile: {} as ProfileSummary['state_profile'],
    trait_profile: {} as ProfileSummary['trait_profile'],
    recent_activity: { generation_count: 0, observation_count: 0, socratic_assessment_count: 0 },
    current_flow: {} as ProfileSummary['current_flow'],
    curriculum_progression: {} as ProfileSummary['curriculum_progression'],
    updated_at: '2026-01-01T00:00:00Z',
  }
}

describe('AffectiveSupport', () => {
  it('shows break message when frustration is high', () => {
    render(<AffectiveSupport summary={makeSummary({ frustration: 'high' })} />)
    expect(screen.getByText("It's okay to take a break")).toBeInTheDocument()
  })

  it('shows nudge message when frustration is medium', () => {
    render(<AffectiveSupport summary={makeSummary({ frustration: 'medium' })} />)
    expect(screen.getByText('Need a different approach?')).toBeInTheDocument()
  })

  it('shows encouragement when engagement is high and frustration is low', () => {
    render(<AffectiveSupport summary={makeSummary({ engagement: 'high', frustration: 'low' })} />)
    expect(screen.getByText("You're on a roll!")).toBeInTheDocument()
  })

  it('prioritizes frustration over engagement', () => {
    render(<AffectiveSupport summary={makeSummary({ engagement: 'high', frustration: 'high' })} />)
    expect(screen.getByText("It's okay to take a break")).toBeInTheDocument()
    expect(screen.queryByText("You're on a roll!")).not.toBeInTheDocument()
  })

  it('renders nothing when both signals are neutral', () => {
    const { container } = render(
      <AffectiveSupport summary={makeSummary({ engagement: 'medium', frustration: 'low' })} />,
    )
    expect(container.innerHTML).toBe('')
  })
})
