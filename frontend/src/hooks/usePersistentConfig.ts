import { useEffect, useState } from 'react'

import { configStorageKey, loadStoredConfig } from '../lib/storage'
import type { FrontendConfig } from '../types'

export function usePersistentConfig() {
  const [config, setConfig] = useState<FrontendConfig>(() => loadStoredConfig())

  useEffect(() => {
    window.localStorage.setItem(configStorageKey, JSON.stringify(config))
  }, [config])

  return {
    config,
    setConfig,
  }
}
