import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { demoLearnerFlow, demoProfile, demoProfileSummary } from '../sample-data'
import { OverviewView } from './OverviewView'

describe('OverviewView', () => {
  it('renders learner summary, current flow, and explainability details', () => {
    render(
      <OverviewView
        summary={demoProfileSummary}
        profile={demoProfile}
        flow={demoLearnerFlow}
        showDebugPanels
      />,
    )

    expect(screen.getByText('Current learning posture')).toBeInTheDocument()
    expect(screen.getByText('check_transfer_readiness')).toBeInTheDocument()
    expect(screen.getByText('Teacher-safe explainability surface')).toBeInTheDocument()
    expect(screen.getByText('extended_time')).toBeInTheDocument()
    expect(screen.getByText('Debug contract payload')).toBeInTheDocument()
  })
})
