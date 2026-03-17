import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  demoCurriculumProgression,
  demoGenerationHistory,
  demoLearnerFlow,
  demoLearnerWorkspace,
  demoProfile,
  demoProfileSummary,
  demoRemediationHistory,
  demoSocraticHistory,
} from '../sample-data'
import { OverviewView } from './OverviewView'

describe('OverviewView', () => {
  it('renders learner summary, workspace resume, history, and explainability details', () => {
    render(
      <OverviewView
        summary={demoProfileSummary}
        profile={demoProfile}
        flow={demoLearnerFlow}
        workspace={demoLearnerWorkspace}
        progression={demoCurriculumProgression}
        generationHistory={demoGenerationHistory}
        socraticHistory={demoSocraticHistory}
        remediationHistory={demoRemediationHistory}
        onSelectView={() => {}}
        showDebugPanels
      />,
    )

    expect(screen.getByText('Current learning posture')).toBeInTheDocument()
    expect(screen.getByText('Resume from the backend-owned workspace')).toBeInTheDocument()
    expect(screen.getByText('Where this learner sits in the broader curriculum')).toBeInTheDocument()
    expect(screen.getByText('Equivalent Fraction Practice')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open generated content workspace' })).toBeInTheDocument()
    expect(screen.getByText('Recent generated, Socratic, and remediation work')).toBeInTheDocument()
    expect(screen.getByText('Generated content')).toBeInTheDocument()
    expect(screen.getByText('check_transfer_readiness')).toBeInTheDocument()
    expect(screen.getByText('Teacher-safe explainability surface')).toBeInTheDocument()
    expect(screen.getByText('extended_time')).toBeInTheDocument()
    expect(screen.getByText('Debug contract payload')).toBeInTheDocument()
  })

  it('falls back to the active artifact when the workspace continue action is idle', () => {
    render(
      <OverviewView
        summary={demoProfileSummary}
        profile={demoProfile}
        flow={demoLearnerFlow}
        workspace={{
          ...demoLearnerWorkspace,
          continue_action: {
            ...demoLearnerWorkspace.continue_action,
            kind: 'idle',
          },
        }}
        progression={demoCurriculumProgression}
        generationHistory={demoGenerationHistory}
        socraticHistory={demoSocraticHistory}
        remediationHistory={demoRemediationHistory}
        onSelectView={() => {}}
      />,
    )

    expect(screen.getByRole('button', { name: 'Open generated content workspace' })).toBeInTheDocument()
  })
})
