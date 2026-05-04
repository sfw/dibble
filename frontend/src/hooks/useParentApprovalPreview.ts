import { useCallback, useState } from 'react'
import { getHouseholdParentApprovalPreview } from '@/api'
import type { FrontendConfig, ParentApprovalPreview } from '@/types'

type PreviewMap = Record<string, ParentApprovalPreview>
type LoadingMap = Record<string, boolean>

function previewKey(learnerId: string, approvalId: string) {
  return `${learnerId}:${approvalId}`
}

export function useParentApprovalPreview(config: FrontendConfig) {
  const [previews, setPreviews] = useState<PreviewMap>({})
  const [loading, setLoading] = useState<LoadingMap>({})
  const [error, setError] = useState('')

  const loadPreview = useCallback(async (learnerId: string, approvalId: string) => {
    const key = previewKey(learnerId, approvalId)
    setLoading((current) => ({ ...current, [key]: true }))
    setError('')

    try {
      const preview = await getHouseholdParentApprovalPreview(config, learnerId, approvalId)
      setPreviews((current) => ({ ...current, [key]: preview }))
      return preview
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to preview the teaching change.')
      return null
    } finally {
      setLoading((current) => ({ ...current, [key]: false }))
    }
  }, [config])

  return {
    error,
    previews,
    isLoading: (learnerId: string, approvalId: string) => loading[previewKey(learnerId, approvalId)] === true,
    getPreview: (learnerId: string, approvalId: string) => previews[previewKey(learnerId, approvalId)] ?? null,
    loadPreview,
  }
}
