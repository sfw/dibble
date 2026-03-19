import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { SetupCompleteStep } from './SetupCompleteStep'
import { ConfigContext } from '../../contexts/ConfigContext'
import { useSetupStatus } from '../../hooks/useSetupStatus'

const navigateMock = vi.fn()

vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router')
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

vi.mock('../../hooks/useSetupStatus', () => ({
  useSetupStatus: vi.fn(),
}))

const mockedUseSetupStatus = vi.mocked(useSetupStatus)

function renderStep() {
  return render(
    <ConfigContext.Provider value={{ baseUrl: 'http://127.0.0.1:8000', setBaseUrl: vi.fn() }}>
      <SetupCompleteStep configPath="~/.dibble/config.toml" />
    </ConfigContext.Provider>,
  )
}

describe('SetupCompleteStep', () => {
  beforeEach(() => {
    navigateMock.mockReset()
    mockedUseSetupStatus.mockReset()
  })

  it('rechecks the backend instead of navigating when setup is not active yet', async () => {
    const refetch = vi.fn()
    mockedUseSetupStatus.mockReturnValue({
      status: {
        configured: false,
        has_llm_key: true,
        has_embedding_key: false,
        has_database: true,
        has_admin_user: false,
        llm_api_base: 'http://127.0.0.1:8000',
        llm_model: 'gpt-4o',
        auth_enabled: false,
        config_file_exists: true,
        app_version: '0.3.0',
      },
      reachable: true,
      loading: false,
      error: '',
      refetch,
    })

    renderStep()
    await userEvent.click(screen.getByRole('button', { name: 'Check server again' }))

    expect(refetch).toHaveBeenCalled()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('navigates to login once the backend reports configured', async () => {
    mockedUseSetupStatus.mockReturnValue({
      status: {
        configured: true,
        has_llm_key: true,
        has_embedding_key: false,
        has_database: true,
        has_admin_user: false,
        llm_api_base: 'http://127.0.0.1:8000',
        llm_model: 'gpt-4o',
        auth_enabled: false,
        config_file_exists: true,
        app_version: '0.3.0',
      },
      reachable: true,
      loading: false,
      error: '',
      refetch: vi.fn(),
    })

    renderStep()
    await userEvent.click(screen.getByRole('button', { name: 'Go to sign in' }))

    expect(navigateMock).toHaveBeenCalledWith('/login', { replace: true })
  })
})
