import { useCallback, useEffect, useState } from 'react'
import { getSetupStatus } from '../api'
import type { SetupStatus } from '../types'

export interface UseSetupStatusResult {
  status: SetupStatus | null
  reachable: boolean
  loading: boolean
  error: string
  refetch: () => void
}

export function useSetupStatus(baseUrl: string): UseSetupStatusResult {
  const [status, setStatus] = useState<SetupStatus | null>(null)
  const [reachable, setReachable] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await getSetupStatus(baseUrl)
      setStatus(result)
      setReachable(true)
    } catch (err) {
      setReachable(false)
      setStatus(null)
      setError(err instanceof Error ? err.message : 'Failed to reach server')
    } finally {
      setLoading(false)
    }
  }, [baseUrl])

  useEffect(() => {
    void fetchStatus()
  }, [fetchStatus])

  return { status, reachable, loading, error, refetch: fetchStatus }
}
