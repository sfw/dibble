import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  approveCurriculumMigrationPlan,
  createCurriculumMigrationPlan,
  listCurriculumImpactAnalyses,
  listCurriculumMigrationPlans,
  listCurriculumSnapshotDiffs,
  previewCurriculumMigrationExecution,
} from '@/api'
import type {
  CurriculumImpactAnalysis,
  CurriculumMigrationExecutionPreview,
  CurriculumMigrationPlan,
  CurriculumSnapshotDiff,
  FrontendConfig,
} from '@/types'

export function useMigrationReview(config: FrontendConfig) {
  const { apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback } = config
  const requestConfig = useMemo(
    () => ({ apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback }),
    [apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback],
  )
  const [diffs, setDiffs] = useState<CurriculumSnapshotDiff[]>([])
  const [impactAnalyses, setImpactAnalyses] = useState<CurriculumImpactAnalysis[]>([])
  const [plans, setPlans] = useState<CurriculumMigrationPlan[]>([])
  const [preview, setPreview] = useState<CurriculumMigrationExecutionPreview | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [loadedDiffs, loadedImpacts, loadedPlans] = await Promise.all([
        listCurriculumSnapshotDiffs(requestConfig),
        listCurriculumImpactAnalyses(requestConfig),
        listCurriculumMigrationPlans(requestConfig),
      ])
      setDiffs(loadedDiffs)
      setImpactAnalyses(loadedImpacts)
      setPlans(loadedPlans)
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to load migration review data.')
    } finally {
      setLoading(false)
    }
  }, [requestConfig])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const createPlan = useCallback(async (diffId: string) => {
    setWorking(true)
    setError('')
    try {
      const created = await createCurriculumMigrationPlan(requestConfig, diffId)
      setPlans((current) => [created, ...current.filter((plan) => plan.plan_id !== created.plan_id)])
      return created
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to create the migration plan.')
      return null
    } finally {
      setWorking(false)
    }
  }, [requestConfig])

  const approvePlan = useCallback(async (planId: string, reviewerId?: string | null) => {
    setWorking(true)
    setError('')
    try {
      const approved = await approveCurriculumMigrationPlan(requestConfig, planId, {
        reviewer_id: reviewerId ?? null,
        action_ids: [],
        approve_all_low_risk: true,
      })
      setPlans((current) => current.map((plan) => (plan.plan_id === approved.plan_id ? approved : plan)))
      return approved
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to approve low-risk migration actions.')
      return null
    } finally {
      setWorking(false)
    }
  }, [requestConfig])

  const previewPlanExecution = useCallback(async (planId: string, executorId?: string | null) => {
    setWorking(true)
    setError('')
    try {
      const executionPreview = await previewCurriculumMigrationExecution(requestConfig, planId, {
        executor_id: executorId ?? null,
        action_ids: [],
        dry_run: true,
      })
      setPreview(executionPreview)
      return executionPreview
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to preview migration execution.')
      return null
    } finally {
      setWorking(false)
    }
  }, [requestConfig])

  return {
    diffs,
    impactAnalyses,
    plans,
    preview,
    loading,
    working,
    error,
    refresh,
    createPlan,
    approvePlan,
    previewPlanExecution,
    setPreview,
  }
}
