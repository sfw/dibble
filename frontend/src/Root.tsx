import { useCallback, useState } from 'react'
import { RouterProvider } from 'react-router'
import { router } from './router'
import { useAuth } from './hooks/useAuth'
import { AuthContext } from './contexts/AuthContext'
import { ConfigContext } from './contexts/ConfigContext'
import { loadStoredConfig } from './lib/storage'

export function Root() {
  const [baseUrl, setBaseUrl] = useState(() => loadStoredConfig().baseUrl)
  const auth = useAuth(baseUrl)

  const handleSetBaseUrl = useCallback((url: string) => {
    setBaseUrl(url)
    // Persist to localStorage so other parts of the app pick it up
    const stored = loadStoredConfig()
    window.localStorage.setItem(
      'dibble-frontend-config',
      JSON.stringify({ ...stored, baseUrl: url }),
    )
  }, [])

  return (
    <ConfigContext.Provider value={{ baseUrl, setBaseUrl: handleSetBaseUrl }}>
      <AuthContext.Provider value={auth}>
        <RouterProvider router={router} />
      </AuthContext.Provider>
    </ConfigContext.Provider>
  )
}
