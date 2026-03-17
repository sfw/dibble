import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { initialSocraticForm, type SocraticFormState } from '../app/workspace'
import { demoSocraticResponse, demoSocraticSession } from '../sample-data'
import { SocraticView } from './SocraticView'

function SocraticHarness({
  onRun,
  onReload,
}: {
  onRun: () => void
  onReload: () => void
}) {
  const [form, setForm] = useState<SocraticFormState>({
    ...initialSocraticForm,
    session_id: demoSocraticResponse.session_id,
  })

  return (
    <SocraticView
      form={form}
      onFormChange={setForm}
      loading={false}
      error=""
      response={demoSocraticResponse}
      session={demoSocraticSession}
      onRun={onRun}
      onReload={onReload}
    />
  )
}

describe('SocraticView', () => {
  it('renders session summary, updates learner response, and triggers actions', async () => {
    const user = userEvent.setup()
    const onRun = vi.fn()
    const onReload = vi.fn()

    render(<SocraticHarness onRun={onRun} onReload={onReload} />)

    const responseInput = screen.getByLabelText('Learner response')
    await user.clear(responseInput)
    await user.type(responseInput, 'I can now explain why the whole stays constant.')

    expect(responseInput).toHaveValue('I can now explain why the whole stays constant.')
    expect(screen.getByText('Conversation summary')).toBeInTheDocument()
    expect(screen.getByText('Prompt')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Run Socratic turn' }))
    await user.click(screen.getByRole('button', { name: 'Load persisted session' }))

    expect(onRun).toHaveBeenCalledTimes(1)
    expect(onReload).toHaveBeenCalledTimes(1)
  })
})
