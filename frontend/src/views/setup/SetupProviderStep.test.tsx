import { useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { SetupProviderStep } from './SetupProviderStep'
import type { SetupConfigureRequest } from '../../types'
import { postSetupModelCatalog } from '../../api'

vi.mock('../../api', () => ({
  postSetupModelCatalog: vi.fn(),
}))

const mockedPostSetupModelCatalog = vi.mocked(postSetupModelCatalog)

function renderProviderStep(initialConfig: SetupConfigureRequest) {
  function Wrapper() {
    const [config, setConfig] = useState<SetupConfigureRequest>(initialConfig)

    return (
      <SetupProviderStep
        baseUrl="http://127.0.0.1:8000"
        config={config}
        onConfigChange={setConfig}
        onNext={vi.fn()}
        onBack={vi.fn()}
      />
    )
  }

  return render(<Wrapper />)
}

describe('SetupProviderStep', () => {
  beforeEach(() => {
    mockedPostSetupModelCatalog.mockReset()
  })

  it('loads models and auto-fills the first model when provider credentials are present', async () => {
    mockedPostSetupModelCatalog.mockResolvedValue({
      models: ['gpt-4o', 'gpt-4o-mini'],
    })

    renderProviderStep({
      llm_api_base: 'https://api.example.com/v1',
      llm_api_key: 'sk-test',
    })

    await waitFor(() => {
      expect(mockedPostSetupModelCatalog).toHaveBeenCalledWith(
        'http://127.0.0.1:8000',
        {
          api_base: 'https://api.example.com/v1',
          api_key: 'sk-test',
        },
      )
    }, { timeout: 2000 })

    expect(screen.getByLabelText('Model name')).toHaveValue('gpt-4o')
    expect(screen.getByText('Loaded 2 model options from the provider.')).toBeInTheDocument()
  })

  it('renders explicit embedding provider fields', () => {
    renderProviderStep({})

    expect(screen.getByLabelText('Embedding API base URL (optional)')).toBeInTheDocument()
    expect(screen.getByLabelText('Embedding API key (optional)')).toBeInTheDocument()
    expect(screen.getByLabelText('Embedding model (optional)')).toBeInTheDocument()
    expect(
      screen.getByText(/Leave blank to keep the local embedding fallback/i),
    ).toBeInTheDocument()
  })
})
