import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { SystemConfig } from './SystemConfig'
import { AuthContext } from '../../contexts/AuthContext'
import { ConfigContext } from '../../contexts/ConfigContext'
import type { AuthState } from '../../hooks/useAuth'
import { getSystemConfig, updateSystemConfig } from '../../api'
import type { SystemConfigValues } from '../../types'

vi.mock('../../api', () => ({
  getSystemConfig: vi.fn(),
  updateSystemConfig: vi.fn(),
}))

const mockedGetSystemConfig = vi.mocked(getSystemConfig)
const mockedUpdateSystemConfig = vi.mocked(updateSystemConfig)

function makeAuthState(): AuthState {
  return {
    identity: {
      principal_id: 'admin-1',
      role: 'admin',
      auth_scheme: 'api_key',
      display_name: 'Admin Operator',
      learner_id: null,
    },
    authenticated: true,
    loading: false,
    error: '',
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    getToken: vi.fn().mockReturnValue(''),
    getApiKey: vi.fn().mockReturnValue('admin-key'),
  }
}

function buildValues(): SystemConfigValues {
  return {
    app_name: 'Dibble Adaptive Platform',
    app_version: '0.3.0',
    database_path: '/Users/sfw/.dibble/dibble.db',
    router_plugin: 'dibble.plugins.defaults.router:build',
    retriever_plugin: 'dibble.plugins.defaults.retriever:build',
    provider_plugin: 'dibble.plugins.defaults.provider:build',
    validator_plugin: 'dibble.plugins.defaults.validator:build',
    llm_api_base: 'https://api.moonshot.ai/v1',
    llm_api_key: 'sk-test',
    llm_model: 'kimi-k2.5',
    llm_timeout_seconds: 20,
    llm_allow_mock_fallback: false,
    llm_secondary_api_base: null,
    llm_secondary_api_key: null,
    llm_secondary_model: null,
    llm_secondary_timeout_seconds: null,
    llm_circuit_breaker_threshold: 2,
    llm_circuit_breaker_cooldown_seconds: 30,
    llm_selection_strategy: 'ordered',
    prompt_library_version: '1.0',
    prompt_experiment_enabled: false,
    prompt_adaptive_selection_enabled: false,
    prompt_variant_override: null,
    embedding_api_base: 'https://api.moonshot.ai/v1',
    embedding_api_key: 'sk-embed',
    embedding_model: 'moonshot-vectors',
    embedding_dimensions: 256,
    embedding_timeout_seconds: 15,
    embedding_allow_local_fallback: true,
    auth_enabled: false,
    auth_token_secret: null,
    auth_token_issuer: 'dibble',
    auth_token_ttl_seconds: 3600,
    auth_refresh_ttl_seconds: 604800,
    generation_cache_ttl_seconds: 3600,
    predictive_warm_inline_process_limit: 2,
  }
}

describe('SystemConfig', () => {
  beforeEach(() => {
    mockedGetSystemConfig.mockReset()
    mockedUpdateSystemConfig.mockReset()
  })

  it('loads the current config and saves edited values', async () => {
    const values = buildValues()
    mockedGetSystemConfig.mockResolvedValue({
      config_path: '/Users/sfw/.dibble/config.toml',
      config_file_exists: true,
      values,
    })
    mockedUpdateSystemConfig.mockResolvedValue({
      status: 'ok',
      config_path: '/Users/sfw/.dibble/config.toml',
      restart_required: true,
    })

    render(
      <ConfigContext.Provider value={{ baseUrl: 'http://localhost:8000', setBaseUrl: vi.fn() }}>
        <AuthContext.Provider value={makeAuthState()}>
          <MemoryRouter>
            <SystemConfig />
          </MemoryRouter>
        </AuthContext.Provider>
      </ConfigContext.Provider>,
    )

    const nameInput = await screen.findByLabelText('Application name')
    expect(nameInput).toHaveValue('Dibble Adaptive Platform')

    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'Dibble Control Plane')
    await userEvent.click(screen.getByRole('button', { name: /save config/i }))

    await waitFor(() => {
      expect(mockedUpdateSystemConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          baseUrl: 'http://localhost:8000',
        }),
        expect.objectContaining({
          app_name: 'Dibble Control Plane',
        }),
      )
    })

    expect(
      screen.getByText('Configuration saved. Restart the backend to apply runtime changes.'),
    ).toBeInTheDocument()
  })
})
