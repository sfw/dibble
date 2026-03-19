import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SetupConnectStep } from './SetupConnectStep'

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
  vi.restoreAllMocks()
})

describe('SetupConnectStep', () => {
  it('keeps the typed URL local until the connection succeeds', async () => {
    const onBaseUrlChange = vi.fn()

    render(
      <SetupConnectStep
        baseUrl="http://127.0.0.1:8000"
        onBaseUrlChange={onBaseUrlChange}
        onNext={vi.fn()}
      />,
    )

    const input = screen.getByLabelText('Server URL')
    await userEvent.clear(input)
    await userEvent.type(input, 'http://localhost:9000')

    expect(input).toHaveValue('http://localhost:9000')
    expect(onBaseUrlChange).not.toHaveBeenCalled()
  })

  it('persists the tested URL after a successful connection check', async () => {
    const onBaseUrlChange = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' }),
    })
    globalThis.fetch = fetchMock as typeof fetch

    render(
      <SetupConnectStep
        baseUrl="http://127.0.0.1:8000"
        onBaseUrlChange={onBaseUrlChange}
        onNext={vi.fn()}
      />,
    )

    const input = screen.getByLabelText('Server URL')
    await userEvent.clear(input)
    await userEvent.type(input, 'http://localhost:9000')
    await userEvent.click(screen.getByRole('button', { name: 'Test connection' }))

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:9000/health')
    expect(onBaseUrlChange).toHaveBeenCalledWith('http://localhost:9000')
    expect(screen.getByText('Connected successfully.')).toBeInTheDocument()
  })
})
