import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { StaffDashboard } from './StaffDashboard'
import { AuthContext } from '../../contexts/AuthContext'
import { ConfigContext } from '../../contexts/ConfigContext'
import type { AuthState } from '../../hooks/useAuth'
import { getSystemConfig } from '../../api'
import { useSetupStatus } from '../../hooks/useSetupStatus'

vi.mock('../../api', () => ({
  getSystemConfig: vi.fn(),
}))

vi.mock('../../hooks/useSetupStatus', () => ({
  useSetupStatus: vi.fn(),
}))

const mockedGetSystemConfig = vi.mocked(getSystemConfig)
const mockedUseSetupStatus = vi.mocked(useSetupStatus)

function makeAuthState(role: string): AuthState {
  return {
    identity: {
      principal_id: 'user-1',
      role,
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

describe('StaffDashboard', () => {
  beforeEach(() => {
    mockedUseSetupStatus.mockReturnValue({
      status: {
        configured: true,
        has_llm_key: true,
        has_embedding_key: true,
        has_database: true,
        has_admin_user: true,
        llm_api_base: 'https://api.moonshot.ai/v1',
        llm_model: 'kimi-k2.5',
        auth_enabled: false,
        config_file_exists: true,
        app_version: '0.3.0',
      },
      reachable: true,
      loading: false,
      error: '',
      refetch: vi.fn(),
    })
    mockedGetSystemConfig.mockResolvedValue({
      config_path: '/Users/sfw/.dibble/config.toml',
      config_file_exists: true,
      values: {
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
        llm_debug_prompts_enabled: false,
      },
    })
  })

  it('renders admin summary cards and quick actions', async () => {
    render(
      <ConfigContext.Provider value={{ baseUrl: 'http://localhost:8000', setBaseUrl: vi.fn() }}>
        <AuthContext.Provider value={makeAuthState('admin')}>
          <MemoryRouter>
            <StaffDashboard />
          </MemoryRouter>
        </AuthContext.Provider>
      </ConfigContext.Provider>,
    )

    expect(screen.getByText('Operate Dibble as a service, not a demo.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open configuration/i })).toHaveAttribute('href', '/staff/config')

    await waitFor(() => {
      expect(screen.getByText('Embedding model: moonshot-vectors')).toBeInTheDocument()
    })
  })
})
