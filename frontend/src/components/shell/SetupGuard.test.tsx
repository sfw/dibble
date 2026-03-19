import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router'
import { SetupGuard } from './SetupGuard'
import { ConfigContext } from '../../contexts/ConfigContext'
import { useSetupStatus } from '../../hooks/useSetupStatus'

vi.mock('../../hooks/useSetupStatus', () => ({
  useSetupStatus: vi.fn(),
}))

const mockedUseSetupStatus = vi.mocked(useSetupStatus)

function renderGuard(
  mode: 'configured' | 'unconfigured',
  initialEntry: string,
) {
  return render(
    <ConfigContext.Provider value={{ baseUrl: 'http://localhost:8000', setBaseUrl: vi.fn() }}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route
            path="/login"
            element={mode === 'configured'
              ? (
                  <SetupGuard mode={mode}>
                    <div>login page</div>
                  </SetupGuard>
                )
              : <div>login page</div>}
          />
          <Route
            path="/setup"
            element={mode === 'unconfigured'
              ? (
                  <SetupGuard mode={mode}>
                    <div>setup page</div>
                  </SetupGuard>
                )
              : <div>setup page</div>}
          />
        </Routes>
      </MemoryRouter>
    </ConfigContext.Provider>,
  )
}

describe('SetupGuard', () => {
  beforeEach(() => {
    mockedUseSetupStatus.mockReset()
  })

  it('redirects configured routes to setup when the backend is unconfigured', () => {
    mockedUseSetupStatus.mockReturnValue({
      status: {
        configured: false,
        has_llm_key: false,
        has_embedding_key: false,
        has_database: true,
        has_admin_user: false,
        llm_api_base: 'https://api.openai.com/v1',
        llm_model: null,
        auth_enabled: false,
        config_file_exists: false,
        app_version: '0.1.0',
      },
      reachable: true,
      loading: false,
      error: '',
      refetch: vi.fn(),
    })

    renderGuard('configured', '/login')

    expect(screen.getByText('setup page')).toBeInTheDocument()
  })

  it('renders configured routes when the backend is configured', () => {
    mockedUseSetupStatus.mockReturnValue({
      status: {
        configured: true,
        has_llm_key: true,
        has_embedding_key: false,
        has_database: true,
        has_admin_user: true,
        llm_api_base: 'https://api.openai.com/v1',
        llm_model: 'gpt-4o',
        auth_enabled: false,
        config_file_exists: true,
        app_version: '0.1.0',
      },
      reachable: true,
      loading: false,
      error: '',
      refetch: vi.fn(),
    })

    renderGuard('configured', '/login')

    expect(screen.getByText('login page')).toBeInTheDocument()
  })

  it('redirects setup route to login when the backend is already configured', () => {
    mockedUseSetupStatus.mockReturnValue({
      status: {
        configured: true,
        has_llm_key: true,
        has_embedding_key: false,
        has_database: true,
        has_admin_user: true,
        llm_api_base: 'https://api.openai.com/v1',
        llm_model: 'gpt-4o',
        auth_enabled: false,
        config_file_exists: true,
        app_version: '0.1.0',
      },
      reachable: true,
      loading: false,
      error: '',
      refetch: vi.fn(),
    })

    renderGuard('unconfigured', '/setup')

    expect(screen.getByText('login page')).toBeInTheDocument()
  })

  it('shows a loading state while setup status is resolving', () => {
    mockedUseSetupStatus.mockReturnValue({
      status: null,
      reachable: false,
      loading: true,
      error: '',
      refetch: vi.fn(),
    })

    renderGuard('configured', '/login')

    expect(screen.getByText('Checking setup...')).toBeInTheDocument()
  })
})
