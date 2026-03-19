import type { SystemConfigValues } from '../../types'

export type SystemConfigFieldKey = keyof SystemConfigValues

export interface SystemConfigFieldDefinition {
  key: SystemConfigFieldKey
  label: string
  description: string
  input: 'text' | 'password' | 'number' | 'url' | 'boolean'
  step?: string
  placeholder?: string
}

export interface SystemConfigSectionDefinition {
  key: string
  label: string
  description: string
  fields: SystemConfigFieldDefinition[]
}

export const systemConfigSections: SystemConfigSectionDefinition[] = [
  {
    key: 'application',
    label: 'Application',
    description: 'Core runtime identity and storage location for this Dibble instance.',
    fields: [
      {
        key: 'app_name',
        label: 'Application name',
        description: 'Used in API metadata and admin surfaces.',
        input: 'text',
      },
      {
        key: 'app_version',
        label: 'Application version',
        description: 'Version string exposed by the backend.',
        input: 'text',
      },
      {
        key: 'database_path',
        label: 'Database path',
        description: 'SQLite database file used by the backend.',
        input: 'text',
      },
    ],
  },
  {
    key: 'plugins',
    label: 'Plugins',
    description: 'Backend plugin entrypoints for routing, retrieval, generation, and validation.',
    fields: [
      {
        key: 'router_plugin',
        label: 'Router plugin',
        description: 'Python import path for the routing strategy.',
        input: 'text',
      },
      {
        key: 'retriever_plugin',
        label: 'Retriever plugin',
        description: 'Python import path for the retrieval strategy.',
        input: 'text',
      },
      {
        key: 'provider_plugin',
        label: 'Provider plugin',
        description: 'Python import path for the content provider.',
        input: 'text',
      },
      {
        key: 'validator_plugin',
        label: 'Validator plugin',
        description: 'Python import path for the response validator.',
        input: 'text',
      },
    ],
  },
  {
    key: 'llm',
    label: 'LLM',
    description: 'Primary language-model provider settings used for generation.',
    fields: [
      {
        key: 'llm_api_base',
        label: 'LLM API base URL',
        description: 'Base URL for the primary chat/completions provider.',
        input: 'url',
        placeholder: 'https://api.openai.com/v1',
      },
      {
        key: 'llm_api_key',
        label: 'LLM API key',
        description: 'API key for the primary LLM provider.',
        input: 'password',
      },
      {
        key: 'llm_model',
        label: 'LLM model',
        description: 'Default generation model.',
        input: 'text',
      },
      {
        key: 'llm_timeout_seconds',
        label: 'LLM timeout (seconds)',
        description: 'Request timeout for the primary provider.',
        input: 'number',
        step: '0.1',
      },
      {
        key: 'llm_allow_mock_fallback',
        label: 'Allow mock fallback',
        description: 'Permit mock responses when no real provider is available.',
        input: 'boolean',
      },
    ],
  },
  {
    key: 'llm-failover',
    label: 'LLM Failover',
    description: 'Secondary LLM and resilience controls for degraded provider conditions.',
    fields: [
      {
        key: 'llm_secondary_api_base',
        label: 'Secondary API base URL',
        description: 'Optional override for the failover provider endpoint.',
        input: 'url',
      },
      {
        key: 'llm_secondary_api_key',
        label: 'Secondary API key',
        description: 'Optional key for the failover provider.',
        input: 'password',
      },
      {
        key: 'llm_secondary_model',
        label: 'Secondary model',
        description: 'Optional model name for failover requests.',
        input: 'text',
      },
      {
        key: 'llm_secondary_timeout_seconds',
        label: 'Secondary timeout (seconds)',
        description: 'Optional timeout override for failover requests.',
        input: 'number',
        step: '0.1',
      },
      {
        key: 'llm_selection_strategy',
        label: 'Selection strategy',
        description: 'Strategy used to choose between configured providers.',
        input: 'text',
      },
      {
        key: 'llm_circuit_breaker_threshold',
        label: 'Circuit breaker threshold',
        description: 'Failures before the provider is considered unhealthy.',
        input: 'number',
        step: '1',
      },
      {
        key: 'llm_circuit_breaker_cooldown_seconds',
        label: 'Circuit breaker cooldown (seconds)',
        description: 'How long to wait before retrying an unhealthy provider.',
        input: 'number',
        step: '0.1',
      },
    ],
  },
  {
    key: 'prompts',
    label: 'Prompts',
    description: 'Prompt library and experimentation controls.',
    fields: [
      {
        key: 'prompt_library_version',
        label: 'Prompt library version',
        description: 'Version label for prompt assets.',
        input: 'text',
      },
      {
        key: 'prompt_experiment_enabled',
        label: 'Enable prompt experiments',
        description: 'Allow prompt experiments during runtime.',
        input: 'boolean',
      },
      {
        key: 'prompt_adaptive_selection_enabled',
        label: 'Enable adaptive prompt selection',
        description: 'Use adaptive prompt selection from audit signals.',
        input: 'boolean',
      },
      {
        key: 'prompt_variant_override',
        label: 'Prompt variant override',
        description: 'Force a specific prompt variant across the application.',
        input: 'text',
      },
    ],
  },
  {
    key: 'embeddings',
    label: 'Embeddings',
    description: 'Vectorization and local fallback settings for retrieval.',
    fields: [
      {
        key: 'embedding_api_base',
        label: 'Embedding API base URL',
        description: 'Base URL for the embedding provider.',
        input: 'url',
      },
      {
        key: 'embedding_api_key',
        label: 'Embedding API key',
        description: 'Optional key for the embedding provider.',
        input: 'password',
      },
      {
        key: 'embedding_model',
        label: 'Embedding model',
        description: 'Optional external embedding model. Leave blank for local fallback only.',
        input: 'text',
      },
      {
        key: 'embedding_dimensions',
        label: 'Embedding dimensions',
        description: 'Dimensionality for local embeddings.',
        input: 'number',
        step: '1',
      },
      {
        key: 'embedding_timeout_seconds',
        label: 'Embedding timeout (seconds)',
        description: 'Request timeout for embedding calls.',
        input: 'number',
        step: '0.1',
      },
      {
        key: 'embedding_allow_local_fallback',
        label: 'Allow local embedding fallback',
        description: 'Use the local hash embedder when no remote embedding model is configured.',
        input: 'boolean',
      },
    ],
  },
  {
    key: 'auth',
    label: 'Auth',
    description: 'Authentication and token issuance settings.',
    fields: [
      {
        key: 'auth_enabled',
        label: 'Enable auth',
        description: 'Require authenticated requests for protected endpoints.',
        input: 'boolean',
      },
      {
        key: 'auth_token_secret',
        label: 'Token signing secret',
        description: 'Required to issue bearer tokens.',
        input: 'password',
      },
      {
        key: 'auth_token_issuer',
        label: 'Token issuer',
        description: 'Issuer claim used for bearer tokens.',
        input: 'text',
      },
      {
        key: 'auth_token_ttl_seconds',
        label: 'Access token TTL (seconds)',
        description: 'Lifetime of issued bearer tokens.',
        input: 'number',
        step: '1',
      },
      {
        key: 'auth_refresh_ttl_seconds',
        label: 'Refresh token TTL (seconds)',
        description: 'Lifetime of refresh tokens.',
        input: 'number',
        step: '1',
      },
    ],
  },
  {
    key: 'performance',
    label: 'Performance',
    description: 'Cache and scheduler settings for generation performance.',
    fields: [
      {
        key: 'generation_cache_ttl_seconds',
        label: 'Generation cache TTL (seconds)',
        description: 'How long generated content remains cacheable.',
        input: 'number',
        step: '1',
      },
      {
        key: 'predictive_warm_inline_process_limit',
        label: 'Predictive warm inline limit',
        description: 'Maximum inline warm tasks before background scheduling takes over.',
        input: 'number',
        step: '1',
      },
    ],
  },
]
