import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import {
  initialRemediationAdvancePrompt,
  initialRemediationForm,
  type RemediationFormState,
} from '../app/workspace'
import { demoGeneration, demoRemediationSession } from '../sample-data'
import type { RemediationWorkflowAdvanceResponse } from '../types'
import { RemediationView } from './RemediationView'

function RemediationHarness({
  onTrigger,
  onReload,
  onAdvance,
}: {
  onTrigger: () => void
  onReload: () => void
  onAdvance: () => void
}) {
  const [form, setForm] = useState<RemediationFormState>(initialRemediationForm)
  const [advancePrompt, setAdvancePrompt] = useState(initialRemediationAdvancePrompt)
  const advance: RemediationWorkflowAdvanceResponse = {
    session: demoRemediationSession,
    content: demoGeneration,
    executed_phase: 'repair',
  }

  return (
    <RemediationView
      form={form}
      onFormChange={setForm}
      loading={false}
      error=""
      content={demoGeneration}
      session={demoRemediationSession}
      advance={advance}
      advancePrompt={advancePrompt}
      onAdvancePromptChange={setAdvancePrompt}
      onTrigger={onTrigger}
      onReload={onReload}
      onAdvance={onAdvance}
    />
  )
}

describe('RemediationView', () => {
  it('renders remediation state, updates prompts, and triggers actions', async () => {
    const user = userEvent.setup()
    const onTrigger = vi.fn()
    const onReload = vi.fn()
    const onAdvance = vi.fn()

    render(<RemediationHarness onTrigger={onTrigger} onReload={onReload} onAdvance={onAdvance} />)

    const advancePrompt = screen.getByLabelText('Advance prompt')
    await user.clear(advancePrompt)
    await user.type(advancePrompt, 'Advance only after the learner explains the whole correctly.')

    expect(advancePrompt).toHaveValue('Advance only after the learner explains the whole correctly.')
    expect(screen.getByText('Current repair state')).toBeInTheDocument()
    expect(screen.getByText('Last executed phase:')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Trigger remediation' }))
    await user.click(screen.getByRole('button', { name: 'Reload session' }))
    await user.click(screen.getByRole('button', { name: 'Advance remediation session' }))

    expect(onTrigger).toHaveBeenCalledTimes(1)
    expect(onReload).toHaveBeenCalledTimes(1)
    expect(onAdvance).toHaveBeenCalledTimes(1)
  })
})
