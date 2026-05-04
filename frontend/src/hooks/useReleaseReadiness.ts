import { useCallback, useEffect, useMemo, useState } from 'react'
import { getReleaseReadiness } from '@/api'
import type { FrontendConfig, ReleaseReadinessSnapshot } from '@/types'

export function useReleaseReadiness(config: FrontendConfig) {
  const { apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback } = config
  const requestConfig = useMemo(
    () => ({ apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback }),
    [apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback],
  )
  const [readiness, setReadiness] = useState<ReleaseReadinessSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setReadiness(await getReleaseReadiness(requestConfig))
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to load release readiness.')
    } finally {
      setLoading(false)
    }
  }, [requestConfig])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return {
    readiness,
    loading,
    error,
    refresh,
  }
}
