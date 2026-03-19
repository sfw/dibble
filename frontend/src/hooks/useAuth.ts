import { useCallback, useEffect, useRef, useState } from 'react'

import { getAuthIdentity, issueAuthToken, refreshAuthToken, revokeAuthToken } from '../api'
import type { AuthIdentity, AuthToken, FrontendConfig } from '../types'

const AUTH_STORAGE_KEY = 'dibble-auth'

interface StoredAuth {
  apiKey: string
  accessToken: string
  authMode: 'api_key' | 'bearer'
  refreshToken: string | null
  identity: AuthIdentity
  expiresAt: number // epoch ms
}

function loadStoredAuth(): StoredAuth | null {
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<StoredAuth>
    const normalized: StoredAuth = {
      apiKey: parsed.apiKey ?? '',
      accessToken: parsed.accessToken ?? '',
      authMode: parsed.authMode ?? (parsed.accessToken ? 'bearer' : 'api_key'),
      refreshToken: parsed.refreshToken ?? null,
      identity: parsed.identity as AuthIdentity,
      expiresAt: parsed.expiresAt ?? Number.MAX_SAFE_INTEGER,
    }
    if (!normalized.identity) return null
    if (normalized.authMode === 'api_key' && !normalized.apiKey) return null
    if (normalized.authMode !== 'api_key' && !normalized.accessToken) return null
    return normalized
  } catch {
    return null
  }
}

function saveAuth(auth: StoredAuth): void {
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth))
}

function clearAuth(): void {
  window.localStorage.removeItem(AUTH_STORAGE_KEY)
}

function tokenToStored(token: AuthToken): StoredAuth {
  return {
    apiKey: '',
    accessToken: token.access_token,
    authMode: 'bearer',
    refreshToken: token.refresh_token ?? null,
    identity: token.identity,
    expiresAt: Date.now() + token.expires_in * 1000,
  }
}

function apiKeyToStored(identity: AuthIdentity, apiKey: string): StoredAuth {
  return {
    apiKey,
    accessToken: '',
    authMode: 'api_key',
    refreshToken: null,
    identity,
    expiresAt: Number.MAX_SAFE_INTEGER,
  }
}

export interface AuthState {
  identity: AuthIdentity | null
  authenticated: boolean
  loading: boolean
  error: string
  login: (apiKey: string, baseUrl: string) => Promise<AuthIdentity>
  logout: () => Promise<void>
  /** Returns the current valid bearer token, refreshing if needed. */
  getToken: () => string
  getApiKey: () => string
}

export function useAuth(baseUrl: string): AuthState {
  const [stored, setStored] = useState<StoredAuth | null>(() => loadStoredAuth())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const refreshingRef = useRef<Promise<StoredAuth> | null>(null)

  // On mount, check if the stored token is still valid; try refresh if expired
  useEffect(() => {
    if (!stored) return
    if (stored.authMode !== 'bearer') return
    if (stored.expiresAt > Date.now()) return

    // Token expired — try refresh
    if (stored.refreshToken) {
      const config: FrontendConfig = {
        baseUrl,
        apiKey: '',
        bearerToken: stored.accessToken,
        useDemoFallback: false,
        showDebugPanels: false,
      }
      refreshAuthToken(config, stored.refreshToken)
        .then((token) => {
          const next = tokenToStored(token)
          saveAuth(next)
          setStored(next)
        })
        .catch(() => {
          clearAuth()
          setStored(null)
        })
    } else {
      clearAuth()
      setStored(null)
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = useCallback(
    async (apiKey: string, configBaseUrl: string): Promise<AuthIdentity> => {
      setLoading(true)
      setError('')
      try {
        const config: FrontendConfig = {
          baseUrl: configBaseUrl,
          apiKey,
          bearerToken: '',
          useDemoFallback: false,
          showDebugPanels: false,
        }
        let next: StoredAuth
        try {
          const token = await issueAuthToken(config)
          next = tokenToStored(token)
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Login failed'
          const canUseApiKeySession =
            message.includes('auth_token_unavailable') ||
            message.includes('DIBBLE_AUTH_TOKEN_SECRET')
          if (!canUseApiKeySession) {
            throw err
          }

          const identity = await getAuthIdentity(config)
          next = apiKeyToStored(identity, apiKey)
        }
        saveAuth(next)
        setStored(next)
        return next.identity
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Login failed'
        setError(message)
        throw err
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  const logout = useCallback(async () => {
    if (stored?.authMode === 'bearer') {
      try {
        const config: FrontendConfig = {
          baseUrl,
          apiKey: '',
          bearerToken: stored.accessToken,
          useDemoFallback: false,
          showDebugPanels: false,
        }
        await revokeAuthToken(config, stored.refreshToken ?? undefined)
      } catch {
        // Best-effort revocation
      }
    }
    clearAuth()
    setStored(null)
    setError('')
  }, [baseUrl, stored])

  const getToken = useCallback((): string => {
    if (!stored) return ''
    if (stored.authMode !== 'bearer') return ''

    // If token is still valid (with 60s buffer), return it
    if (stored.expiresAt > Date.now() + 60_000) {
      return stored.accessToken
    }

    // Token is expiring soon or expired — try a synchronous refresh
    if (stored.refreshToken && !refreshingRef.current) {
      const config: FrontendConfig = {
        baseUrl,
        apiKey: '',
        bearerToken: stored.accessToken,
        useDemoFallback: false,
        showDebugPanels: false,
      }
      refreshingRef.current = refreshAuthToken(config, stored.refreshToken)
        .then((token) => {
          const next = tokenToStored(token)
          saveAuth(next)
          setStored(next)
          refreshingRef.current = null
          return next
        })
        .catch(() => {
          clearAuth()
          setStored(null)
          refreshingRef.current = null
          return null as unknown as StoredAuth
        })
    }

    // Return current token while refresh is in-flight
    return stored.accessToken
  }, [baseUrl, stored])

  const getApiKey = useCallback((): string => {
    if (!stored || stored.authMode !== 'api_key') {
      return ''
    }
    return stored.apiKey
  }, [stored])

  return {
    identity: stored?.identity ?? null,
    authenticated: stored !== null,
    loading,
    error,
    login,
    logout,
    getToken,
    getApiKey,
  }
}
