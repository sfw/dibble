import { useCallback, useEffect, useRef, useState } from 'react'

import { getLearnerProfile, getLearnerWorkspace, getLearners } from '../api'
import type { DataSource } from '../app/workspace'
import { asMessage } from '../lib/formatters'
import { SAMPLE_STUDENT_ID, demoLearnerFlow, demoLearnerWorkspace, demoProfile, demoProfileSummary } from '../sample-data'
import type { FrontendConfig, LearnerFlowSummary, LearnerProfileV2, LearnerWorkspace, ProfileSummary } from '../types'

export function useLearnerWorkspace({
  config,
  initialLearnerId,
  onDataSourceChange,
}: {
  config: FrontendConfig
  initialLearnerId?: string
  onDataSourceChange: (source: DataSource) => void
}) {
  const hasBootstrapped = useRef(false)
  const [learnerId, setLearnerId] = useState(initialLearnerId ?? SAMPLE_STUDENT_ID)
  const [learnerIds, setLearnerIds] = useState<string[]>([SAMPLE_STUDENT_ID])
  const [summary, setSummary] = useState<ProfileSummary>(demoProfileSummary)
  const [profile, setProfile] = useState<LearnerProfileV2>(demoProfile)
  const [flow, setFlow] = useState<LearnerFlowSummary>(demoLearnerFlow)
  const [workspace, setWorkspace] = useState<LearnerWorkspace>(demoLearnerWorkspace)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(!config.useDemoFallback)

  const loadLearnerIds = useCallback(async () => {
    try {
      const ids = await getLearners(config)
      if (ids.length > 0) {
        setLearnerIds(ids)
      }
    } catch {
      setLearnerIds((current) => Array.from(new Set([SAMPLE_STUDENT_ID, ...current])))
    }
  }, [config])

  const loadLearnerWorkspace = useCallback(async (studentId: string) => {
    setLoading(true)
    setError('')

    try {
      const [nextWorkspace, nextProfile] = await Promise.all([
        getLearnerWorkspace(config, studentId),
        getLearnerProfile(config, studentId),
      ])
      setWorkspace(nextWorkspace)
      setSummary(nextWorkspace.summary)
      setProfile(nextProfile)
      setFlow(nextWorkspace.summary.current_flow)
      onDataSourceChange('live')
      setLearnerId(studentId)
    } catch (caughtError) {
      if (!config.useDemoFallback) {
        setError(asMessage(caughtError))
        return
      }

      setWorkspace(demoLearnerWorkspace)
      setSummary(demoProfileSummary)
      setProfile(demoProfile)
      setFlow(demoLearnerFlow)
      onDataSourceChange('demo')
      setError(`${asMessage(caughtError)} Showing demo data instead.`)
      setLearnerId(studentId)
    } finally {
      setLoading(false)
    }
  }, [config, onDataSourceChange])

  const refreshCurrentLearner = useCallback(async () => {
    await loadLearnerWorkspace(learnerId)
  }, [learnerId, loadLearnerWorkspace])

  useEffect(() => {
    if (hasBootstrapped.current) {
      return
    }

    hasBootstrapped.current = true
    void loadLearnerWorkspace(learnerId)
    void loadLearnerIds()
  }, [learnerId, loadLearnerIds, loadLearnerWorkspace])

  return {
    learnerId,
    setLearnerId,
    learnerIds,
    summary,
    profile,
    flow,
    workspace,
    error,
    loading,
    loadLearnerWorkspace,
    refreshCurrentLearner,
  }
}
