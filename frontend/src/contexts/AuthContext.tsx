import { createContext, useContext } from 'react'
import type { AuthState } from '../hooks/useAuth'

export const AuthContext = createContext<AuthState | null>(null)

export function useAuthContext(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuthContext must be used within an AuthContext.Provider')
  }
  return ctx
}
