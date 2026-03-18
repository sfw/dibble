import { defaultConfig } from '../sample-data'
import type { FrontendConfig } from '../types'

export const configStorageKey = 'dibble-frontend-config'

export function loadStoredConfig(): FrontendConfig {
  try {
    const raw = window.localStorage.getItem(configStorageKey)
    if (!raw) {
      return defaultConfig
    }

    return { ...defaultConfig, ...(JSON.parse(raw) as Partial<FrontendConfig>) }
  } catch {
    return defaultConfig
  }
}
