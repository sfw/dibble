import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  getRolloutEvaluationSummary,
  getRolloutPolicy,
  simulateRolloutPolicyChange,
  updateRolloutPolicy,
} from '@/api'
import type {
  EvaluationSummaryResponse,
  FrontendConfig,
  RolloutPolicy,
  RolloutSimulationResponse,
  RolloutSimulationSubject,
} from '@/types'

function deriveSubjects(policy: RolloutPolicy): RolloutSimulationSubject[] {
  const subjects: RolloutSimulationSubject[] = []
  const seen = new Set<string>()

  for (const cohort of policy.cohorts) {
    for (const learnerId of cohort.learner_ids) {
      const key = `learner:${learnerId}`
      if (seen.has(key)) {
        continue
      }
      seen.add(key)
      subjects.push({
        learner_id: learnerId,
        label: `${cohort.label} learner ${learnerId}`,
      })
    }

    for (const householdId of cohort.household_ids) {
      const key = `household:${householdId}`
      if (seen.has(key)) {
        continue
      }
      seen.add(key)
      subjects.push({
        household_id: householdId,
        label: `${cohort.label} household ${householdId}`,
      })
    }
  }

  return subjects
}

export function useRolloutGovernance(config: FrontendConfig) {
  const { apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback } = config
  const requestConfig = useMemo(
    () => ({ apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback }),
    [apiKey, baseUrl, bearerToken, showDebugPanels, useDemoFallback],
  )
  const [policy, setPolicy] = useState<RolloutPolicy | null>(null)
  const [draftPolicy, setDraftPolicy] = useState<RolloutPolicy | null>(null)
  const [evaluationSummary, setEvaluationSummary] = useState<EvaluationSummaryResponse | null>(null)
  const [simulation, setSimulation] = useState<RolloutSimulationResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [simulating, setSimulating] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [policyResponse, evaluation] = await Promise.all([
        getRolloutPolicy(requestConfig),
        getRolloutEvaluationSummary(requestConfig),
      ])
      setPolicy(policyResponse.policy)
      setDraftPolicy(policyResponse.policy)
      setEvaluationSummary(evaluation)
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to load rollout governance.')
    } finally {
      setLoading(false)
    }
  }, [requestConfig])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const defaultSubjects = useMemo(
    () => (draftPolicy ? deriveSubjects(draftPolicy) : []),
    [draftPolicy],
  )

  const runSimulation = useCallback(async (subjects: RolloutSimulationSubject[]) => {
    if (!draftPolicy) {
      return null
    }

    setSimulating(true)
    setError('')
    try {
      const response = await simulateRolloutPolicyChange(requestConfig, {
        proposed_policy: draftPolicy,
        subjects,
        include_unchanged: false,
      })
      setSimulation(response)
      return response
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to simulate the rollout policy.')
      return null
    } finally {
      setSimulating(false)
    }
  }, [draftPolicy, requestConfig])

  const savePolicy = useCallback(async () => {
    if (!draftPolicy) {
      return null
    }

    setSaving(true)
    setError('')
    try {
      const response = await updateRolloutPolicy(requestConfig, { policy: draftPolicy })
      setPolicy(response.policy)
      setDraftPolicy(response.policy)
      return response.policy
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Unable to save the rollout policy.')
      return null
    } finally {
      setSaving(false)
    }
  }, [draftPolicy, requestConfig])

  return {
    policy,
    draftPolicy,
    setDraftPolicy,
    evaluationSummary,
    simulation,
    defaultSubjects,
    loading,
    saving,
    simulating,
    error,
    refresh,
    runSimulation,
    savePolicy,
  }
}
