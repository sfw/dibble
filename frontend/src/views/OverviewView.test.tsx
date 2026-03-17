import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

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
    expect(screen.getAllByText('Continue generated content').length).toBeGreaterThan(0)
    expect(screen.getByText('Recent generated, Socratic, and remediation work')).toBeInTheDocument()
    expect(screen.getAllByText('Generated content').length).toBeGreaterThan(0)
    expect(screen.getByText('Check Transfer Readiness')).toBeInTheDocument()
    expect(screen.getByText('Teacher-safe explainability surface')).toBeInTheDocument()
    expect(screen.getByText('Extended Time')).toBeInTheDocument()
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

  it('renders contract refresh and empty-history states', () => {
    render(
      <OverviewView
        summary={demoProfileSummary}
        profile={demoProfile}
        flow={demoLearnerFlow}
        workspace={demoLearnerWorkspace}
        progression={demoCurriculumProgression}
        generationHistory={[]}
        socraticHistory={[]}
        remediationHistory={[]}
        contractsLoading
        contractsError="Workspace contracts failed to refresh."
        onSelectView={() => {}}
      />,
    )

    expect(screen.getByText('Refreshing workspace contracts…')).toBeInTheDocument()
    expect(screen.getByText('Workspace contracts failed to refresh.')).toBeInTheDocument()
    expect(screen.getAllByText('Nothing to review yet').length).toBeGreaterThan(0)
  })

  it('routes resume and history actions through the selected view callback', async () => {
    const user = userEvent.setup()
    const onSelectView = vi.fn()

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
        onSelectView={onSelectView}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Open generated content workspace' }))
    await user.click(screen.getAllByRole('button', { name: 'Open generation' })[0]!)
    await user.click(screen.getByRole('button', { name: 'Open Socratic' }))
    await user.click(screen.getByRole('button', { name: 'Open remediation' }))

    expect(onSelectView).toHaveBeenNthCalledWith(1, 'generation')
    expect(onSelectView).toHaveBeenNthCalledWith(2, 'generation')
    expect(onSelectView).toHaveBeenNthCalledWith(3, 'socratic')
    expect(onSelectView).toHaveBeenNthCalledWith(4, 'remediation')
  })
})
