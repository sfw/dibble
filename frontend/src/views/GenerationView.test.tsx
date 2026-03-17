import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { initialGenerationForm, type GenerationFormState } from '../app/workspace'
import { demoGeneration } from '../sample-data'
import type { GeneratedBlock } from '../types'
import { GenerationView } from './GenerationView'

function GenerationHarness({
  onGenerate,
  onStream,
  streamedBlocks,
}: {
  onGenerate: () => void
  onStream: () => void
  streamedBlocks?: GeneratedBlock[]
}) {
  const [form, setForm] = useState<GenerationFormState>(initialGenerationForm)

  return (
    <GenerationView
      form={form}
      onFormChange={setForm}
      loading={false}
      error=""
      result={demoGeneration}
      streaming={false}
      streamEvents={[]}
      streamedBlocks={streamedBlocks ?? []}
      onGenerate={onGenerate}
      onStream={onStream}
    />
  )
}

describe('GenerationView', () => {
  it('renders streamed blocks, updates form fields, and triggers actions', async () => {
    const user = userEvent.setup()
    const onGenerate = vi.fn()
    const onStream = vi.fn()

    render(
      <GenerationHarness
        onGenerate={onGenerate}
        onStream={onStream}
        streamedBlocks={[
          {
            kind: 'hint',
            title: 'Streamed block',
            body: 'Use the current flow summary before broadening the task.',
          },
        ]}
      />,
    )

    const sessionInput = screen.getByLabelText('Learning session ID')
    await user.clear(sessionInput)
    await user.type(sessionInput, 'session-stream-check')

    expect(sessionInput).toHaveValue('session-stream-check')
    expect(screen.getByText('Streamed block')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Generate response' }))
    await user.click(screen.getByRole('button', { name: 'Stream via SSE' }))

    expect(onGenerate).toHaveBeenCalledTimes(1)
    expect(onStream).toHaveBeenCalledTimes(1)
  })
})
