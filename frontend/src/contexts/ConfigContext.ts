import { createContext, useContext } from 'react'

export interface ConfigContextValue {
  baseUrl: string
  setBaseUrl: (url: string) => void
}

export const ConfigContext = createContext<ConfigContextValue | null>(null)

export function useConfigContext(): ConfigContextValue {
  const ctx = useContext(ConfigContext)
  if (!ctx) {
    throw new Error('useConfigContext must be used within a ConfigContext.Provider')
  }
  return ctx
}
